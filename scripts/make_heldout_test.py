"""Build the fixed 500-image held-out TEST set for final model evaluation.

Drawn from test-eligible patients (min annotated image_id >= TEST_START), so it is
patient-disjoint from every training subset (which only uses patients with min id <
TEST_START). Images must have all three annotations (eyelid + iris + pupil) and an
existing file. Saved to outputs/training_subsets/heldout_test.json and verified to
share no patient and no image with the largest training subset.

Run:  python scripts/make_heldout_test.py
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
from config import IMAGES_DIR, EYELID_XML, IRIS_XML  # noqa: E402

SEED = 42
TEST_START, TEST_END = 2500, 2999
N_TEST = 500
OUT = ROOT / "outputs" / "training_subsets" / "heldout_test.json"


def patient_of(name):
    return name.split("-")[0]


def main():
    # presence dicts (which images have Eyelid/Caruncle polygon and Iris+Pupil ellipse)
    eye_labels = defaultdict(set)
    for im in ET.parse(str(EYELID_XML)).getroot().findall("image"):
        nm = Path(im.attrib["name"]).name
        for p in im.findall("polygon"):
            if p.get("label"):
                eye_labels[nm].add(p.get("label"))
    iris_labels = defaultdict(set)
    for im in ET.parse(str(IRIS_XML)).getroot().findall("image"):
        nm = Path(im.attrib["name"]).name
        for e in im.findall("ellipse"):
            if e.get("label"):
                iris_labels[nm].add(e.get("label"))

    imgs = [{"id": int(im.attrib["id"]), "name": im.attrib["name"], "ns": len(list(im)),
             "w": int(float(im.attrib.get("width", 0))), "h": int(float(im.attrib.get("height", 0)))}
            for im in ET.parse(str(EYELID_XML)).getroot().findall("image")]

    min_ann = defaultdict(lambda: 10**9)
    for r in imgs:
        if r["ns"] > 0:
            min_ann[patient_of(r["name"])] = min(min_ann[patient_of(r["name"])], r["id"])
    eligible = {p for p, m in min_ann.items() if m >= TEST_START}

    pool = []
    for r in imgs:
        nm = Path(r["name"]).name
        if not (TEST_START <= r["id"] <= TEST_END) or patient_of(nm) not in eligible:
            continue
        if not (IMAGES_DIR / nm).exists():
            continue
        if (eye_labels[nm] & {"Eyelid", "Caruncle"}) and ("Iris" in iris_labels[nm]) and ("Pupil" in iris_labels[nm]):
            pool.append({"image_id": r["id"], "filename": nm, "patient_id": patient_of(nm),
                         "width": r["w"], "height": r["h"]})

    rng = random.Random(SEED)
    chosen = rng.sample(pool, min(N_TEST, len(pool)))
    chosen.sort(key=lambda r: r["image_id"])

    # verify disjoint from training (largest subset = full training pool)
    subs = json.loads((ROOT / "outputs/training_subsets/subsets.json").read_text(encoding="utf-8"))["subsets"]
    train_imgs = set(subs["2500"]["images"])
    train_pats = set(subs["2500"]["patients"])
    test_imgs = {r["filename"] for r in chosen}
    test_pats = {r["patient_id"] for r in chosen}
    img_overlap = test_imgs & train_imgs
    pat_overlap = test_pats & train_pats

    print(f"eligible test pool: {len(pool)} imgs / {len(eligible)} patients")
    print(f"held-out TEST set:  {len(chosen)} imgs / {len(test_pats)} patients")
    print(f"image overlap with training:   {len(img_overlap)} (must be 0)")
    print(f"patient overlap with training: {len(pat_overlap)} (must be 0)")
    print(f"ALL DISJOINT: {'PASS' if not img_overlap and not pat_overlap else 'FAIL'}")

    OUT.write_text(json.dumps({
        "seed": SEED, "test_start": TEST_START, "n": len(chosen),
        "n_patients": len(test_pats), "eligible_pool": len(pool),
        "images": chosen}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
