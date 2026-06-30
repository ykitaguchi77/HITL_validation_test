"""Session result persistence: per-image JSON records + a flat CSV summary."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from config import RESULTS_DIR, CLASSES

# CSV columns (one row per submitted image)
_BASE_COLS = [
    "session_id", "annotator", "attempt", "timestamp",
    "session_key", "session_index", "condition", "model", "train_size", "is_hitl",
    "is_practice", "block", "gaze", "ecc", "order_in_session",
    "phase", "image_id", "filename",
    "duration_sec", "total_clicks", "mouse_distance_px",
    "vertices_added", "vertices_moved", "vertices_deleted",
    "shapes_created", "shapes_deleted", "undo_count", "redo_count",
    "zoom_count", "pan_count", "mean_dice", "mean_iou",
]


def _per_class_cols() -> list[str]:
    cols = []
    for c in CLASSES:
        k = c["key"]
        cols += [f"{k}_dice", f"{k}_iou", f"{k}_clicks", f"{k}_time_sec",
                 f"{k}_vertices_edited", f"{k}_correction_dice", f"{k}_area_change",
                 f"{k}_gt_present", f"{k}_submitted_present"]
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


def _flatten(record: dict) -> dict:
    m = record.get("metrics", {})
    s = record.get("scores", {})
    pc = s.get("per_class", {})
    pcm = m.get("per_class", {})
    row = {
        "session_id": record.get("session_id"),
        "annotator": record.get("annotator"),
        "attempt": record.get("attempt"),
        "timestamp": record.get("timestamp"),
        "session_key": record.get("session_key"),
        "session_index": record.get("session_index"),
        "condition": record.get("condition"),
        "model": record.get("model"),
        "train_size": record.get("train_size"),
        "is_hitl": record.get("is_hitl"),
        "is_practice": record.get("is_practice"),
        "block": record.get("block"),
        "gaze": record.get("gaze"),
        "ecc": record.get("ecc"),
        "order_in_session": record.get("order_in_session"),
        "phase": record.get("phase"),
        "image_id": record.get("image_id"),
        "filename": record.get("filename"),
        "duration_sec": m.get("duration_sec"),
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
    for c in CLASSES:
        k = c["key"]
        cs = pc.get(k, {})
        cm = pcm.get(k, {})
        row[f"{k}_dice"] = cs.get("dice")
        row[f"{k}_iou"] = cs.get("iou")
        row[f"{k}_clicks"] = cm.get("clicks")
        row[f"{k}_time_sec"] = cm.get("time_sec")
        row[f"{k}_vertices_edited"] = cm.get("vertices_edited")
        row[f"{k}_correction_dice"] = cs.get("correction_dice")
        row[f"{k}_area_change"] = cs.get("area_change")
        row[f"{k}_gt_present"] = cs.get("gt_present")
        row[f"{k}_submitted_present"] = cs.get("submitted_present")
    return row
