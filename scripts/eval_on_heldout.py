"""Sanity check for leakage: evaluate trained subset models on TRULY held-out
test images (patients with min annotated id >= TEST_START, i.e. test-eligible
patients that never appear in ANY training subset). If the internal-val Dice was
inflated by leakage, these disjoint-patient numbers would drop sharply; if the
task is simply easy + in-distribution, they stay comparable.

GT masks are built identically to training (eyelid = Eyelid∪Caruncle, iris/pupil
full ellipses). Runs on CPU by default to avoid disturbing the training GPU jobs.

Run:  .venv/Scripts/python.exe scripts/eval_on_heldout.py --n 120 \
        --ckpts outputs/models/seg100.pth outputs/models/seg200.pth ...
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "webapp" / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from config import IMAGES_DIR, EYELID_XML, IRIS_XML  # noqa: E402
from train_subset import make_masks, load_polys, load_ellipses, MODEL_NAME, IMAGE_SIZE  # noqa: E402
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor  # noqa: E402

TEST_START, TEST_END = 2500, 2999


def patient_of(name):
    return name.split("-")[0]


def held_out_images(polys, ells, n, seed=42):
    # prefer the fixed held-out set so every model is scored on the identical images
    fixed = ROOT / "outputs/training_subsets/heldout_test.json"
    if fixed.exists():
        data = json.loads(fixed.read_text(encoding="utf-8"))
        names = [r["filename"] for r in data["images"]]
        return (names if n <= 0 else names[:n]), data.get("n_patients", -1)
    # fallback: derive on the fly
    imgs = [{"id": int(im.attrib["id"]), "name": im.attrib["name"], "ns": len(list(im))}
            for im in ET.parse(str(EYELID_XML)).getroot().findall("image")]
    min_ann = defaultdict(lambda: 10**9)
    for r in imgs:
        if r["ns"] > 0:
            min_ann[patient_of(r["name"])] = min(min_ann[patient_of(r["name"])], r["id"])
    eligible = {p for p, m in min_ann.items() if m >= TEST_START}
    pool = []
    for r in imgs:
        if not (TEST_START <= r["id"] <= TEST_END) or patient_of(r["name"]) not in eligible:
            continue
        nm = Path(r["name"]).name
        if not (IMAGES_DIR / nm).exists():
            continue
        labs = {l for l, _ in polys.get(nm, [])}
        elabs = {l for l, *_ in ells.get(nm, [])}
        if ("Eyelid" in labs or "Caruncle" in labs) and "Iris" in elabs and "Pupil" in elabs:
            pool.append(nm)
    random.Random(seed).shuffle(pool)
    return (pool if n <= 0 else pool[:n]), len(eligible)


def dice(pred_bin, gt_bin):
    inter = np.logical_and(pred_bin, gt_bin).sum()
    s = pred_bin.sum() + gt_bin.sum()
    if s == 0:
        return 1.0
    return float(2 * inter / s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpts", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    device = torch.device(args.device)
    polys = load_polys(EYELID_XML)
    ells = load_ellipses(IRIS_XML)
    names, n_elig = held_out_images(polys, ells, args.n)
    pats = sorted({patient_of(n) for n in names})
    print(f"held-out test images: {len(names)} from {len(pats)} eligible patients "
          f"(of {n_elig}); all min-id>={TEST_START}, disjoint from every training subset", flush=True)

    processor = SegformerImageProcessor.from_pretrained(
        MODEL_NAME, do_resize=False, do_rescale=True, do_normalize=True)

    # precompute GT + inputs once
    cache = []
    for nm in names:
        bgr = cv2.imread(str(IMAGES_DIR / nm))
        oh, ow = bgr.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(bgr, (IMAGE_SIZE, IMAGE_SIZE)), cv2.COLOR_BGR2RGB)
        gt = make_masks(nm, oh, ow, polys, ells)
        gt = cv2.resize(gt, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_NEAREST)
        pv = processor(images=rgb, return_tensors="pt")["pixel_values"]
        cache.append((pv, gt > 127))

    print(f"\n{'model':>22} {'eyelid':>8} {'iris':>8} {'pupil':>8} {'mean':>8}", flush=True)
    for ck in args.ckpts:
        ckpt = torch.load(ck, map_location=device)
        model = SegformerForSemanticSegmentation.from_pretrained(
            MODEL_NAME, num_labels=3, ignore_mismatched_sizes=True)
        model.load_state_dict(ckpt["model"])
        model.to(device).eval()
        acc = {0: [], 1: [], 2: []}
        with torch.no_grad():
            for pv, gt in cache:
                logits = model(pixel_values=pv.to(device)).logits
                logits = F.interpolate(logits, size=(IMAGE_SIZE, IMAGE_SIZE),
                                       mode="bilinear", align_corners=False)
                pred = (torch.sigmoid(logits)[0] > 0.5).cpu().numpy()
                for c in range(3):
                    acc[c].append(dice(pred[c], gt[:, :, c]))
        d = [float(np.mean(acc[c])) for c in range(3)]
        m = sum(d) / 3
        tag = Path(ck).stem + f"(ep{ckpt.get('epoch','?')})"
        print(f"{tag:>22} {d[0]:>8.3f} {d[1]:>8.3f} {d[2]:>8.3f} {m:>8.3f}", flush=True)
        del model


if __name__ == "__main__":
    main()
