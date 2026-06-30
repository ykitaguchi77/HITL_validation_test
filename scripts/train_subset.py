"""Train one SegFormer-B1 amodal model on a patient-safe training subset.

Faithful port of the proven `train_SegFormerB1_Amodal_Blur_v3` notebook pipeline
(3-channel amodal masks: eyelid=Eyelid+Caruncle union / iris / pupil full ellipse;
v3 enhanced-blur augmentation; per-channel Tversky + pupil-in-iris constraint loss;
AdamW 6e-5; AMP; early stop on mean val Dice), restricted to the image list of one
subset from outputs/training_subsets/subsets.json. The subset is split train/val by
patient (no leakage), and the subset itself is already patient-disjoint from the
held-out test set (see make_training_subsets.py).

Run (inside the venv):
  .venv/Scripts/python.exe scripts/train_subset.py --subset 500 \
      --out outputs/models/seg500.pth --epochs 300 --patience 20
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset
import albumentations as A
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "webapp" / "backend"))
from config import IMAGES_DIR, EYELID_XML, IRIS_XML, SEGFORMER_BACKBONE  # noqa: E402

IMAGE_SIZE = 512
SEED = 42
VAL_RATIO = 0.2
BATCH_SIZE = 8
LEARNING_RATE = 6e-5
WEIGHT_DECAY = 0.01
ELLIPSE_N = 100
CHANNEL_WEIGHTS = [1.0, 1.2, 3.0]
TVERSKY = {"eyelid": (0.5, 0.5), "iris": (0.4, 0.6), "pupil": (0.3, 0.7)}
CONSTRAINT_WEIGHT = 0.1
MODEL_NAME = SEGFORMER_BACKBONE  # nvidia/segformer-b1-finetuned-ade-512-512


# --- XML parsing (eyelid polygons + iris/pupil ellipses) -------------------
def _parse_points(s):
    return [(float(x), float(y)) for x, y in
            (t.split(",") for t in s.strip().split(";") if t.strip())]


def _ellipse_pts(cx, cy, rx, ry, rot_deg, n=ELLIPSE_N):
    th = math.radians(rot_deg % 360.0)
    ct, st = math.cos(th), math.sin(th)
    out = []
    for i in range(n):
        a = 2 * math.pi * (i / n)
        x0, y0 = rx * math.cos(a), ry * math.sin(a)
        out.append((cx + x0 * ct - y0 * st, cy + x0 * st + y0 * ct))
    return out


def load_polys(xml_path):
    out = {}
    for img in ET.parse(str(xml_path)).getroot().findall("image"):
        name = Path(img.get("name")).name
        items = [(p.get("label"), _parse_points(p.get("points")))
                 for p in img.findall("polygon") if p.get("label") and p.get("points")]
        if items:
            out[name] = items
    return out


def load_ellipses(xml_path):
    out = {}
    for img in ET.parse(str(xml_path)).getroot().findall("image"):
        name = Path(img.get("name")).name
        items = []
        for el in img.findall("ellipse"):
            lab = el.get("label")
            if not lab:
                continue
            try:
                items.append((lab, float(el.get("cx")), float(el.get("cy")),
                              float(el.get("rx")), float(el.get("ry")),
                              float(el.get("rotation") or 0.0)))
            except Exception:
                continue
        if items:
            out[name] = items
    return out


def make_masks(name, h, w, polys, ells):
    eyelid = np.zeros((h, w), np.uint8); iris = np.zeros((h, w), np.uint8); pupil = np.zeros((h, w), np.uint8)
    for label, pts in polys.get(name, []):
        if label in ("Eyelid", "Caruncle"):
            cv2.fillPoly(eyelid, [np.round(np.array(pts, np.float32)).astype(np.int32)], 255)
    for label, cx, cy, rx, ry, rot in ells.get(name, []):
        p = np.round(np.array(_ellipse_pts(cx, cy, rx, ry, rot), np.float32)).astype(np.int32)
        if label == "Iris":
            cv2.fillPoly(iris, [p], 255)
        elif label == "Pupil":
            cv2.fillPoly(pupil, [p], 255)
    return np.stack([eyelid, iris, pupil], axis=-1)


# --- v3 enhanced-blur augmentation (image+mask geometric, image-only photo) -
def build_aug():
    return A.Compose([
        A.RandomResizedCrop(size=(IMAGE_SIZE, IMAGE_SIZE), scale=(0.8, 1.0), ratio=(0.9, 1.1),
                            interpolation=cv2.INTER_LINEAR, p=0.5),
        A.Rotate(limit=180, interpolation=cv2.INTER_LINEAR, border_mode=cv2.BORDER_CONSTANT, p=1.0),
        A.OneOf([
            A.RandomBrightnessContrast(brightness_limit=0.25, contrast_limit=0.25, p=1.0),
            A.RandomGamma(gamma_limit=(70, 140), p=1.0),
            A.Compose([A.RandomBrightnessContrast(brightness_limit=0.125, contrast_limit=0.125, p=1.0),
                       A.RandomGamma(gamma_limit=(80, 120), p=1.0)]),
        ], p=0.5),
        A.OneOf([
            A.Blur(blur_limit=(7, 15), p=1.0),
            A.MotionBlur(blur_limit=(7, 21), p=1.0),
            A.GaussianBlur(blur_limit=(7, 15), sigma_limit=(1.5, 5.0), p=1.0),
            A.Downscale(scale_range=(0.15, 0.35), p=1.0),
            A.Downscale(scale_range=(0.0625, 0.125), p=1.0),
            A.Defocus(radius=(5, 10), alias_blur=(0.1, 0.5), p=1.0),
            A.ZoomBlur(max_factor=(1.1, 1.3), p=1.0),
        ], p=0.6),
        A.ImageCompression(quality_range=(20, 70), p=0.4),
        A.OneOf([A.GaussNoise(std_range=(10 / 255, 50 / 255), p=1.0),
                 A.ISONoise(intensity=(0.1, 0.5), p=1.0)], p=0.4),
    ])


class EyeDataset(Dataset):
    def __init__(self, names, polys, ells, processor, augment=False):
        self.names = names; self.polys = polys; self.ells = ells
        self.processor = processor
        self.aug = build_aug() if augment else None

    def __len__(self):
        return len(self.names)

    def __getitem__(self, idx):
        name = self.names[idx]
        img = cv2.imread(str(IMAGES_DIR / name))
        oh, ow = img.shape[:2]
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_LINEAR)
        masks = make_masks(name, oh, ow, self.polys, self.ells)
        masks = cv2.resize(masks, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_NEAREST)
        if self.aug is not None:
            a = self.aug(image=img, mask=masks); img, masks = a["image"], a["mask"]
        pixel_values = self.processor(images=img, return_tensors="pt")["pixel_values"].squeeze(0)
        labels = torch.from_numpy(masks).permute(2, 0, 1).float() / 255.0
        return {"pixel_values": pixel_values, "labels": labels}


class BalancedConstrainedLoss(nn.Module):
    names = ["eyelid", "iris", "pupil"]

    def __init__(self):
        super().__init__()

    @staticmethod
    def _tversky(pred, target, alpha, beta, smooth=1e-6):
        TP = (pred * target).sum(dim=(1, 2))
        FP = (pred * (1 - target)).sum(dim=(1, 2))
        FN = ((1 - pred) * target).sum(dim=(1, 2))
        return 1 - ((TP + smooth) / (TP + alpha * FP + beta * FN + smooth)).mean()

    def forward(self, logits, targets):
        if logits.shape[-2:] != targets.shape[-2:]:
            logits = F.interpolate(logits, size=targets.shape[-2:], mode="bilinear", align_corners=False)
        probs = torch.sigmoid(logits)
        wsum = sum(CHANNEL_WEIGHTS); wloss = 0.0; ch = {}
        for c, nm in enumerate(self.names):
            a, b = TVERSKY[nm]
            l = self._tversky(probs[:, c], targets[:, c], a, b)
            ch[nm] = l.item(); wloss = wloss + CHANNEL_WEIGHTS[c] * l
        main = wloss / wsum
        constraint = (probs[:, 2] * (1 - probs[:, 1])).mean()
        total = main + CONSTRAINT_WEIGHT * constraint
        ch["total"] = total.item()
        return total, ch


def dice_batch(pred, target, thr=0.5):
    pb = (pred > thr).float()
    inter = (pb * target).sum(dim=(1, 2))
    union = pb.sum(dim=(1, 2)) + target.sum(dim=(1, 2))
    return ((2 * inter + 1e-6) / (union + 1e-6)).mean().item()


def subject(name):
    return name.split("-", 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--max-minutes", type=float, default=0.0, help="0 = no time cap")
    ap.add_argument("--limit", type=int, default=0, help="debug: cap #images (0=all)")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    subs = json.loads((ROOT / "outputs/training_subsets/subsets.json").read_text(encoding="utf-8"))
    names = subs["subsets"][str(args.subset)]["images"]
    if args.limit:
        names = names[:args.limit]

    # patient-grouped train/val split of the subset
    subjects = sorted({subject(n) for n in names})
    random.Random(SEED).shuffle(subjects)
    val_subj = set(subjects[:max(1, int(len(subjects) * VAL_RATIO))])
    train_names = [n for n in names if subject(n) not in val_subj]
    val_names = [n for n in names if subject(n) in val_subj]
    assert not ({subject(n) for n in train_names} & {subject(n) for n in val_names}), "val leak!"

    polys = load_polys(EYELID_XML); ells = load_ellipses(IRIS_XML)
    processor = SegformerImageProcessor.from_pretrained(
        MODEL_NAME, do_resize=False, do_rescale=True, do_normalize=True)
    train_ds = EyeDataset(train_names, polys, ells, processor, augment=True)
    val_ds = EyeDataset(val_names, polys, ells, processor, augment=False)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True)

    print(f"[subset {args.subset}] images={len(names)} train={len(train_names)} val={len(val_names)} "
          f"subjects={len(subjects)} (val {len(val_subj)}) device={device}", flush=True)

    model = SegformerForSemanticSegmentation.from_pretrained(
        MODEL_NAME, num_labels=3, ignore_mismatched_sizes=True).to(device)
    criterion = BalancedConstrainedLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scaler = GradScaler("cuda")

    best_mean, best_epoch, patience = 0.0, 0, 0
    t0 = time.time()
    out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        for batch in train_loader:
            pv = batch["pixel_values"].to(device); lb = batch["labels"].to(device)
            optimizer.zero_grad()
            with autocast("cuda"):
                logits = model(pixel_values=pv).logits
                loss, _ = criterion(logits, lb)
            scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update()

        model.eval(); dsum = {"eyelid": 0, "iris": 0, "pupil": 0}; nb = 0
        with torch.no_grad():
            for batch in val_loader:
                pv = batch["pixel_values"].to(device); lb = batch["labels"].to(device)
                logits = model(pixel_values=pv).logits
                if logits.shape[-2:] != lb.shape[-2:]:
                    logits = F.interpolate(logits, size=lb.shape[-2:], mode="bilinear", align_corners=False)
                probs = torch.sigmoid(logits)
                for c, nm in enumerate(["eyelid", "iris", "pupil"]):
                    dsum[nm] += dice_batch(probs[:, c], lb[:, c])
                nb += 1
        dice = {k: v / nb for k, v in dsum.items()}; dice["mean"] = sum(dice.values()) / 3
        improved = dice["mean"] > best_mean
        if improved:
            best_mean, best_epoch, patience = dice["mean"], epoch, 0
            torch.save({"epoch": epoch, "model": model.state_dict(),
                        "val_dice": dice, "subset": int(args.subset),
                        "n_images": len(names), "n_train": len(train_names), "n_val": len(val_names),
                        "backbone": MODEL_NAME}, out_path)
        else:
            patience += 1
        mins = (time.time() - t0) / 60
        print(f"  ep{epoch:>3} D_eyelid={dice['eyelid']:.3f} D_iris={dice['iris']:.3f} "
              f"D_pupil={dice['pupil']:.3f} D_mean={dice['mean']:.3f} "
              f"{'*SAVED*' if improved else f'p={patience}/{args.patience}'} [{mins:.1f}m]", flush=True)
        if patience >= args.patience:
            print(f"  early stop (best ep{best_epoch} mean={best_mean:.3f})", flush=True); break
        if args.max_minutes and mins >= args.max_minutes:
            print(f"  time cap {args.max_minutes}m reached (best ep{best_epoch} mean={best_mean:.3f})", flush=True); break

    print(f"[subset {args.subset}] DONE best_mean={best_mean:.4f} @ep{best_epoch} -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
