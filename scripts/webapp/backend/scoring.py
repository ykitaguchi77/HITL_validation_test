"""Score a submitted annotation against ground truth and quantify HITL correction.

All masks are rasterized in the image's native pixel space.
"""
from __future__ import annotations

import numpy as np

from config import CLASSES, CLASS_BY_KEY
from geometry import get_gt_annotation, rasterize_class, dice_iou


def _area(mask: np.ndarray) -> int:
    return int((mask > 0).sum())


def score_annotation(image_name: str, submitted: dict, native_w: int, native_h: int,
                     initial: dict | None = None) -> dict:
    """Compute per-class quality (vs GT) and correction (vs model initial).

    submitted / initial: {class_key: [shapes...]} in native coords.
    Returns a dict with per-class metrics and aggregate mean Dice/IoU.
    """
    h = native_h or (get_gt_annotation(image_name).get("size") or (native_w, native_w))[1]
    w = native_w or h
    gt = get_gt_annotation(image_name)

    per_class = {}
    dices, ious = [], []
    for cls in CLASSES:
        key, kind = cls["key"], cls["kind"]
        sub_mask = rasterize_class(submitted.get(key, []), kind, h, w)
        gt_mask = rasterize_class(gt.get(key, []), kind, h, w)
        dice, iou = dice_iou(sub_mask, gt_mask)

        rec = {
            "dice": dice, "iou": iou,
            "gt_present": _area(gt_mask) > 0,
            "submitted_present": _area(sub_mask) > 0,
            "submitted_area": _area(sub_mask),
            "gt_area": _area(gt_mask),
            "n_submitted_shapes": len(submitted.get(key, [])),
        }

        # HITL correction: how far the final moved from the model's initial prediction.
        if initial is not None:
            init_mask = rasterize_class(initial.get(key, []), kind, h, w)
            init_dice, init_iou = dice_iou(sub_mask, init_mask)
            rec["initial_present"] = _area(init_mask) > 0
            rec["initial_area"] = _area(init_mask)
            rec["correction_dice"] = init_dice   # 1.0 = untouched, lower = more edited
            rec["correction_iou"] = init_iou
            rec["area_change"] = _area(sub_mask) - _area(init_mask)

        per_class[key] = rec
        # aggregate only over classes that exist in GT or submission
        if rec["gt_present"] or rec["submitted_present"]:
            dices.append(dice)
            ious.append(iou)

    return {
        "per_class": per_class,
        "mean_dice": float(np.mean(dices)) if dices else 1.0,
        "mean_iou": float(np.mean(ious)) if ious else 1.0,
        "native_size": [w, h],
    }
