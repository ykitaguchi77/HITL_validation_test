"""Score a submitted annotation against ground truth and quantify HITL correction.

All masks are rasterized in the image's native pixel space.
"""
from __future__ import annotations

import cv2
import numpy as np

from config import CLASSES, CLASS_BY_KEY
from geometry import get_gt_annotation, rasterize_class, dice_iou

# Pixel tolerance below which a boundary offset counts as agreement for the
# Boundary-F1 metric (<=2 px matches; >=3 px is a meaningful error). Fixed (not
# scaled by structure size), so it reads more leniently for the small pupil;
# HD95/ASSD are absolute pixel distances and stay interpretable at any size.
BOUNDARY_TOL_PX = 2.0


def _area(mask: np.ndarray) -> int:
    return int((mask > 0).sum())


def _boundary(mask: np.ndarray) -> np.ndarray:
    """1-px inner boundary of a binary mask (morphological gradient)."""
    m = (mask > 0).astype(np.uint8)
    er = cv2.erode(m, np.ones((3, 3), np.uint8))
    return m - er


def boundary_metrics(sub_mask: np.ndarray, gt_mask: np.ndarray,
                     tol: float = BOUNDARY_TOL_PX) -> dict:
    """HD95, ASSD and Boundary-F1@tol between two binary masks.

    Distances are symmetric surface distances in pixels (via a Euclidean
    distance transform to the other mask's boundary). Returns Nones when either
    mask is empty (a boundary distance is undefined then).
    """
    ba, bb = _boundary(sub_mask), _boundary(gt_mask)
    if ba.sum() == 0 or bb.sum() == 0:
        return {"hd95": None, "assd": None, "boundary_f1": None}
    # distanceTransform gives, per pixel, the distance to the nearest zero pixel;
    # feed the boundary's complement so zeros ARE the boundary pixels.
    dt_to_b = cv2.distanceTransform((bb == 0).astype(np.uint8), cv2.DIST_L2, 5)
    dt_to_a = cv2.distanceTransform((ba == 0).astype(np.uint8), cv2.DIST_L2, 5)
    d_ab = dt_to_b[ba > 0]   # submitted boundary -> nearest GT boundary
    d_ba = dt_to_a[bb > 0]   # GT boundary -> nearest submitted boundary
    both = np.concatenate([d_ab, d_ba])
    prec = float((d_ab <= tol).mean())   # submitted pixels within tol of GT
    rec = float((d_ba <= tol).mean())    # GT pixels within tol of submitted
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return {"hd95": float(np.percentile(both, 95)),
            "assd": float(both.mean()),
            "boundary_f1": f1}


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

        # boundary/surface accuracy (all classes): what overlap Dice/IoU misses.
        rec.update(boundary_metrics(sub_mask, gt_mask))

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
