"""Geometry helpers: CVAT XML parsing, vector<->mask conversion, rasterization.

Coordinate convention: everything is in the **image's native pixel space**
(the displayed image's own resolution). Polygons are lists of [x, y] points;
ellipses (OBB) are {cx, cy, rx, ry, rotation_deg}.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Optional

import cv2
import numpy as np

from config import EYELID_XML, IRIS_XML, XML_LABEL_TO_KEY, CLASS_BY_KEY


# --- CVAT XML parsing ------------------------------------------------------
def _parse_points(s: str) -> list[list[float]]:
    return [[float(v) for v in pt.split(",")] for pt in s.strip().split(";") if pt]


@lru_cache(maxsize=2)
def _index_xml(xml_path: str) -> dict:
    """name -> {'size': (w, h), 'shapes': [(key, kind, data), ...]}"""
    tree = ET.parse(xml_path)
    index: dict[str, dict] = {}
    for im in tree.getroot().findall("image"):
        name = im.attrib["name"]
        w = int(float(im.attrib.get("width", 0)))
        h = int(float(im.attrib.get("height", 0)))
        shapes = []
        for ch in im:
            label = ch.attrib.get("label")
            key = XML_LABEL_TO_KEY.get(label)
            if key is None:
                continue
            if ch.tag == "polygon":
                shapes.append((key, "polygon", _parse_points(ch.attrib["points"])))
            elif ch.tag == "ellipse":
                a = ch.attrib
                shapes.append((key, "ellipse", {
                    "cx": float(a["cx"]), "cy": float(a["cy"]),
                    "rx": float(a["rx"]), "ry": float(a["ry"]),
                    "rotation": float(a.get("rotation", 0.0)),
                }))
        index[name] = {"size": (w, h), "shapes": shapes}
    return index


def get_gt_annotation(image_name: str) -> dict:
    """Return ground-truth shapes for an image grouped by class key.

    {'eyelid':[poly,...], 'caruncle':[poly,...], 'iris':[ellipse], 'pupil':[ellipse], 'size':(w,h)}
    """
    out: dict = {k: [] for k in CLASS_BY_KEY}
    size = None
    for xml_path, want in ((str(EYELID_XML), {"eyelid"}),   # Eyelid+Caruncle both -> eyelid
                           (str(IRIS_XML), {"iris", "pupil"})):
        entry = _index_xml(xml_path).get(image_name)
        if not entry:
            continue
        if size is None and entry["size"][0]:
            size = entry["size"]
        for key, kind, data in entry["shapes"]:
            if key in want:
                out[key].append(data)
    out["size"] = size
    return out


# --- Rasterization (vector -> binary mask) ---------------------------------
def rasterize_class(shapes: list, kind: str, h: int, w: int) -> np.ndarray:
    """Rasterize a list of shapes of one class to a uint8 {0,255} mask."""
    mask = np.zeros((h, w), dtype=np.uint8)
    for s in shapes:
        if kind == "polygon":
            pts = np.asarray(s, dtype=np.int32).reshape(-1, 1, 2)
            if len(pts) >= 3:
                cv2.fillPoly(mask, [pts], 255)
        else:  # ellipse OBB
            cv2.ellipse(
                mask,
                (int(round(s["cx"])), int(round(s["cy"]))),
                (max(1, int(round(s["rx"]))), max(1, int(round(s["ry"])))),
                float(s.get("rotation", 0.0)), 0, 360, 255, -1,
            )
    return mask


def rasterize_annotation(ann: dict, h: int, w: int) -> dict[str, np.ndarray]:
    """ann: {class_key: [shapes...]} -> {class_key: mask}."""
    out = {}
    for key, cls in CLASS_BY_KEY.items():
        out[key] = rasterize_class(ann.get(key, []), cls["kind"], h, w)
    return out


# --- Mask -> vector (for HITL initial annotations) -------------------------
def mask_to_polygon(mask: np.ndarray, max_points: int = 120, min_area: int = 80,
                    spacing: float = 14.0) -> Optional[list[list[float]]]:
    """Largest external contour -> polygon with EVENLY spaced points (one every
    ~`spacing` px of contour length). Even spacing (rather than curvature-based
    approxPolyDP) gives a uniform, denser outline that is easier for the HITL
    annotator to correct. None if empty."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) >= min_area]
    if not cnts:
        return None
    pts = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(float)
    if len(pts) < 3:
        return None
    closed = np.vstack([pts, pts[:1]])                 # close the loop
    seg = np.sqrt((np.diff(closed, axis=0) ** 2).sum(1))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total <= 0:
        return pts.tolist()
    n = int(np.clip(round(total / spacing), 24, max_points))
    targets = np.linspace(0.0, total, n, endpoint=False)
    idx = np.clip(np.searchsorted(cum, targets, side="right") - 1, 0, len(seg) - 1)
    f = (targets - cum[idx]) / np.where(seg[idx] > 0, seg[idx], 1.0)
    out = closed[idx] * (1 - f)[:, None] + closed[idx + 1] * f[:, None]
    return out.astype(float).tolist()


def mask_to_ellipse(mask: np.ndarray, min_area: int = 80) -> Optional[dict]:
    """Largest contour -> fitted OBB ellipse {cx,cy,rx,ry,rotation}. None if empty."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) >= min_area and len(c) >= 5]
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    (cx, cy), (maj, minr), angle = cv2.fitEllipse(cnt)
    return {"cx": float(cx), "cy": float(cy),
            "rx": float(maj) / 2.0, "ry": float(minr) / 2.0,
            "rotation": float(angle)}


# --- Dice / IoU ------------------------------------------------------------
def dice_iou(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Dice and IoU between two {0,255} (or bool) masks.

    Both empty -> (1.0, 1.0) (correctly agreeing on absence). One empty -> 0.
    """
    a = a.astype(bool)
    b = b.astype(bool)
    inter = np.logical_and(a, b).sum()
    sa, sb = a.sum(), b.sum()
    if sa == 0 and sb == 0:
        return 1.0, 1.0
    union = sa + sb - inter
    dice = (2.0 * inter) / (sa + sb) if (sa + sb) else 0.0
    iou = inter / union if union else 0.0
    return float(dice), float(iou)
