"""Central configuration for the HITL annotation webapp.

Paths to the external dataset / model live here. Experiment-specific data
(phases, model registry, per-phase image assignments) live in
``scripts/webapp/config/experiment.json`` and are generated/edited via
``scripts/prepare_experiment.py``. Everything model-related is config-driven so
the subset checkpoints (500/1000/.../2500) can be swapped in later without code
changes.
"""
from __future__ import annotations

import json
from pathlib import Path

# --- Project layout -------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]          # Eyelid_HITL_experiment
WEBAPP_DIR = Path(__file__).resolve().parents[1]            # scripts/webapp
STATIC_DIR = WEBAPP_DIR / "static"
CONFIG_DIR = WEBAPP_DIR / "config"
EXPERIMENT_JSON = CONFIG_DIR / "experiment.json"
RESULTS_DIR = PROJECT_ROOT / "outputs" / "results"

# --- External dataset (comparison repo) -----------------------------------
COMPARISON_REPO = Path(r"C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison")
IMAGES_DIR = COMPARISON_REPO / "Images" / "images"
EYELID_XML = COMPARISON_REPO / "Images" / "eyelid_caruncle_seg_0-3000.xml"
IRIS_XML = COMPARISON_REPO / "Images" / "obb_iris_pupil_1-3000.xml"
METADATA_CSV = COMPARISON_REPO / "image_metadata.csv"

# Default checkpoint (full 3000-image model). Subset models replace the
# per-phase entries in experiment.json once trained.
DEFAULT_CHECKPOINT = (
    COMPARISON_REPO
    / "Ablation_SegFormerB1_Amodal_Blur_v3"
    / "models"
    / "segformer_b1_amodal_v3_best.pth"
)
SEGFORMER_BACKBONE = "nvidia/segformer-b1-finetuned-ade-512-512"
INFER_SIZE = 512  # model input resolution

# --- Annotation classes ---------------------------------------------------
# kind: "polygon" (Eyelid) or "ellipse" (Iris/Pupil OBB).
# Caruncle is NOT a separate class: the Eyelid and Caruncle XML polygons are
# merged into a single "Eyelid" region (matching the model's eyelid channel,
# which was trained on the Eyelid∪Caruncle union).
CLASSES = [
    {"key": "eyelid", "name": "Eyelid", "kind": "polygon", "color": "#ff3b30", "model_channel": "eyelid"},
    {"key": "iris", "name": "Iris", "kind": "ellipse", "color": "#34c759", "model_channel": "iris"},
    {"key": "pupil", "name": "Pupil", "kind": "ellipse", "color": "#0a84ff", "model_channel": "pupil"},
]
CLASS_BY_KEY = {c["key"]: c for c in CLASSES}
# XML label name -> class key (Caruncle folds into eyelid)
XML_LABEL_TO_KEY = {"Eyelid": "eyelid", "Caruncle": "eyelid", "Iris": "iris", "Pupil": "pupil"}


def load_experiment() -> dict:
    """Load experiment.json (phases, models, per-phase image assignments)."""
    if not EXPERIMENT_JSON.exists():
        raise FileNotFoundError(
            f"{EXPERIMENT_JSON} not found. Run: python scripts/prepare_experiment.py"
        )
    with open(EXPERIMENT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_model_path(model_key: str | None, experiment: dict) -> str | None:
    """Return checkpoint path for a model key (None => no model / scratch)."""
    if not model_key:
        return None
    entry = experiment.get("models", {}).get(model_key)
    if not entry:
        return None
    return entry.get("path") or str(DEFAULT_CHECKPOINT)
