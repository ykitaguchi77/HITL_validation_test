"""Recompute every quality metric from the stored geometry (records.jsonl) with the
CURRENT scoring code, and write summary_rescored.csv next to each summary.csv.

Use when scoring.py gains metrics after some sessions were recorded (e.g. the
ellipse-parameter / MRD metrics added 2026-09-20): behaviour metrics (times,
clicks, vertex counts) are copied from the record; GT comparisons are recomputed.

Run:  python scripts/analysis/rescore_records.py [--results outputs/results] [--glob "test_s0*"]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "webapp" / "backend"))
from scoring import score_annotation  # noqa: E402
from session import CSV_COLS, _flatten  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "outputs" / "results"))
    ap.add_argument("--glob", default="*")
    args = ap.parse_args()
    n_dirs = 0
    for d in sorted(Path(args.results).glob(args.glob)):
        rec_path = d / "records.jsonl"
        if not rec_path.exists():
            continue
        rows = []
        for line in rec_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            w, h = r["native_size"]
            has_prop = bool(r.get("n"))
            r["scores"] = score_annotation(r["filename"], r["annotation"], w, h,
                                           initial=r.get("initial") if has_prop else None)
            rows.append(_flatten(r))
        with open(d / "summary_rescored.csv", "w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
            wr.writeheader()
            wr.writerows(rows)
        n_dirs += 1
        print(f"{d.name}: {len(rows)} rows -> summary_rescored.csv")
    print(f"rescored {n_dirs} session folder(s)")


if __name__ == "__main__":
    main()
