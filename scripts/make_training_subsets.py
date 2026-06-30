"""Build patient-safe, nested training subsets (~500/1000/1500/2000/2500 images)
for the HITL models, and VERIFY no patient leaks into the held-out test set.

Leakage policy (strict, by patient):
  - A patient is "test-eligible" iff its minimum annotated image_id >= TEST_START
    (same rule prepare_experiment.py uses to build the test pool). All 60 test
    images come from these patients.
  - Training uses ONLY patients whose min annotated id < TEST_START, i.e. patients
    that are NOT test-eligible. These two patient sets are disjoint by construction,
    so no training image can share a patient with any test image.
Patient id = filename.split('-')[0] (same as the training notebook).

Subsets are nested (500 ⊂ 1000 ⊂ ... ⊂ all): whole patients are added in a fixed
shuffled order until each image-count target is reached (counts need not be exact).
Only images that have all three annotations (eyelid + iris + pupil) and an existing
file are used. Writes outputs/training_subsets/subsets.json.

Run:  python scripts/make_training_subsets.py
"""
from __future__ import annotations

import json
import random
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "webapp" / "backend"))
from config import IMAGES_DIR, EYELID_XML, EXPERIMENT_JSON  # noqa: E402
from geometry import get_gt_annotation                       # noqa: E402

SEED = 42
TEST_START = 2500
ID_MAX = 2999                 # training notebook's MAX_IMAGE_ID
TARGETS = [100, 200, 300, 500, 1000, 1500, 2000, 2500]
OUT = ROOT / "outputs" / "training_subsets" / "subsets.json"


def patient_of(name: str) -> str:
    return name.split("-")[0]


def main() -> None:
    tree = ET.parse(EYELID_XML)
    imgs = [{"image_id": int(im.attrib["id"]), "filename": im.attrib["name"],
             "patient_id": patient_of(im.attrib["name"]), "n_shapes": len(list(im))}
            for im in tree.getroot().findall("image")]

    # min annotated id per patient -> test-eligible patients (>= TEST_START)
    min_ann = defaultdict(lambda: 10**9)
    for r in imgs:
        if r["n_shapes"] > 0:
            min_ann[r["patient_id"]] = min(min_ann[r["patient_id"]], r["image_id"])
    test_eligible = {p for p, mid in min_ann.items() if mid >= TEST_START}

    # patients actually used by the held-out test set (cross-check)
    exp = json.loads(Path(EXPERIMENT_JSON).read_text(encoding="utf-8"))
    test_used = {e["patient_id"] for blk in exp["assignments"].values() for e in blk}

    # training pool: not test-eligible, in id range, has eyelid+iris+pupil, file exists
    pool = []
    for r in imgs:
        if r["image_id"] > ID_MAX or r["patient_id"] in test_eligible:
            continue
        if not (IMAGES_DIR / r["filename"]).exists():
            continue
        ann = get_gt_annotation(r["filename"])
        if ann.get("eyelid") and ann.get("iris") and ann.get("pupil"):
            pool.append(r)

    # group by patient, fixed shuffled patient order, accumulate to nested subsets
    by_pat = defaultdict(list)
    for r in pool:
        by_pat[r["patient_id"]].append(r)
    patients = sorted(by_pat)                 # deterministic base order
    random.Random(SEED).shuffle(patients)

    ordered = []                              # images in patient-block order
    for p in patients:
        ordered.extend(sorted(by_pat[p], key=lambda r: r["image_id"]))

    subsets = {}
    for t in TARGETS:
        # take whole patients until we reach >= t images (nested by construction)
        names, pats, count = [], [], 0
        for p in patients:
            block = sorted(by_pat[p], key=lambda r: r["image_id"])
            names += [r["filename"] for r in block]
            pats.append(p)
            count += len(block)
            if count >= t:
                break
        subsets[str(t)] = {"target": t, "n_images": len(names),
                           "n_patients": len(pats), "patients": pats, "images": names}

    # ---- leakage verification ----
    print("=== patient-leakage verification ===")
    all_ok = True
    test_patients = test_eligible  # superset of test_used
    for t in TARGETS:
        s = subsets[str(t)]
        sp = set(s["patients"])
        leak_elig = sp & test_eligible
        leak_used = sp & test_used
        ok = not leak_elig and not leak_used
        all_ok &= ok
        print(f"  ~{t:>4}: {s['n_images']:>4} imgs / {s['n_patients']:>3} patients | "
              f"leak(test-used)={len(leak_used)} leak(test-eligible)={len(leak_elig)} -> "
              f"{'OK' if ok else 'LEAK!'}")
    # nesting check
    nested = all(set(subsets[str(TARGETS[i])]["images"]) <= set(subsets[str(TARGETS[i + 1])]["images"])
                 for i in range(len(TARGETS) - 1))
    print(f"  nested (each subset subset of the next): {nested}")
    print(f"  training pool: {len(pool)} imgs / {len(by_pat)} patients (all min-id < {TEST_START})")
    print(f"  test set: {len(test_used)} patients used, {len(test_eligible)} eligible (min-id >= {TEST_START})")
    print(f"  overlap train-pool-patients ∩ test-eligible = {len(set(by_pat) & test_eligible)} (must be 0)")
    print(f"\n  ALL CHECKS: {'PASS' if (all_ok and nested and not (set(by_pat) & test_eligible)) else 'FAIL'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {"seed": SEED, "test_start": TEST_START, "id_max": ID_MAX, "targets": TARGETS,
            "n_test_patients_used": len(test_used), "n_test_eligible": len(test_eligible),
            "pool_images": len(pool), "pool_patients": len(by_pat)}
    OUT.write_text(json.dumps({"meta": meta, "subsets": subsets}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
