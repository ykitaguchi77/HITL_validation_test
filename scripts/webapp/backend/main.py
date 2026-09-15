"""FastAPI app for the BLIND, Latin-square, interleaved HITL annotation study.

Run from scripts/webapp/backend:
    uvicorn main:app --reload --port 8000
Then open http://localhost:8000

Blinding contract: for HITL sessions the client never receives the model /
condition / block. The server resolves the hidden model per (annotator, session,
image) to compute the prefill, and writes the hidden truth into the saved record
for later analysis. Practice is exempt (GT is revealed for calibration) and its
images are disjoint from the 90 study images.
"""
from __future__ import annotations

import base64
import os
import secrets
import shutil
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (STATIC_DIR, IMAGES_DIR, CLASSES, RESULTS_DIR, load_experiment,
                    resolve_model_path, SEGFORMER_BACKBONE)
from geometry import get_gt_annotation, rasterize_class, mask_to_polygon
from scoring import score_annotation
from session import save_record

app = FastAPI(title="Eyelid HITL Annotation (blind)")
DEBUG = os.environ.get("HITL_DEBUG") == "1"

EXPERIMENT = load_experiment()
MODELS = EXPERIMENT["models"]
RUNS = EXPERIMENT.get("runs", {})
PRACTICE = EXPERIMENT.get("practice", [])
if isinstance(PRACTICE, dict):   # back-compat with the old single-practice schema
    PRACTICE = [dict(PRACTICE, key="practice", is_hitl=True, label="練習 (Practice)")]
PRACTICE_BY_KEY = {p["key"]: p for p in PRACTICE}
ANNOTATORS = EXPERIMENT.get("annotators", [])
# "test" is a functional-test pseudo-annotator: it runs annotator 1's assignment but
# its records save under session_id "test_..." (annotator="test"), separate from real data.
RUN_ALIAS = {"test": (ANNOTATORS[0] if ANNOTATORS else "kubota")}
UI_ANNOTATORS = ["test"] + list(ANNOTATORS)   # practice/test shown first


def _run(annotator: str):
    return RUNS.get(RUN_ALIAS.get(str(annotator), str(annotator)))

# image_id -> {filename, width, height, ...}  (study blocks + practice + legacy)
IMG_INDEX: dict[int, dict] = {}
for _src in (*EXPERIMENT.get("blocks", {}).values(),
             *[p["items"] for p in PRACTICE],
             *EXPERIMENT.get("assignments", {}).values()):
    for _e in _src:
        IMG_INDEX.setdefault(_e["image_id"], _e)

PHASE_BY_KEY = {p["key"]: p for p in EXPERIMENT.get("phases", [])}  # legacy/debug


@app.middleware("http")
async def _no_cache(request: Request, call_next):
    """Never cache the HTML/JS/CSS so frontend edits show up on a normal reload."""
    resp = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".js", ".css", ".html")):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


# --- shared-password HTTP Basic auth (案A) ---------------------------------
# Enabled whenever HITL_AUTH_PASS is set in the environment. When the app is
# exposed via a Cloudflare tunnel this MUST be set, otherwise the medical images
# are reachable by anyone who has the URL. On localhost it can be left unset for
# convenience. The startup script (run_server.ps1) always sets it.
AUTH_USER = os.environ.get("HITL_AUTH_USER", "annotator")
AUTH_PASS = os.environ.get("HITL_AUTH_PASS", "")
if not AUTH_PASS:
    print("[auth] WARNING: HITL_AUTH_PASS is not set -> access control DISABLED. "
          "Do NOT expose this server via a public tunnel without it.")


@app.middleware("http")
async def _basic_auth(request: Request, call_next):
    """Gate every request behind one shared username/password (HTTP Basic)."""
    if AUTH_PASS:
        hdr = request.headers.get("authorization", "")
        ok = False
        if hdr.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(hdr[6:]).decode("utf-8").partition(":")
                ok = (secrets.compare_digest(user, AUTH_USER)
                      and secrets.compare_digest(pw, AUTH_PASS))
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401, content="Authentication required",
                            headers={"WWW-Authenticate": 'Basic realm="HITL Annotation"'})
    return await call_next(request)


def _warm_models():
    """Pre-load every subset checkpoint into the inference cache at startup so the
    first /api/predict per model is a fast forward pass, not a multi-second cold
    load (which previously made the 1st image's prefill pop in mid-annotation)."""
    try:
        from inference import _load
    except Exception:
        return
    for m in MODELS.values():
        try:
            _load(m["path"], (m or {}).get("backbone") or SEGFORMER_BACKBONE)
        except Exception:
            pass


import threading  # noqa: E402
threading.Thread(target=_warm_models, daemon=True, name="warm-models").start()


# --- helpers ---------------------------------------------------------------
def _backbone(model: str) -> str:
    return (MODELS.get(model, {}) or {}).get("backbone") or SEGFORMER_BACKBONE


def _resolve(annotator: str, session_key: str, image_id: int):
    """Hidden item dict for (annotator, session, image), or None.
    Adds is_practice / is_hitl / session_index / model / condition."""
    ps = PRACTICE_BY_KEY.get(session_key)
    if ps is not None:
        for it in ps["items"]:
            if it["image_id"] == image_id:
                return {**it, "model": ps.get("model"), "condition": "practice",
                        "train_size": None, "is_practice": True, "is_hitl": ps.get("is_hitl", True),
                        "session_key": session_key, "session_index": -1}
        return None
    run = _run(annotator)
    if not run:
        return None
    for s in run["sessions"]:
        if s["key"] == session_key:
            for it in s["items"]:
                if it["image_id"] == image_id:
                    return {**it, "is_practice": False, "is_hitl": s["is_hitl"],
                            "session_key": session_key, "session_index": s["session_index"]}
    return None


def _predict(model: str | None, image_id: int) -> dict:
    e = IMG_INDEX.get(image_id)
    if not e:
        raise HTTPException(404, "unknown image")
    if not model:   # scratch -> empty initial
        return {"eyelid": [], "caruncle": [], "iris": [], "pupil": []}
    from inference import predict_initial_shapes  # lazy: torch only when needed
    path = resolve_model_path(model, EXPERIMENT)
    return predict_initial_shapes(str(IMAGES_DIR / e["filename"]), path,
                                  e["width"], e["height"], _backbone(model))


# --- API models ------------------------------------------------------------
class PredictReq(BaseModel):
    annotator: str
    session_key: str
    image_id: int


class SubmitReq(BaseModel):
    session_id: str
    annotator: str
    session_key: str
    image_id: int
    attempt: int = 1
    annotation: dict
    initial: dict | None = None
    metrics: dict
    effort: int | None = None   # Paas single-item mental-effort rating (1-9)


class AbortReq(BaseModel):
    session_id: str


class CheckReq(BaseModel):
    annotator: str
    session_key: str
    image_id: int
    annotation: dict


# --- endpoints -------------------------------------------------------------
_CLIENT_CLASSES = [{k: c[k] for k in ("key", "name", "kind", "color")} for c in CLASSES]


@app.get("/api/config")
def get_config():
    return {"classes": _CLIENT_CLASSES, "n_per_session": EXPERIMENT.get("n_per_session"),
            "annotators": UI_ANNOTATORS, "debug": DEBUG}


@app.get("/api/run/{annotator}")
def get_run(annotator: str):
    run = _run(annotator)
    if not run:
        raise HTTPException(404, "unknown annotator")
    sessions = [{"key": p["key"], "is_hitl": p["is_hitl"], "is_practice": True,
                 "label": p["label"], "n_images": len(p["items"])} for p in PRACTICE]
    for s in run["sessions"]:   # blinded: no model/condition/block
        sessions.append({"key": s["key"], "is_hitl": s["is_hitl"], "is_practice": False,
                         "label": s["label"], "n_images": len(s["items"])})
    return {"annotator": str(annotator), "sessions": sessions}


@app.get("/api/session/{annotator}/{session_key}")
def get_session(annotator: str, session_key: str):
    ps = PRACTICE_BY_KEY.get(session_key)
    if ps is not None:
        items, label, is_hitl, is_practice = ps["items"], ps["label"], ps.get("is_hitl", True), True
    else:
        run = _run(annotator)
        if not run:
            raise HTTPException(404, "unknown annotator")
        s = next((s for s in run["sessions"] if s["key"] == session_key), None)
        if not s:
            raise HTTPException(404, "unknown session")
        items, label, is_hitl, is_practice = s["items"], s["label"], s["is_hitl"], False
    # blinded image list (no filename / model / condition / block)
    return {"key": session_key, "label": label, "is_hitl": is_hitl, "is_practice": is_practice,
            "images": [{"image_id": it["image_id"], "width": it["width"],
                        "height": it["height"], "url": f"/api/image/{it['image_id']}"}
                       for it in items]}


@app.post("/api/predict")
def predict(req: PredictReq):
    it = _resolve(req.annotator, req.session_key, req.image_id)
    if it is None:
        raise HTTPException(404, "image not in this session")
    return {"initial": _predict(it.get("model"), req.image_id)}   # NO model field (blind)


@app.post("/api/submit")
def submit(req: SubmitReq):
    it = _resolve(req.annotator, req.session_key, req.image_id)
    if it is None:
        raise HTTPException(404, "image not in this session")
    e = IMG_INDEX[req.image_id]
    scores = score_annotation(e["filename"], req.annotation, e["width"], e["height"],
                              initial=req.initial)
    record = {
        "session_id": req.session_id, "annotator": str(req.annotator),
        "attempt": req.attempt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_key": it["session_key"], "session_index": it["session_index"],
        "condition": it.get("condition"), "model": it.get("model"),
        "train_size": it.get("train_size"), "is_hitl": it.get("is_hitl"),
        "is_practice": it.get("is_practice"), "is_repeat": it.get("is_repeat", False),
        "block": it.get("block"), "gaze": it.get("gaze"), "ecc": it.get("ecc"),
        "order_in_session": it.get("order_in_session"),
        "image_id": req.image_id, "filename": e["filename"],
        "native_size": [e["width"], e["height"]],
        "annotation": req.annotation, "initial": req.initial,
        "effort": req.effort,
        "metrics": req.metrics, "scores": scores,
    }
    save_record(req.session_id, record)
    # GT calibration feedback for practice is shown on the confirmation screen
    # (via /api/practice_gt) BEFORE saving, so no post-save review is needed here.
    return {"ok": True, "is_practice": bool(it.get("is_practice"))}


def _practice_feedback(e: dict, annotation: dict) -> dict:
    """Merged-eyelid GT outline + per-class Dice for practice calibration."""
    scores = score_annotation(e["filename"], annotation, e["width"], e["height"])
    gt = get_gt_annotation(e["filename"])
    # merge Eyelid+Caruncle into a single outer outline (no internal boundary line)
    eyelid_mask = rasterize_class(gt.get("eyelid", []), "polygon", e["height"], e["width"])
    eyelid_outline = mask_to_polygon(eyelid_mask)
    gt_out = {"eyelid": [eyelid_outline] if eyelid_outline else [],
              "iris": gt.get("iris", []), "pupil": gt.get("pupil", [])}
    return {"gt": gt_out,
            "scores": {k: round(v.get("dice", 0.0), 3) for k, v in scores["per_class"].items()},
            "mean_dice": round(scores["mean_dice"], 3)}


@app.post("/api/practice_gt")
def practice_gt(req: CheckReq):
    """Dry-run GT + Dice for the confirmation screen (practice only; never saves,
    and refuses real sessions so GT is never revealed there)."""
    it = _resolve(req.annotator, req.session_key, req.image_id)
    if it is None:
        raise HTTPException(404, "image not in this session")
    if not it.get("is_practice"):
        raise HTTPException(403, "GT is only available for practice sessions")
    return _practice_feedback(IMG_INDEX[req.image_id], req.annotation)


@app.post("/api/abort")
def abort(req: AbortReq):
    """Discard an aborted session's partial records (folder must be under RESULTS_DIR)."""
    base = RESULTS_DIR.resolve()
    d = (RESULTS_DIR / req.session_id).resolve()
    if d.is_dir() and base in d.parents:
        shutil.rmtree(d, ignore_errors=True)
    return {"ok": True}


@app.get("/api/image/{image_id}")
def get_image(image_id: int):
    e = IMG_INDEX.get(image_id)
    if not e:
        raise HTTPException(404, "unknown image")
    path = IMAGES_DIR / e["filename"]
    if not path.exists():
        raise HTTPException(404, "image file missing")
    return FileResponse(str(path))


# --- legacy debug endpoints (only when HITL_DEBUG=1) -----------------------
if DEBUG:
    @app.get("/api/phase/{phase_key}")
    def get_phase(phase_key: str):
        if phase_key not in PHASE_BY_KEY:
            raise HTTPException(404, "unknown phase")
        ph = PHASE_BY_KEY[phase_key]
        return {"phase": phase_key, "label": ph["label"], "model": ph["model"],
                "is_hitl": ph["model"] is not None,
                "images": [{"image_id": e["image_id"], "filename": e["filename"],
                            "width": e["width"], "height": e["height"],
                            "url": f"/api/image/{e['image_id']}"}
                           for e in EXPERIMENT["assignments"][phase_key]]}


# static frontend (mounted last so /api/* wins)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
