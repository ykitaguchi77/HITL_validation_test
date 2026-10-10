"""Step A: freeze the study image pool for the n-shot dose-response HITL study.

Draws S*G study images (+5 practice) from the patient-safe held-out pool
(outputs/training_subsets/heldout_test.json, image_id 2500..2999, all 3 GT
labels), gaze-classified by de-baselined iris eccentricity exactly as the
previous design did, with at most MAX_PER_PATIENT images per patient.

The output JSON is the single contract consumed by BOTH repos:
  * Eyelid_few_shot_HITL/scripts/eval/make_nshot_checkpoints.py excludes
    `excluded_patients` (= every patient of the held-out pool, not just the
    selected ones) from training orders and the model-eval set;
  * scripts/prepare_experiment.py builds experiment.json from `images`.
Its sha256 is carried through manifest.json / proposals.json / experiment.json.

Run:  python scripts/select_study_images.py [--annotators 6] [--group-size G]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "webapp" / "backend"))
from study_design import design_params  # noqa: E402
from config import IMAGES_DIR  # noqa: E402
from geometry import get_gt_annotation  # noqa: E402

SEED = 42
HELDOUT_JSON = ROOT / "outputs" / "training_subsets" / "heldout_test.json"
OUT_JSON = ROOT / "outputs" / "study_pool" / "study_images.json"
ECC_THRESHOLD = 0.20
MAX_PER_PATIENT = 5
PRACTICE = {"frontal": 3, "peripheral": 2}


def patient_of(name: str) -> str:
    return name.split("-")[0]


def _poly_bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def iris_offset(ann: dict):
    """Signed (ex, ey): iris OBB centre minus eyelid bbox centre, normalised by
    eyelid bbox size (same definition as the previous design)."""
    eyelids, irises = ann.get("eyelid") or [], ann.get("iris") or []
    if not eyelids or not irises:
        return None
    best = max(eyelids, key=lambda p: (lambda b: (b[2] - b[0]) * (b[3] - b[1]))(_poly_bbox(p)))
    x0, y0, x1, y1 = _poly_bbox(best)
    w, h = (x1 - x0), (y1 - y0)
    if w <= 0 or h <= 0:
        return None
    return ((irises[0]["cx"] - (x0 + x1) / 2) / w, (irises[0]["cy"] - (y0 + y1) / 2) / h)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _draw(rng, cands, need, per_patient: Counter):
    """Greedy sample honouring the per-patient cap; cands already shuffled."""
    out = []
    for r in cands:
        if len(out) == need:
            break
        if per_patient[r["patient_id"]] >= MAX_PER_PATIENT:
            continue
        per_patient[r["patient_id"]] += 1
        out.append(r)
    if len(out) < need:
        raise SystemExit(f"only {len(out)}/{need} images available under the patient cap")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotators", type=int, default=6)
    ap.add_argument("--group-size", type=int, default=None)
    args = ap.parse_args()
    p = design_params(args.annotators, args.group_size)

    held = json.load(open(HELDOUT_JSON, encoding="utf-8"))
    pool_all = held["images"]
    excluded_patients = sorted({r["patient_id"] for r in pool_all})

    # keep images with all three GT structures and an existing file
    pool, offsets = [], {}
    for r in pool_all:
        if not (IMAGES_DIR / r["filename"]).exists():
            continue
        ann = get_gt_annotation(r["filename"])
        if not (ann["eyelid"] and ann["iris"] and ann["pupil"]):
            continue
        o = iris_offset(ann)
        if o is None:
            continue
        offsets[r["image_id"]] = o
        pool.append(dict(r, stem=Path(r["filename"]).stem))
    pool.sort(key=lambda r: r["image_id"])

    # gaze: de-baseline by the pool median offset (removes anatomical vertical bias)
    have = list(offsets.values())
    mex = sorted(o[0] for o in have)[len(have) // 2]
    mey = sorted(o[1] for o in have)[len(have) // 2]
    for r in pool:
        dx, dy = offsets[r["image_id"]][0] - mex, offsets[r["image_id"]][1] - mey
        r["ecc"] = round((dx * dx + dy * dy) ** 0.5, 4)
        r["gaze"] = "peripheral" if r["ecc"] >= ECC_THRESHOLD else "frontal"
    frontal = [r for r in pool if r["gaze"] == "frontal"]
    peripheral = [r for r in pool if r["gaze"] == "peripheral"]

    rng = random.Random(SEED)
    rng.shuffle(frontal); rng.shuffle(peripheral)
    per_patient: Counter = Counter()
    study_f = _draw(rng, frontal, p["n_study_frontal"], per_patient)
    study_p = _draw(rng, peripheral, p["n_study_peripheral"], per_patient)
    used = {r["image_id"] for r in study_f + study_p}
    prac_f = _draw(rng, [r for r in frontal if r["image_id"] not in used], PRACTICE["frontal"], per_patient)
    prac_p = _draw(rng, [r for r in peripheral if r["image_id"] not in used], PRACTICE["peripheral"], per_patient)

    images = ([dict(r, role="study") for r in study_f + study_p]
              + [dict(r, role="practice") for r in prac_f + prac_p])
    images.sort(key=lambda r: (r["role"] != "study", r["image_id"]))

    # --- assertions -------------------------------------------------------
    ids = [r["image_id"] for r in images]; stems = [r["stem"] for r in images]
    assert len(ids) == len(set(ids)) == len(set(stems)) == p["n_study_images"] + 5
    assert all(r["patient_id"] in excluded_patients for r in images)
    study = [r for r in images if r["role"] == "study"]
    assert Counter(r["gaze"] for r in study) == {"frontal": p["n_study_frontal"],
                                                  "peripheral": p["n_study_peripheral"]}
    assert Counter(r["gaze"] for r in images if r["role"] == "practice") == PRACTICE
    assert max(Counter(r["patient_id"] for r in images).values()) <= MAX_PER_PATIENT

    out = {
        "seed": SEED, "source": str(HELDOUT_JSON.relative_to(ROOT)),
        "design": {k: v for k, v in p.items()},
        "ecc_threshold": ECC_THRESHOLD, "gaze_baseline": {"ex": round(mex, 4), "ey": round(mey, 4)},
        "max_per_patient": MAX_PER_PATIENT,
        "pool_size": len(pool), "pool_frontal": len(frontal), "pool_peripheral": len(peripheral),
        "excluded_patients": excluded_patients,
        "images": [{k: r[k] for k in ("image_id", "filename", "stem", "patient_id", "width",
                                      "height", "gaze", "ecc", "role")} for r in images],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"pool {len(pool)} (F {len(frontal)} / P {len(peripheral)}), "
          f"study {len(study)} (F {p['n_study_frontal']} / P {p['n_study_peripheral']}), "
          f"practice 5, patients used {len({r['patient_id'] for r in images})}, "
          f"excluded_patients {len(excluded_patients)}")
    print(f"Wrote {OUT_JSON}\nsha256 {sha256_of(OUT_JSON)}")


if __name__ == "__main__":
    main()
