"""Generate scripts/webapp/config/experiment.json for the BLIND, Latin-square,
interleaved HITL study.

Design (see plan): 9 conditions = scratch + 8 HITL models (seg100..seg2500).
90 patient-safe images (disjoint from training) form 9 gaze-balanced blocks
(7 frontal + 3 peripheral each). A 3x9 cyclic Latin square maps
(annotator, block) -> condition so image difficulty is balanced across the 3
annotators. Per annotator the run is baked: session 0 = scratch (fixed first,
a clean baseline before any model exposure); sessions 1..8 = the 8 HITL blocks'
80 images repartitioned into condition-mixed, gaze-balanced, blind sessions of
10 (shuffled slot order). A separate ~5-image practice set (3 frontal + 2
peripheral, disjoint from the 90 and from training) warms up tool familiarity
(GT revealed after each practice submission; excluded from analysis).

Gaze is auto-classified by de-baselined iris eccentricity (see iris_offset).
patient_id = filename prefix before first '-'. Test pool = patients whose min
annotated image_id >= TEST_START, so no test patient appears in any training set.

Run:  python scripts/prepare_experiment.py
"""
from __future__ import annotations

import json
import random
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict
from itertools import zip_longest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "webapp" / "backend"))
from config import (EXPERIMENT_JSON, CONFIG_DIR, IMAGES_DIR, EYELID_XML,  # noqa: E402
                    SEGFORMER_BACKBONE)
from geometry import get_gt_annotation  # noqa: E402  (parses eyelid + iris GT)

SEED = 42
TEST_START = 2500     # test pool lower bound (image_id); train patients have min id < this
TEST_END = 2999       # manual-annotation upper bound
N_BLOCKS = 9          # = number of conditions
N_PER_SESSION = 10
N_FRONTAL = 7         # frontal images per block / per session
N_PERIPHERAL = 3      # peripheral images per block / per session
N_ANNOTATORS = 3
# Practice = two short warm-up sessions covering BOTH workflows: draw-from-scratch
# THEN correct-a-prefill. Each has 2 frontal + 1 peripheral (peripheral exercises
# the iris/pupil ellipse tilt). GT is revealed after each practice submission.
PRACTICE_SPEC = [
    {"key": "p_scratch", "is_hitl": False, "model": None,
     "label": "練習1 Scratch（ゼロから描く）", "n_f": 2, "n_p": 1},
    {"key": "p_hitl", "is_hitl": True, "model": "seg1000",
     "label": "練習2 修正（予測を直す）", "n_f": 2, "n_p": 1},
]
N_PRACTICE_FRONTAL = sum(s["n_f"] for s in PRACTICE_SPEC)
N_PRACTICE_PERIPHERAL = sum(s["n_p"] for s in PRACTICE_SPEC)
# de-baselined iris eccentricity at/above which a gaze counts as peripheral.
ECC_THRESHOLD = 0.20

# Condition index 0 = scratch; 1..8 = the 8 HITL models (this order = Latin-square columns)
CONDITION_MODELS = [None, "seg100", "seg200", "seg300", "seg500",
                    "seg1000", "seg1500", "seg2000", "seg2500"]

# Subset models trained by scripts/train_subset.py on patient-safe nested subsets.
_MODELS_DIR = Path(__file__).resolve().parents[1] / "outputs" / "models"
MODELS = {
    f"seg{n}": {"path": str(_MODELS_DIR / f"seg{n}.pth"),
                "trained_on": f"~{n} imgs, patient-safe (min annotated id < {TEST_START})",
                "backbone": SEGFORMER_BACKBONE, "placeholder": False, "trained_images": n}
    for n in (100, 200, 300, 500, 1000, 1500, 2000, 2500)
}


def patient_of(name: str) -> str:
    return name.split("-")[0]


def _poly_bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def iris_offset(name: str):
    """Signed (ex, ey): iris OBB centre minus eyelid bbox centre, normalised by
    eyelid bbox size. None if eyelid or iris GT is missing."""
    ann = get_gt_annotation(name)
    eyelids = ann.get("eyelid") or []
    irises = ann.get("iris") or []
    if not eyelids or not irises:
        return None
    best = max(eyelids, key=lambda p: (lambda b: (b[2] - b[0]) * (b[3] - b[1]))(_poly_bbox(p)))
    x0, y0, x1, y1 = _poly_bbox(best)
    w, h = (x1 - x0), (y1 - y0)
    if w <= 0 or h <= 0:
        return None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    iris = irises[0]
    return ((iris["cx"] - cx) / w, (iris["cy"] - cy) / h)


def load_images_from_xml() -> list[dict]:
    """[{image_id, filename, patient_id, width, height, n_shapes}] for all images."""
    out = []
    for im in ET.parse(EYELID_XML).getroot().findall("image"):
        out.append({
            "image_id": int(im.attrib["id"]),
            "filename": im.attrib["name"],
            "patient_id": patient_of(im.attrib["name"]),
            "width": int(float(im.attrib.get("width", 0))),
            "height": int(float(im.attrib.get("height", 0))),
            "n_shapes": len(list(im)),
        })
    return out


def _base(r: dict, block=None) -> dict:
    e = {k: r[k] for k in ("image_id", "filename", "patient_id", "width", "height")}
    e["gaze"] = r["gaze"]; e["ecc"] = r["ecc"]
    if block is not None:
        e["block"] = block
    return e


def _roundrobin_by_condition(items: list[dict]) -> list[dict]:
    """Interleave items so consecutive picks cycle through conditions (spreads
    each condition's images across sessions). Deterministic (groups sorted)."""
    groups = OrderedDict()
    for x in sorted(items, key=lambda y: y["condition"]):
        groups.setdefault(x["condition"], []).append(x)
    out = []
    for tup in zip_longest(*groups.values()):
        out.extend(x for x in tup if x is not None)
    return out


def main() -> None:
    imgs = load_images_from_xml()

    # patient-safe test pool: patients whose min annotated id >= TEST_START
    min_ann_id: dict[str, int] = defaultdict(lambda: 10**9)
    for r in imgs:
        if r["n_shapes"] > 0:
            min_ann_id[r["patient_id"]] = min(min_ann_id[r["patient_id"]], r["image_id"])
    safe_patients = {p for p, mid in min_ann_id.items() if mid >= TEST_START}

    pool = [r for r in imgs
            if TEST_START <= r["image_id"] <= TEST_END and r["n_shapes"] > 0
            and r["patient_id"] in safe_patients and (IMAGES_DIR / r["filename"]).exists()]
    pool.sort(key=lambda r: r["image_id"])

    # gaze classification (de-baselined iris eccentricity)
    offsets = {r["image_id"]: iris_offset(r["filename"]) for r in pool}
    have = [o for o in offsets.values() if o is not None]
    mex = sorted(o[0] for o in have)[len(have) // 2]
    mey = sorted(o[1] for o in have)[len(have) // 2]
    pool = [r for r in pool if offsets[r["image_id"]] is not None]
    for r in pool:
        o = offsets[r["image_id"]]
        dx, dy = o[0] - mex, o[1] - mey
        r["ecc"] = round((dx * dx + dy * dy) ** 0.5, 4)
        r["gaze"] = "peripheral" if r["ecc"] >= ECC_THRESHOLD else "frontal"

    frontal = [r for r in pool if r["gaze"] == "frontal"]
    peripheral = [r for r in pool if r["gaze"] == "peripheral"]

    need_f = N_BLOCKS * N_FRONTAL + N_PRACTICE_FRONTAL      # 63 + 3
    need_p = N_BLOCKS * N_PERIPHERAL + N_PRACTICE_PERIPHERAL  # 27 + 2
    if len(frontal) < need_f or len(peripheral) < need_p:
        raise SystemExit(f"Need {need_f} frontal + {need_p} peripheral; pool has "
                         f"{len(frontal)} / {len(peripheral)} (lower ECC_THRESHOLD).")

    rng = random.Random(SEED)
    sel_f = rng.sample(frontal, need_f)
    sel_p = rng.sample(peripheral, need_p)
    study_f, prac_f = sel_f[:N_BLOCKS * N_FRONTAL], sel_f[N_BLOCKS * N_FRONTAL:]
    study_p, prac_p = sel_p[:N_BLOCKS * N_PERIPHERAL], sel_p[N_BLOCKS * N_PERIPHERAL:]
    rng.shuffle(study_f); rng.shuffle(study_p)

    # 9 gaze-balanced blocks (7F + 3P)
    blocks: dict[str, list[dict]] = {}
    for j in range(N_BLOCKS):
        bid = f"B{j}"
        items = [_base(r, bid) for r in (study_f[j * N_FRONTAL:(j + 1) * N_FRONTAL]
                                         + study_p[j * N_PERIPHERAL:(j + 1) * N_PERIPHERAL])]
        blocks[bid] = items

    # 3x9 cyclic Latin square: L[annotator_row][block] = condition index
    L = [[(i + j) % N_BLOCKS for j in range(N_BLOCKS)] for i in range(N_ANNOTATORS)]

    conditions = [{"index": i, "key": ("scratch" if i == 0 else CONDITION_MODELS[i]),
                   "model": CONDITION_MODELS[i], "is_hitl": i != 0} for i in range(N_BLOCKS)]

    def train_size(model):
        return MODELS[model]["trained_images"] if model else None

    runs: dict[str, dict] = {}
    for ai in range(N_ANNOTATORS):
        annot = str(ai + 1)
        block_cond = {f"B{j}": L[ai][j] for j in range(N_BLOCKS)}

        # scratch session = the block this annotator maps to condition 0
        scratch_bid = next(b for b, c in block_cond.items() if c == 0)
        scratch_imgs = [dict(im, condition="scratch", model=None, train_size=None)
                        for im in blocks[scratch_bid]]
        rng.shuffle(scratch_imgs)

        # the 8 HITL blocks -> 80 images tagged with their hidden condition
        hitl = []
        for bid, cidx in block_cond.items():
            if cidx == 0:
                continue
            model = CONDITION_MODELS[cidx]
            hitl += [dict(im, condition=model, model=model, train_size=train_size(model))
                     for im in blocks[bid]]
        hf = _roundrobin_by_condition([x for x in hitl if x["gaze"] == "frontal"])    # 56
        hp = _roundrobin_by_condition([x for x in hitl if x["gaze"] == "peripheral"])  # 24

        # chunk into 8 condition-mixed, gaze-balanced sessions of 10
        hitl_sessions = []
        for s in range(N_BLOCKS - 1):
            sitems = (hf[s * N_FRONTAL:(s + 1) * N_FRONTAL]
                      + hp[s * N_PERIPHERAL:(s + 1) * N_PERIPHERAL])
            rng.shuffle(sitems)
            hitl_sessions.append(sitems)
        rng.shuffle(hitl_sessions)   # shuffle only the 8 HITL slots (scratch stays first)

        def sess(items, idx, key, is_hitl, label):
            return {"session_index": idx, "key": key, "is_hitl": is_hitl, "label": label,
                    "items": [dict(it, order_in_session=k) for k, it in enumerate(items)]}

        sessions = [sess(scratch_imgs, 0, "scratch", False, "Scratch")]
        for s, sitems in enumerate(hitl_sessions):
            sessions.append(sess(sitems, s + 1, f"hitl_{s + 1}", True, f"Session {s + 1}"))
        runs[annot] = {"sessions": sessions}

    # practice: two short warm-up sessions (disjoint from the 90 study images & training)
    fi, pi = iter(prac_f), iter(prac_p)
    practice = []
    for spec in PRACTICE_SPEC:
        items = ([_base(next(fi)) for _ in range(spec["n_f"])]
                 + [_base(next(pi)) for _ in range(spec["n_p"])])
        rng.shuffle(items)
        practice.append({"key": spec["key"], "is_hitl": spec["is_hitl"], "model": spec["model"],
                         "label": spec["label"],
                         "items": [dict(it, order_in_session=k) for k, it in enumerate(items)]})

    # legacy phases/assignments (annotator 1's block->condition) for HITL_DEBUG fallback
    legacy_phases, legacy_assign = [], {}
    for cidx in range(N_BLOCKS):
        model = CONDITION_MODELS[cidx]
        ckey = "scratch" if cidx == 0 else model
        label = "Scratch (no model)" if cidx == 0 else f"HITL @{MODELS[model]['trained_images']}"
        legacy_phases.append({"key": ckey, "label": label, "model": model})
        bid = next(f"B{j}" for j in range(N_BLOCKS) if L[0][j] == cidx)
        legacy_assign[ckey] = [dict(im) for im in blocks[bid]]

    experiment = {
        "seed": SEED, "test_start": TEST_START, "test_end": TEST_END,
        "n_blocks": N_BLOCKS, "n_annotators": N_ANNOTATORS, "n_per_session": N_PER_SESSION,
        "n_frontal": N_FRONTAL, "n_peripheral": N_PERIPHERAL, "ecc_threshold": ECC_THRESHOLD,
        "gaze_baseline": {"ex": round(mex, 4), "ey": round(mey, 4)},
        "conditions": conditions, "blocks": blocks, "latin_square": L,
        "annotators": [str(i + 1) for i in range(N_ANNOTATORS)],
        "runs": runs, "practice": practice, "models": MODELS,
        # legacy fallback (debug only)
        "phases": legacy_phases, "assignments": legacy_assign, "n_per_phase": N_PER_SESSION,
    }

    _audit_and_assert(experiment, pool, study_f + study_p, prac_f + prac_p)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(EXPERIMENT_JSON, "w", encoding="utf-8") as f:
        json.dump(experiment, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {EXPERIMENT_JSON}")


def _audit_and_assert(exp, pool, study, practice_imgs):
    blocks, L, runs = exp["blocks"], exp["latin_square"], exp["runs"]
    pool_ids = {r["image_id"] for r in pool}
    study_ids = {r["image_id"] for r in study}
    prac_ids = {r["image_id"] for r in practice_imgs}

    print("=== experiment.json audit ===")
    print(f"pool={len(pool_ids)}  study(90)={len(study_ids)}  practice={len(prac_ids)}")

    # blocks: 9 blocks, each 7F+3P, all in pool, study = union of blocks (90 unique)
    assert len(blocks) == N_BLOCKS
    block_union = set()
    for bid, items in blocks.items():
        assert len(items) == N_PER_SESSION, bid
        assert sum(i["gaze"] == "frontal" for i in items) == N_FRONTAL, bid
        assert sum(i["gaze"] == "peripheral" for i in items) == N_PERIPHERAL, bid
        ids = {i["image_id"] for i in items}
        assert ids <= pool_ids
        block_union |= ids
    assert block_union == study_ids and len(block_union) == 90, "blocks != 90 unique study imgs"

    # Latin square: each row a permutation of 0..8; each column 3 distinct
    for row in L:
        assert sorted(row) == list(range(N_BLOCKS)), "row not a permutation"
    for c in range(N_BLOCKS):
        col = [L[r][c] for r in range(len(L))]
        assert len(set(col)) == len(col), "column has duplicate condition"

    # practice: two warm-up sessions (scratch then hitl), each gaze-balanced; disjoint from study
    prac_sessions = exp["practice"]
    prac_items = [it for ps in prac_sessions for it in ps["items"]]
    assert len(prac_ids) == len(prac_items) == N_PRACTICE_FRONTAL + N_PRACTICE_PERIPHERAL
    pf = sum(i["gaze"] == "frontal" for i in prac_items)
    pp = sum(i["gaze"] == "peripheral" for i in prac_items)
    assert (pf, pp) == (N_PRACTICE_FRONTAL, N_PRACTICE_PERIPHERAL), (pf, pp)
    assert pp >= 2, "practice must include >=2 peripheral"
    for ps in prac_sessions:
        assert sum(i["gaze"] == "peripheral" for i in ps["items"]) >= 1, f"{ps['key']} needs >=1 peripheral"
    assert [ps["is_hitl"] for ps in prac_sessions] == [False, True], "practice order: scratch then hitl"
    assert not (prac_ids & study_ids), "practice overlaps study images"

    # per-annotator runs
    for annot, run in runs.items():
        sessions = run["sessions"]
        assert len(sessions) == N_BLOCKS
        s0 = sessions[0]
        assert s0["session_index"] == 0 and s0["key"] == "scratch" and not s0["is_hitl"], \
            f"annotator {annot}: scratch not session 0"
        seen_ids, conds_seen = set(), set()
        for s in sessions:
            assert len(s["items"]) == N_PER_SESSION
            assert sum(i["gaze"] == "frontal" for i in s["items"]) == N_FRONTAL
            assert sum(i["gaze"] == "peripheral" for i in s["items"]) == N_PERIPHERAL
            sconds = {i["condition"] for i in s["items"]}
            if s["is_hitl"]:
                assert len(sconds) >= 2, f"annotator {annot} {s['key']} not interleaved: {sconds}"
            else:
                assert sconds == {"scratch"}
            conds_seen |= sconds
            seen_ids |= {i["image_id"] for i in s["items"]}
        assert seen_ids == study_ids, f"annotator {annot} image set != 90 study imgs"
        assert conds_seen == {"scratch"} | {m for m in CONDITION_MODELS if m}, \
            f"annotator {annot} missing conditions"
        # report
        order = " ".join(s["key"] for s in sessions)
        print(f"  annotator {annot}: {order}")
    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
