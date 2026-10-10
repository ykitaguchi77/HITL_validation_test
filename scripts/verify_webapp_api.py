"""End-to-end machine check of the blinded webapp API (no browser needed).

Uses FastAPI's TestClient against scripts/webapp/backend/main.py with the real
experiment.json + proposals.json, under a throw-away RESULTS_DIR:

  1. no torch import at startup; startup validation passes
  2. /api/run, /api/session, /api/predict never expose n / seed / model / condition /
     group / proposal_key / filename / metrics
  3. manual items -> empty initial; proposal items -> non-empty initial (or the
     precomputed empty proposal), byte-identical to proposals.json
  4. /api/predict latency is indistinguishable between manual and proposal items
  5. /api/submit writes summary.csv with n / seed / *_prop_* / per-class edit columns
  6. /api/practice_gt returns GT for practice and 403 for study sessions

Run:  python scripts/verify_webapp_api.py
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "scripts" / "webapp" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import config  # noqa: E402
TMP = Path(tempfile.mkdtemp(prefix="hitl_verify_"))
config.RESULTS_DIR = TMP           # session.py reads RESULTS_DIR at import -> patch before importing main
import session  # noqa: E402
session.RESULTS_DIR = TMP

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

assert "torch" not in sys.modules, "torch was imported at startup"
client = TestClient(main.app)
EXP = main.EXPERIMENT
PROPOSALS = json.loads(config.PROPOSALS_JSON.read_text(encoding="utf-8"))
SECRET_KEYS = {"n", "seed", "model", "condition", "group", "proposal_key", "filename", "metrics",
               "proposal_metrics", "train_size", "patient_id", "slot"}
annot = EXP["annotators"][0]
fails = 0


def check(cond, msg):
    global fails
    print(("  ok   " if cond else "  FAIL ") + msg)
    fails += (not cond)


def walk(o, path="$"):
    if isinstance(o, dict):
        for k, v in o.items():
            assert k not in SECRET_KEYS, f"{path}.{k} exposed"
            walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, f"{path}[{i}]")


# 1-2. run / session listings
run = client.get(f"/api/run/{annot}").json()
walk(run)
keys = [s["key"] for s in run["sessions"]]
check(len(run["sessions"]) == len(EXP["practice"]) + EXP["n_sessions"], f"run lists {len(run['sessions'])} sessions {keys}")
main_key = next(s["key"] for s in run["sessions"] if not s["is_practice"])
sess = client.get(f"/api/session/{annot}/{main_key}").json()
walk(sess)
check(len(sess["images"]) == EXP["n_per_session"], f"session {main_key} has {len(sess['images'])} images, no hidden fields")

# 3-4. predict for every item of the session; compare to the hidden truth
items = {it["image_id"]: it for s in EXP["runs"][annot]["sessions"] if s["key"] == main_key for it in s["items"]}
lat = {"manual": [], "proposal": []}
ok_shapes = True
for im in sess["images"]:
    it = items[im["image_id"]]
    for _ in range(5):
        t0 = time.perf_counter()
        r = client.post("/api/predict", json={"annotator": annot, "session_key": main_key, "image_id": im["image_id"]})
        lat["manual" if it["n"] == 0 else "proposal"].append(time.perf_counter() - t0)
    body = r.json()
    walk(body)
    initial = body["initial"]
    if it["n"] == 0:
        ok_shapes &= all(len(v) == 0 for v in initial.values())
    else:
        truth = PROPOSALS["images"][it["filename"]]["proposals"][f"n{it['n']}"][f"s{it['seed']}"]["shapes"]
        ok_shapes &= initial == truth
check(ok_shapes, "manual -> empty initial; proposal -> identical to proposals.json (blind body)")
m, p = statistics.median(lat["manual"]) * 1000, statistics.median(lat["proposal"]) * 1000
check(abs(m - p) < 50, f"/api/predict latency manual {m:.1f} ms vs proposal {p:.1f} ms (diff < 50 ms)")

# 5. submit one manual and one proposal item
def submit(it, sid):
    ann = {"eyelid": [[[100, 100], [300, 100], [300, 300], [100, 300]]],
           "iris": [{"cx": 200, "cy": 200, "rx": 50, "ry": 40, "rotation": 10}],
           "pupil": [{"cx": 200, "cy": 200, "rx": 20, "ry": 18, "rotation": 0}], "caruncle": []}
    init = client.post("/api/predict", json={"annotator": annot, "session_key": main_key, "image_id": it["image_id"]}).json()["initial"]
    metrics = {"duration_sec": 12.3, "total_clicks": 5, "vertices_added": 1, "vertices_moved": 2, "vertices_deleted": 0,
               "shapes_created": 1, "shapes_deleted": 0,
               "per_class": {k: {"clicks": 1, "time_sec": 4.0, "vertices_edited": 1, "vertices_added": 1,
                                 "vertices_moved": 0, "vertices_deleted": 0, "shapes_created": 0, "shapes_deleted": 0}
                             for k in ("eyelid", "iris", "pupil")}}
    r = client.post("/api/submit", json={"session_id": sid, "annotator": annot, "session_key": main_key,
                                         "image_id": it["image_id"], "attempt": 1, "annotation": ann,
                                         "initial": init, "metrics": metrics, "effort": 4})
    return r.status_code == 200

sid = f"verify_{annot}_{main_key}"
man = next(it for it in items.values() if it["n"] == 0)
prop = next(it for it in items.values() if it["n"] == 128) if any(it["n"] == 128 for it in items.values()) \
    else next(it for it in items.values() if it["n"] > 0)
check(submit(man, sid) and submit(prop, sid), "submit manual + proposal items")
rows = list(csv.DictReader(open(TMP / sid / "summary.csv", encoding="utf-8")))
cols = rows[0].keys()
need = ["n", "seed", "group", "proposal_key", "eyelid_prop_assd", "iris_prop_dice", "pupil_prop_area_diff",
        "eyelid_vertices_added", "pupil_shapes_deleted"]
check(all(c in cols for c in need), f"summary.csv has {need}")
check(rows[0]["n"] == "0" and rows[0]["eyelid_prop_assd"] == "" and rows[1]["n"] == str(prop["n"])
      and rows[1]["seed"] == str(prop["seed"]) and rows[1]["eyelid_prop_assd"] != "",
      f"rows: manual n=0 (no prop metrics) / proposal n={rows[1]['n']} seed={rows[1]['seed']} prop_assd={rows[1]['eyelid_prop_assd'][:6]}")
rec = [json.loads(l) for l in open(TMP / sid / "records.jsonl", encoding="utf-8")]
check(rec[1]["proposal_metrics"]["eyelid"]["assd"] == PROPOSALS["images"][prop["filename"]]["proposals"][f"n{prop['n']}"][f"s{prop['seed']}"]["metrics"]["eyelid"]["assd"],
      "records.jsonl proposal_metrics copied from proposals.json")

# 6. practice GT
pk = EXP["practice"][1]["key"]
pit = EXP["practice"][1]["items"][0]
pinit = client.post("/api/predict", json={"annotator": annot, "session_key": pk, "image_id": pit["image_id"]}).json()["initial"]
check(any(len(v) for v in pinit.values()), f"practice '{pk}' item has a proposal (n={pit['n']})")
r = client.post("/api/practice_gt", json={"annotator": annot, "session_key": pk, "image_id": pit["image_id"], "annotation": pinit})
check(r.status_code == 200 and "gt" in r.json() and "scores" in r.json(), "practice_gt returns GT + Dice for practice")
r = client.post("/api/practice_gt", json={"annotator": annot, "session_key": main_key, "image_id": man["image_id"], "annotation": pinit})
check(r.status_code == 403, "practice_gt refuses study sessions (403)")
# test pseudo-annotator maps to annotator 1
check(client.get("/api/run/test").json()["sessions"] == run["sessions"], "'test' alias runs annotator 1's sessions")

print(f"\n{'ALL CHECKS PASSED' if not fails else f'{fails} CHECK(S) FAILED'}  (scratch results in {TMP})")
sys.exit(1 if fails else 0)
