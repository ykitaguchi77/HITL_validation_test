"""Session result persistence: per-image JSON records + a flat CSV summary."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from config import RESULTS_DIR, CLASSES

# CSV columns (one row per submitted image)
_BASE_COLS = [
    "session_id", "annotator", "attempt", "timestamp",
    "session_key", "session_index", "condition", "model", "n", "seed", "train_size",
    "proposal_key", "is_hitl", "is_practice", "group", "gaze", "ecc", "order_in_session",
    "image_id", "filename",
    "duration_sec", "paused_time_sec", "time_to_first_action_sec", "idle_time_sec", "effort",
    "total_clicks", "mouse_distance_px",
    "vertices_added", "vertices_moved", "vertices_deleted",
    "shapes_created", "shapes_deleted", "undo_count", "redo_count",
    "zoom_count", "pan_count", "mean_dice", "mean_iou",
    # clinical indices (eyelid outline + pupil centre; mm via GT iris HVID = 11.7 mm)
    "hvid_px_gt", "mrd1_mm", "mrd2_mm", "pfh_mm", "mrd1_gt_mm", "mrd2_gt_mm", "pfh_gt_mm",
    "mrd1_err_mm", "mrd2_err_mm", "pfh_err_mm",
]
_ELLIPSE_KEYS = ["center_err", "center_dx", "center_dy", "major_err", "minor_err", "rot_err",
                 "hdiam_err", "vdiam_err"]


def _per_class_cols() -> list[str]:
    cols = []
    for c in CLASSES:
        k = c["key"]
        cols += [f"{k}_dice", f"{k}_iou", f"{k}_hd95", f"{k}_assd", f"{k}_boundary_f1",
                 f"{k}_clicks", f"{k}_time_sec",
                 f"{k}_vertices_edited", f"{k}_vertices_added", f"{k}_vertices_moved",
                 f"{k}_vertices_deleted", f"{k}_shapes_created", f"{k}_shapes_deleted",
                 f"{k}_correction_dice", f"{k}_area_change",
                 f"{k}_gt_present", f"{k}_submitted_present",
                 # precomputed proposal-vs-GT quality (what the annotator was shown)
                 f"{k}_prop_dice", f"{k}_prop_assd", f"{k}_prop_hd95", f"{k}_prop_bf1",
                 f"{k}_prop_area_diff", f"{k}_prop_present"]
        if c["kind"] == "ellipse":
            cols += [f"{k}_{e}" for e in _ELLIPSE_KEYS] + [f"{k}_prop_center_err", f"{k}_prop_major_err"]
    return cols


CSV_COLS = _BASE_COLS + _per_class_cols()


def session_dir(session_id: str) -> Path:
    d = RESULTS_DIR / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_record(session_id: str, record: dict) -> None:
    """Append one image record to the session's JSONL and CSV summary."""
    d = session_dir(session_id)

    # 1) full record -> JSONL (lossless: geometry, metrics, scores)
    with open(d / "records.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 2) flat row -> summary.csv
    row = _flatten(record)
    csv_path = d / "summary.csv"
    write_header = not csv_path.exists()
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerow(row)


def completed_attempts(annotator: str, n_images: dict[str, int]) -> dict[str, int]:
    """Completed attempts per session_key for one annotator, read from the saved
    records (server-side truth, independent of browser/PC). A session folder counts
    as completed once it holds records for all n_images[key] distinct images."""
    done: dict[str, int] = {}
    if not RESULTS_DIR.is_dir():
        return done
    for d in RESULTS_DIR.glob(f"{annotator}_*"):
        f = d / "records.jsonl"
        if not f.is_file():
            continue
        key, imgs = None, set()
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("annotator") != annotator:
                    continue
                key = r.get("session_key")
                imgs.add(r.get("image_id"))
        if key in n_images and len(imgs) >= n_images[key]:
            done[key] = done.get(key, 0) + 1
    return done


def _flatten(record: dict) -> dict:
    m = record.get("metrics", {})
    s = record.get("scores", {})
    pc = s.get("per_class", {})
    pcm = m.get("per_class", {})
    ppm = (record.get("proposal_metrics") or {})
    row = {
        "session_id": record.get("session_id"),
        "annotator": record.get("annotator"),
        "attempt": record.get("attempt"),
        "timestamp": record.get("timestamp"),
        "session_key": record.get("session_key"),
        "session_index": record.get("session_index"),
        "condition": record.get("condition"),
        "model": record.get("model"),
        "n": record.get("n"),
        "seed": record.get("seed"),
        "train_size": record.get("train_size"),
        "proposal_key": record.get("proposal_key"),
        "is_hitl": record.get("is_hitl"),
        "is_practice": record.get("is_practice"),
        "group": record.get("group"),
        "gaze": record.get("gaze"),
        "ecc": record.get("ecc"),
        "order_in_session": record.get("order_in_session"),
        "image_id": record.get("image_id"),
        "filename": record.get("filename"),
        "duration_sec": m.get("duration_sec"),
        "paused_time_sec": m.get("paused_time_sec"),
        "time_to_first_action_sec": m.get("time_to_first_action_sec"),
        "idle_time_sec": m.get("idle_time_sec"),
        "effort": record.get("effort"),
        "total_clicks": m.get("total_clicks"),
        "mouse_distance_px": m.get("mouse_distance_px"),
        "vertices_added": m.get("vertices_added"),
        "vertices_moved": m.get("vertices_moved"),
        "vertices_deleted": m.get("vertices_deleted"),
        "shapes_created": m.get("shapes_created"),
        "shapes_deleted": m.get("shapes_deleted"),
        "undo_count": m.get("undo_count"),
        "redo_count": m.get("redo_count"),
        "zoom_count": m.get("zoom_count"),
        "pan_count": m.get("pan_count"),
        "mean_dice": s.get("mean_dice"),
        "mean_iou": s.get("mean_iou"),
    }
    clin = s.get("clinical") or {}
    for f in ("hvid_px_gt", "mrd1_mm", "mrd2_mm", "pfh_mm", "mrd1_gt_mm", "mrd2_gt_mm", "pfh_gt_mm",
              "mrd1_err_mm", "mrd2_err_mm", "pfh_err_mm"):
        row[f] = clin.get(f)
    for c in CLASSES:
        k = c["key"]
        cs = pc.get(k, {})
        cm = pcm.get(k, {})
        row[f"{k}_dice"] = cs.get("dice")
        row[f"{k}_iou"] = cs.get("iou")
        row[f"{k}_hd95"] = cs.get("hd95")
        row[f"{k}_assd"] = cs.get("assd")
        row[f"{k}_boundary_f1"] = cs.get("boundary_f1")
        row[f"{k}_clicks"] = cm.get("clicks")
        row[f"{k}_time_sec"] = cm.get("time_sec")
        row[f"{k}_vertices_edited"] = cm.get("vertices_edited")
        for f in ("vertices_added", "vertices_moved", "vertices_deleted",
                  "shapes_created", "shapes_deleted"):
            row[f"{k}_{f}"] = cm.get(f)
        row[f"{k}_correction_dice"] = cs.get("correction_dice")
        row[f"{k}_area_change"] = cs.get("area_change")
        row[f"{k}_gt_present"] = cs.get("gt_present")
        row[f"{k}_submitted_present"] = cs.get("submitted_present")
        pm = ppm.get(k) or {}
        row[f"{k}_prop_dice"] = pm.get("dice")
        row[f"{k}_prop_assd"] = pm.get("assd")
        row[f"{k}_prop_hd95"] = pm.get("hd95")
        row[f"{k}_prop_bf1"] = pm.get("boundary_f1")
        row[f"{k}_prop_area_diff"] = pm.get("area_diff")
        row[f"{k}_prop_present"] = pm.get("submitted_present")
        if c["kind"] == "ellipse":
            for e in _ELLIPSE_KEYS:
                row[f"{k}_{e}"] = cs.get(e)
            row[f"{k}_prop_center_err"] = pm.get("center_err")
            row[f"{k}_prop_major_err"] = pm.get("major_err")
    return row
