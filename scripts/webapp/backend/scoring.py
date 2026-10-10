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


# --- ellipse-parameter metrics (iris / pupil) --------------------------------
# Conventions from the iris-localisation / pupillometry literature: centre error
# (px), axis (radius) errors, rotation error of the major axis, plus the axis-
# aligned horizontal / vertical diameters (the vertical iris diameter is the
# occluded, interpreted part of an amodal ellipse).
HVID_MM = 11.7   # mean horizontal visible iris diameter, used as the mm scale


def _ellipse_geom(e: dict) -> dict:
    rx, ry, rot = float(e["rx"]), float(e["ry"]), float(e.get("rotation", 0.0))
    major, minor = max(rx, ry), min(rx, ry)
    th = np.radians(rot if rx >= ry else rot + 90.0)      # orientation of the major axis
    c, s_ = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    return {"cx": float(e["cx"]), "cy": float(e["cy"]), "major": major, "minor": minor,
            "theta_deg": float(np.degrees(th) % 180.0),
            "hdiam": 2.0 * float(np.hypot(rx * c, ry * s_)),   # extent along image x
            "vdiam": 2.0 * float(np.hypot(rx * s_, ry * c))}   # extent along image y


def ellipse_metrics(sub: list, gt: list) -> dict:
    """Parameter errors between the first submitted and the first GT ellipse.
    None-valued when either side has no ellipse."""
    keys = ("center_err", "center_dx", "center_dy", "major_err", "minor_err", "rot_err",
            "hdiam_err", "vdiam_err", "sub_hdiam", "sub_vdiam", "gt_hdiam", "gt_vdiam")
    if not sub or not gt:
        return {k: None for k in keys}
    a, b = _ellipse_geom(sub[0]), _ellipse_geom(gt[0])
    d_th = abs(a["theta_deg"] - b["theta_deg"]) % 180.0
    d_th = min(d_th, 180.0 - d_th)
    return {"center_err": float(np.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])),
            "center_dx": a["cx"] - b["cx"], "center_dy": a["cy"] - b["cy"],
            "major_err": a["major"] - b["major"], "minor_err": a["minor"] - b["minor"],
            "rot_err": float(d_th),
            "hdiam_err": a["hdiam"] - b["hdiam"], "vdiam_err": a["vdiam"] - b["vdiam"],
            "sub_hdiam": a["hdiam"], "sub_vdiam": a["vdiam"], "gt_hdiam": b["hdiam"], "gt_vdiam": b["vdiam"]}


def _lid_margins_at(eyelid_mask: np.ndarray, x: float):
    """(top_y, bottom_y) of the eyelid mask in the column through x, or None."""
    h, w = eyelid_mask.shape
    xi = int(round(x))
    if xi < 0 or xi >= w:
        return None
    col = np.flatnonzero(eyelid_mask[:, xi] > 0)
    return (float(col[0]), float(col[-1])) if len(col) else None


def clinical_indices(eyelid_mask: np.ndarray, pupil: list, mm_per_px: float | None) -> dict:
    """MRD1 / MRD2 / PFH along the vertical through the pupil centre (px, and mm if a scale is given)."""
    out = {"mrd1_px": None, "mrd2_px": None, "pfh_px": None, "mrd1_mm": None, "mrd2_mm": None, "pfh_mm": None}
    if not pupil:
        return out
    cx, cy = float(pupil[0]["cx"]), float(pupil[0]["cy"])
    m = _lid_margins_at(eyelid_mask, cx)
    if m is None:
        return out
    top, bot = m
    out.update({"mrd1_px": cy - top, "mrd2_px": bot - cy, "pfh_px": bot - top})
    if mm_per_px:
        out.update({"mrd1_mm": (cy - top) * mm_per_px, "mrd2_mm": (bot - cy) * mm_per_px,
                    "pfh_mm": (bot - top) * mm_per_px})
    return out


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
        # ellipse parameters (iris / pupil): centre / axis / rotation / diameter errors
        if kind == "ellipse":
            rec.update(ellipse_metrics(submitted.get(key, []), gt.get(key, [])))

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

    # clinical indices (MRD1 / MRD2 / PFH) from eyelid outline + pupil centre; the mm
    # scale comes from the GT iris horizontal diameter (HVID ~ 11.7 mm) for BOTH sides
    # so the comparison is not confounded by the submitted iris size
    gt_iris = gt.get("iris", [])
    mm_per_px = (HVID_MM / _ellipse_geom(gt_iris[0])["hdiam"]) if gt_iris else None
    sub_lid = rasterize_class(submitted.get("eyelid", []), "polygon", h, w)
    gt_lid = rasterize_class(gt.get("eyelid", []), "polygon", h, w)
    clin_sub = clinical_indices(sub_lid, submitted.get("pupil", []), mm_per_px)
    clin_gt = clinical_indices(gt_lid, gt.get("pupil", []), mm_per_px)
    clinical = {"hvid_px_gt": _ellipse_geom(gt_iris[0])["hdiam"] if gt_iris else None,
                "mm_per_px": mm_per_px}
    for k in ("mrd1", "mrd2", "pfh"):
        clinical[f"{k}_px"] = clin_sub[f"{k}_px"]
        clinical[f"{k}_mm"] = clin_sub[f"{k}_mm"]
        clinical[f"{k}_gt_mm"] = clin_gt[f"{k}_mm"]
        clinical[f"{k}_err_mm"] = (clin_sub[f"{k}_mm"] - clin_gt[f"{k}_mm"]
                                   if clin_sub[f"{k}_mm"] is not None and clin_gt[f"{k}_mm"] is not None else None)

    return {
        "per_class": per_class,
        "mean_dice": float(np.mean(dices)) if dices else 1.0,
        "mean_iou": float(np.mean(ious)) if ious else 1.0,
        "native_size": [w, h],
        "clinical": clinical,
    }
