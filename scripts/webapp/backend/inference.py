"""SegFormer-B1 amodal inference -> initial HITL vector annotations.

Loads a checkpoint (cached per path), runs the 3-channel amodal forward pass on
a 512x512 RGB crop, then converts the eyelid/iris/pupil masks back to native
image coordinates as editable polygons / OBB ellipses. Caruncle has no model
channel, so it is never pre-filled (annotator draws it manually).
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

from config import INFER_SIZE, SEGFORMER_BACKBONE
from geometry import mask_to_polygon, mask_to_ellipse

CHANNELS = ["eyelid", "iris", "pupil"]   # model output channel order
_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


@lru_cache(maxsize=9)   # 8 subset models + headroom; avoids reload thrash in interleaved sessions
def _load(checkpoint_path: str, backbone: str):
    model = SegformerForSemanticSegmentation.from_pretrained(
        backbone, num_labels=3, ignore_mismatched_sizes=True
    ).to(_DEVICE)
    try:
        ckpt = torch.load(checkpoint_path, map_location=_DEVICE, weights_only=False)
    except TypeError:  # older torch without weights_only kwarg
        ckpt = torch.load(checkpoint_path, map_location=_DEVICE)
    state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state)
    model.eval()
    processor = SegformerImageProcessor.from_pretrained(
        backbone, do_resize=False, do_rescale=True, do_normalize=True
    )
    return model, processor


@torch.no_grad()
def _predict_masks(image_path: str, checkpoint_path: str, backbone: str,
                   threshold: float = 0.5) -> dict[str, np.ndarray]:
    """Return {channel: 512x512 uint8 {0,255} mask}."""
    model, processor = _load(checkpoint_path, backbone)
    bgr = cv2.imread(image_path)
    if bgr is None:
        raise FileNotFoundError(image_path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (INFER_SIZE, INFER_SIZE), interpolation=cv2.INTER_LINEAR)
    pixel_values = processor(images=rgb, return_tensors="pt")["pixel_values"].to(_DEVICE)
    logits = model(pixel_values=pixel_values).logits
    logits = F.interpolate(logits, size=(INFER_SIZE, INFER_SIZE),
                           mode="bilinear", align_corners=False)
    probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()
    return {name: ((probs[c] > threshold) * 255).astype(np.uint8)
            for c, name in enumerate(CHANNELS)}


def predict_initial_shapes(image_path: str, checkpoint_path: str,
                           native_w: int, native_h: int,
                           backbone: str = SEGFORMER_BACKBONE) -> dict:
    """HITL initial annotation in NATIVE image coords.

    Returns {'eyelid':[poly], 'caruncle':[], 'iris':[ellipse], 'pupil':[ellipse]}.
    Polygon = [[x,y],...]; ellipse = {cx,cy,rx,ry,rotation}.
    """
    masks = _predict_masks(image_path, checkpoint_path, backbone)
    sx, sy = native_w / INFER_SIZE, native_h / INFER_SIZE
    out: dict = {"eyelid": [], "caruncle": [], "iris": [], "pupil": []}

    # eyelid -> polygon (rescale points to native)
    poly = mask_to_polygon(masks["eyelid"])
    if poly:
        out["eyelid"].append([[x * sx, y * sy] for x, y in poly])

    # iris / pupil -> OBB ellipse (rescale; native is near-square so use mean scale for radii)
    s_mean = (sx + sy) / 2.0
    for name in ("iris", "pupil"):
        el = mask_to_ellipse(masks[name])
        if el:
            out[name].append({
                "cx": el["cx"] * sx, "cy": el["cy"] * sy,
                "rx": el["rx"] * s_mean, "ry": el["ry"] * s_mean,
                "rotation": el["rotation"],
            })
    return out
