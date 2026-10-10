"""Proposal lookup for the n-shot dose-response study (no runtime inference).

Every (study image, n, seed) proposal of the fixed decoder-LoRA checkpoints is
precomputed offline into ``outputs/proposals/proposals.json`` by
``Eyelid_few_shot_HITL/scripts/eval/export_study_proposals.py`` (which imports
``geometry.masks_to_shapes`` / ``scoring.score_annotation`` from here, so the
shape format and the proposal-vs-GT metrics are exactly the app's own).

    proposals.json = {
      version, provenance{...}, n_levels, seeds,
      images: {filename: {image_id, width, height,
                proposals: {"n8": {"s1": {shapes: {eyelid:[poly], caruncle:[],
                                                   iris:[ellipse], pupil:[ellipse]},
                                          metrics: {eyelid:{dice,assd,...}, ..., mean_dice}}}}}}}

Manual items (n = 0) return EMPTY. Both paths are dict lookups, so there is no
latency difference an annotator could use to infer the condition.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from config import PROPOSALS_JSON

EMPTY: dict = {"eyelid": [], "caruncle": [], "iris": [], "pupil": []}


def empty() -> dict:
    return {k: [] for k in EMPTY}


@lru_cache(maxsize=1)
def _load() -> dict:
    if not PROPOSALS_JSON.exists():
        raise FileNotFoundError(
            f"{PROPOSALS_JSON} not found. Run Eyelid_few_shot_HITL/scripts/eval/export_study_proposals.py")
    with open(PROPOSALS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def file_sha256() -> str:
    return hashlib.sha256(PROPOSALS_JSON.read_bytes()).hexdigest()


def proposal_key(filename: str, n: int, seed: int) -> str:
    return f"{filename}|n{n}|s{seed}"


def _entry(filename: str, n: int, seed: int) -> dict | None:
    img = _load()["images"].get(filename)
    if not img:
        return None
    return img["proposals"].get(f"n{n}", {}).get(f"s{seed}")


def get_proposal(filename: str, n: int, seed: int) -> dict:
    """Initial shapes for the item (deep-copied so callers can mutate)."""
    if not n:
        return empty()
    e = _entry(filename, n, seed)
    if e is None:
        raise KeyError(proposal_key(filename, n, seed))
    return json.loads(json.dumps(e["shapes"]))


def get_proposal_metrics(filename: str, n: int, seed: int) -> dict | None:
    """Precomputed proposal-vs-GT metrics (None for manual items)."""
    if not n:
        return None
    e = _entry(filename, n, seed)
    return None if e is None else e.get("metrics")


def validate(experiment: dict) -> int:
    """Fail fast at startup: every item with n > 0 (runs + practice) must have
    its proposal. Returns the number of proposal items checked."""
    checked, missing = 0, []
    items = [it for run in experiment.get("runs", {}).values()
             for s in run["sessions"] for it in s["items"]]
    items += [it for ps in experiment.get("practice", []) for it in ps["items"]]
    for it in items:
        n = it.get("n") or 0
        if not n:
            continue
        checked += 1
        if _entry(it["filename"], n, it["seed"]) is None:
            missing.append(proposal_key(it["filename"], n, it["seed"]))
    if missing:
        raise RuntimeError(f"{len(missing)} proposals missing in {PROPOSALS_JSON}: {missing[:5]} ...")
    want = experiment.get("proposals_sha256")
    if want and want != file_sha256():
        raise RuntimeError("proposals.json changed since experiment.json was generated "
                           "(sha256 mismatch) -> re-run scripts/prepare_experiment.py")
    return checked
