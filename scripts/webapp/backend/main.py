"""FastAPI app for the BLIND n-shot dose-response HITL annotation study.

Run from scripts/webapp/backend:
    uvicorn main:app --reload --port 8000
Then open http://localhost:8000

Design: every main session mixes the 8 proposal conditions (n = 1..128 fixed
decoder-LoRA checkpoints, 3 training-order seeds) with manual items (n = 0) in
random order. Blinding contract: the client never receives n / seed / model /
condition / group / filename. The server resolves the hidden item per
(annotator, session, image), serves the PRECOMPUTED proposal (no runtime
inference -> identical latency for manual and proposal items) and writes the
hidden truth + the proposal's precomputed GT metrics into the saved record.
Practice is exempt (GT is revealed for calibration) and its images are disjoint
from the study images.
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

from config import STATIC_DIR, IMAGES_DIR, CLASSES, RESULTS_DIR, load_experiment, load_tokens
from geometry import get_gt_annotation, rasterize_class, mask_to_polygon
from inference import get_proposal, get_proposal_metrics, validate as validate_proposals
from scoring import score_annotation
from session import save_record, completed_attempts

app = FastAPI(title="Eyelid HITL Annotation (blind)")
DEBUG = os.environ.get("HITL_DEBUG") == "1"

EXPERIMENT = load_experiment()
if EXPERIMENT.get("version") != 2:
    raise RuntimeError("experiment.json is not the v2 (dose_response_nshot) schema; "
                       "re-run scripts/prepare_experiment.py")
RUNS = EXPERIMENT.get("runs", {})
PRACTICE = EXPERIMENT.get("practice", [])
PRACTICE_BY_KEY = {p["key"]: p for p in PRACTICE}
ANNOTATORS = EXPERIMENT.get("annotators", [])
# "test" is a functional-test pseudo-annotator: it runs annotator 1's assignment but
# its records save under session_id "test_..." (annotator="test"), separate from real data.
RUN_ALIAS = {"test": ANNOTATORS[0]}
UI_ANNOTATORS = ["test"]   # real annotators are reachable ONLY via their personal link

# Identity: the client never names a real annotator itself. It sends an "ident" =
# "test" or the personal token from its link (?t=...), and the server maps the
# token to the annotator. Tokens are random, so a typo / wrong link is rejected
# instead of silently running someone else's assignment.
TOKENS = {t: a for t, a in load_tokens().items() if a in RUNS}
_missing = sorted(set(ANNOTATORS) - set(TOKENS.values()))
if _missing:
    print(f"[tokens] WARNING: no personal link for {_missing} "
          "-> run: python scripts/make_annotator_links.py")


def _who(ident: str) -> str:
    """Annotator name for an ident ("test" or a personal token); 403 if unknown."""
    ident = str(ident)
    if ident == "test":
        return "test"
    if ident in TOKENS:
        return TOKENS[ident]
    raise HTTPException(403, "unknown personal link")


def _run(annotator: str):
    return RUNS.get(RUN_ALIAS.get(str(annotator), str(annotator)))


def _check_session_id(annotator: str, session_id: str) -> None:
    """Records may only be written/discarded under the caller's own name."""
    if not str(session_id).startswith(f"{annotator}_"):
        raise HTTPException(403, "session_id does not belong to this annotator")

# image_id -> {filename, width, height, ...}  (study groups + practice)
IMG_INDEX: dict[int, dict] = {}
for _src in (*EXPERIMENT.get("groups", {}).values(), *[p["items"] for p in PRACTICE]):
    for _e in _src:
        IMG_INDEX.setdefault(_e["image_id"], _e)

# fail fast if any item's precomputed proposal is missing / proposals.json changed
print(f"[proposals] {validate_proposals(EXPERIMENT)} proposal items verified")


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


# --- helpers ---------------------------------------------------------------
def _resolve(annotator: str, session_key: str, image_id: int):
    """Hidden item dict for (annotator, session, image), or None.
    Adds is_practice / is_hitl / session_index; items carry n / seed / model /
    condition / proposal_key themselves (practice items too).
    `annotator` is the client's ident (403 if it is not a valid link)."""
    name = _who(annotator)
    ps = PRACTICE_BY_KEY.get(session_key)
    if ps is not None:
        for it in ps["items"]:
            if it["image_id"] == image_id:
                return {**it, "condition": "practice", "is_practice": True,
                        "is_hitl": ps.get("is_hitl", True),
                        "session_key": session_key, "session_index": -1}
        return None
    run = _run(name)
    if not run:
        return None
    for s in run["sessions"]:
        if s["key"] == session_key:
            for it in s["items"]:
                if it["image_id"] == image_id:
                    return {**it, "is_practice": False, "is_hitl": s["is_hitl"],
                            "session_key": session_key, "session_index": s["session_index"]}
    return None


def _predict(it: dict) -> dict:
    """Precomputed proposal for the hidden item (empty for manual, n = 0).
    Both branches are dict lookups: no latency difference between conditions."""
    e = IMG_INDEX.get(it["image_id"])
    if not e:
        raise HTTPException(404, "unknown image")
    return get_proposal(e["filename"], it.get("n") or 0, it.get("seed") or 0)


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
    annotator: str


class CheckReq(BaseModel):
    annotator: str
    session_key: str
    image_id: int
    annotation: dict


# --- endpoints -------------------------------------------------------------
_CLIENT_CLASSES = [{k: c[k] for k in ("key", "name", "kind", "color")} for c in CLASSES]


# frontend build id = newest mtime of the static files at server start; the
# client compares it at every session start and reloads itself when it changed,
# so a tab left open for days never runs stale JS (per-class metrics bug 09/20)
APP_VERSION = str(int(max(p.stat().st_mtime for p in STATIC_DIR.rglob("*") if p.is_file())))


@app.get("/api/whoami/{ident}")
def whoami(ident: str):
    """Annotator name for a personal-link token (shown so they can confirm it's them)."""
    return {"annotator": _who(ident)}


@app.get("/api/config")
def get_config():
    return {"classes": _CLIENT_CLASSES, "n_per_session": EXPERIMENT.get("n_per_session"),
            "annotators": UI_ANNOTATORS, "debug": DEBUG, "app_version": APP_VERSION}


@app.get("/api/run/{annotator}")
def get_run(annotator: str):
    name = _who(annotator)
    run = _run(name)
    if not run:
        raise HTTPException(404, "unknown annotator")
    sessions = [{"key": p["key"], "is_hitl": p["is_hitl"], "is_practice": True,
                 "label": p["label"], "n_images": len(p["items"])} for p in PRACTICE]
    for s in run["sessions"]:   # blinded: no model/condition/block
        sessions.append({"key": s["key"], "is_hitl": s["is_hitl"], "is_practice": False,
                         "label": s["label"], "n_images": len(s["items"])})
    # completion comes from the saved records (not the browser), so it follows the
    # annotator across PCs/browsers and the next attempt number is always correct
    done = completed_attempts(name, {s["key"]: s["n_images"] for s in sessions})
    for s in sessions:
        s["completed"] = done.get(s["key"], 0)
    return {"annotator": name, "sessions": sessions}


@app.get("/api/session/{annotator}/{session_key}")
def get_session(annotator: str, session_key: str):
    name = _who(annotator)
    ps = PRACTICE_BY_KEY.get(session_key)
    if ps is not None:
        items, label, is_hitl, is_practice = ps["items"], ps["label"], ps.get("is_hitl", True), True
    else:
        run = _run(name)
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
    return {"initial": _predict(it)}   # NO n / seed / model field (blind)


@app.post("/api/submit")
def submit(req: SubmitReq):
    name = _who(req.annotator)
    _check_session_id(name, req.session_id)
    it = _resolve(req.annotator, req.session_key, req.image_id)
    if it is None:
        raise HTTPException(404, "image not in this session")
    e = IMG_INDEX[req.image_id]
    # correction metrics (final vs proposal) only make sense for proposal items;
    # for manual items the client sends an empty initial -> skip (else Dice 0)
    has_proposal = bool(it.get("n"))
    scores = score_annotation(e["filename"], req.annotation, e["width"], e["height"],
                              initial=req.initial if has_proposal else None)
    record = {
        "session_id": req.session_id, "annotator": name,
        "attempt": req.attempt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_key": it["session_key"], "session_index": it["session_index"],
        "condition": it.get("condition"), "model": it.get("model"),
        "n": it.get("n") or 0, "seed": it.get("seed"), "train_size": it.get("n") or 0,
        "proposal_key": it.get("proposal_key"),
        "is_hitl": it.get("is_hitl"), "is_practice": it.get("is_practice"),
        "group": it.get("group"), "gaze": it.get("gaze"), "ecc": it.get("ecc"),
        "order_in_session": it.get("order_in_session"),
        "image_id": req.image_id, "filename": e["filename"],
        "native_size": [e["width"], e["height"]],
        "annotation": req.annotation, "initial": req.initial,
        "effort": req.effort,
        "metrics": req.metrics, "scores": scores,
        # precomputed proposal-vs-GT metrics (what the annotator was shown)
        "proposal_metrics": get_proposal_metrics(e["filename"], it.get("n") or 0, it.get("seed") or 0),
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
    _check_session_id(_who(req.annotator), req.session_id)
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


# static frontend (mounted last so /api/* wins)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
