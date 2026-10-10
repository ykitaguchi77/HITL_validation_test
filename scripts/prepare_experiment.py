"""Generate scripts/webapp/config/experiment.json (v2) for the BLIND n-shot
dose-response HITL study.

Design (see ~/.claude/plans and outputs/docs/analysis_plan.md v2):
  * Conditions = 8 proposal levels n ∈ {1,2,4,...,128} (fixed structure-specific
    SAM2 decoder-LoRA checkpoints, sequential 1-epoch-per-image warm start, 3
    training-order seeds) + manual (n = 0). Condition SLOTS = the 8 n-levels plus
    k manual slots (scripts/study_design.py: A annotators -> S slots, k = S-8).
  * Study images = S groups x G images (each group gaze-balanced n_f F + n_p P).
    Annotator a works group g under slot[(g + (S/A)*a) mod S]: every image is
    seen by all A annotators under A DISTINCT slots, and is annotated manually
    exactly k*A/S times (A=6: 12 slots, 60 images, manual x2 per image).
  * Per annotator: n_sessions sessions of session_size (10) images, each holding
    one image of 10 distinct slots (the S - 10 omitted slots rotate so every slot
    is omitted equally often and manual items per session differ by <= 1;
    study_design.session_slots); order shuffled; n / seed hidden. Within a group
    the peripheral images are staggered across its sessions so each session's
    gaze mix is as even as possible. Seeds rotate so each (annotator, n) cell is
    split as evenly as possible over the 3 seeds and each n is balanced overall.
  * Proposals are PRECOMPUTED (outputs/proposals/proposals.json); this script
    verifies every item has one and that the training orders / model-eval set
    are patient-disjoint from the study images.
  * Practice: 2 manual + 3 proposal images (n = 4/16/64, seed 0), GT shown,
    excluded from analysis, disjoint from the study images.

Run:  python scripts/prepare_experiment.py [--annotators 6]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "webapp" / "backend"))
from study_design import design_params, slot_of, session_slots, MANUAL, SEEDS  # noqa: E402
from config import EXPERIMENT_JSON, CONFIG_DIR, STUDY_IMAGES_JSON, PROPOSALS_JSON  # noqa: E402

SEED = 42
MODEL_EVAL_MANIFEST = ROOT / "outputs" / "model_eval" / "manifest.json"
# Real annotator identities (order = rotation index a). Names 4-6 are
# placeholders until recruitment is final; records are keyed by these strings.
ANNOTATOR_NAMES = ["kubota", "maeda", "kaisho", "annotator4", "annotator5", "annotator6"]
# Practice: manual first, then proposal correction (n covers the quality range).
PRACTICE_SPEC = [
    {"key": "p_manual", "is_hitl": False, "label": "練習1 ゼロから描く", "n": [0, 0]},
    {"key": "p_hitl", "is_hitl": True, "label": "練習2 予測を直す", "n": [4, 16, 64]},
]
PRACTICE_SEED = 0


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_name(n: int, seed) -> str | None:
    return None if not n else f"lora_s{seed}_n{n}"


def proposal_key(filename: str, n: int, seed) -> str | None:
    return None if not n else f"{filename}|n{n}|s{seed}"


def _item(r: dict, group: str, slot: str, n: int, seed) -> dict:
    e = {k: r[k] for k in ("image_id", "filename", "patient_id", "width", "height", "gaze", "ecc")}
    e.update({"group": group, "condition": slot, "n": n, "seed": seed, "train_size": n,
              "model": model_name(n, seed), "proposal_key": proposal_key(r["filename"], n, seed)})
    return e


def build_runs(p: dict, groups: dict[str, list[dict]], names: list[str], rng: random.Random) -> dict:
    S, G, A = p["n_slots"], p["group_size"], p["n_annotators"]
    n_p, n_sess = p["n_peripheral_per_group"], p["n_sessions"]
    gids = list(groups)
    runs = {}
    for a, annot in enumerate(names):
        slot_by_group = {g: slot_of(a, gi, p) for gi, g in enumerate(gids)}
        # sessions containing each group's slot (slot index of group gi = (gi + step*a) mod S)
        sess_of_slot = session_slots(p, a)                       # session -> slot indices
        sessions_of_group = {g: [k for k in range(n_sess) if ((gi + p["step"] * a) % S) in sess_of_slot[k]]
                             for gi, g in enumerate(gids)}
        assert all(len(v) == G for v in sessions_of_group.values())
        # seed per (n-slot): as even as possible, the short seed rotates with a and the slot index
        seeds_for_slot: dict[str, list] = {}
        for j, slot in enumerate(p["slots"]):
            if slot == MANUAL:
                continue
            lst = [SEEDS[(i + a + j) % len(SEEDS)] for i in range(G)]
            rng.shuffle(lst)
            seeds_for_slot[slot] = lst
        # session assignment: group g's n_p peripheral images go to the sessions
        # (among the G that contain its slot) with the fewest peripheral images so
        # far (random tie-break) -> per-session peripheral counts stay within +-1
        order = list(range(len(gids)))
        rng.shuffle(order)
        sessions: list[list[dict]] = [[] for _ in range(n_sess)]
        per_count = [0] * n_sess
        seed_cursor: Counter = Counter()
        for gi in order:
            g = gids[gi]
            slot = slot_by_group[g]
            L = list(sessions_of_group[g])
            imgs = list(groups[g])
            per = [x for x in imgs if x["gaze"] == "peripheral"]
            fro = [x for x in imgs if x["gaze"] == "frontal"]
            rng.shuffle(per); rng.shuffle(fro); rng.shuffle(L)
            L.sort(key=lambda k: per_count[k])          # stable: random order among ties
            per_sessions = L[:n_p]
            for k in per_sessions:
                per_count[k] += 1
            fro_sessions = L[n_p:]
            for k, r in zip(per_sessions + fro_sessions, per + fro):
                n = 0 if slot == MANUAL else int(slot[1:])
                seed = None if not n else seeds_for_slot[slot][seed_cursor[slot]]
                seed_cursor[slot] += 1
                sessions[k].append(_item(r, g, slot, n, seed))
        rng.shuffle(sessions)                       # session order
        out = []
        for k, items in enumerate(sessions):
            rng.shuffle(items)                      # order within session
            out.append({"session_index": k, "key": f"s{k + 1:02d}", "is_hitl": True,
                        "label": f"Session {k + 1}",
                        "items": [dict(it, order_in_session=i) for i, it in enumerate(items)]})
        runs[annot] = {"sessions": out}
    return runs


def build_practice(prac: list[dict], rng: random.Random) -> list[dict]:
    fro = [r for r in prac if r["gaze"] == "frontal"]
    per = [r for r in prac if r["gaze"] == "peripheral"]
    rng.shuffle(fro); rng.shuffle(per)
    # each practice session gets >= 1 peripheral (ellipse tilt practice)
    pools = {"p_manual": [fro.pop(), per.pop()], "p_hitl": [fro.pop(), fro.pop(), per.pop()]}
    out = []
    for spec in PRACTICE_SPEC:
        imgs = pools[spec["key"]]
        rng.shuffle(imgs)
        items = []
        for i, (r, n) in enumerate(zip(imgs, spec["n"])):
            it = _item(r, "practice", "practice", n, None if not n else PRACTICE_SEED)
            items.append(dict(it, order_in_session=i))
        out.append({"key": spec["key"], "is_hitl": spec["is_hitl"], "label": spec["label"], "items": items})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotators", type=int, default=6)
    args = ap.parse_args()

    study = json.loads(STUDY_IMAGES_JSON.read_text(encoding="utf-8"))
    p = design_params(args.annotators, study["design"]["group_size"])
    assert p["n_study_images"] == study["design"]["n_study_images"], \
        "annotator count incompatible with the frozen study pool (re-run select_study_images.py)"
    names = ANNOTATOR_NAMES[:p["n_annotators"]]
    assert len(names) == p["n_annotators"], "add annotator names"
    proposals = json.loads(PROPOSALS_JSON.read_text(encoding="utf-8"))
    manifest = json.loads(MODEL_EVAL_MANIFEST.read_text(encoding="utf-8"))
    study_sha = sha256_of(STUDY_IMAGES_JSON)
    assert proposals["provenance"]["study_images_sha256"] == study_sha, "proposals built from another study pool"
    assert manifest["study_images_sha256"] == study_sha, "checkpoints built from another study pool"

    imgs = [dict(r) for r in study["images"] if r["role"] == "study"]
    prac = [dict(r) for r in study["images"] if r["role"] == "practice"]
    rng = random.Random(SEED)
    fro = [r for r in imgs if r["gaze"] == "frontal"]
    per = [r for r in imgs if r["gaze"] == "peripheral"]
    rng.shuffle(fro); rng.shuffle(per)
    S, G, nf, npp = p["n_slots"], p["group_size"], p["n_frontal_per_group"], p["n_peripheral_per_group"]
    groups = {f"G{g}": fro[g * nf:(g + 1) * nf] + per[g * npp:(g + 1) * npp] for g in range(S)}

    runs = build_runs(p, groups, names, rng)
    practice = build_practice(prac, rng)
    conditions = [{"key": MANUAL, "n": 0, "is_hitl": False}] + \
                 [{"key": f"n{n}", "n": n, "is_hitl": True} for n in p["n_levels"]]
    experiment = {
        "version": 2, "design": "dose_response_nshot", "seed": SEED,
        **{k: p[k] for k in ("n_annotators", "n_slots", "n_manual_slots", "step", "group_size",
                             "n_frontal_per_group", "n_peripheral_per_group", "manual_per_image",
                             "images_per_annotator", "manual_per_annotator", "slots", "n_levels", "seeds",
                             "session_size", "n_sessions", "omit_per_session")},
        "n_per_session": p["session_size"],
        "ecc_threshold": study["ecc_threshold"], "gaze_baseline": study["gaze_baseline"],
        "conditions": conditions, "annotators": names,
        "groups": {g: [{k: r[k] for k in ("image_id", "filename", "patient_id", "width", "height",
                                            "gaze", "ecc")} for r in items] for g, items in groups.items()},
        "slot_assignment": {annot: {g: slot_of(a, gi, p) for gi, g in enumerate(groups)}
                            for a, annot in enumerate(names)},
        "runs": runs, "practice": practice,
        "checkpoints": {"run": manifest["run"], "recipe": manifest["recipe"],
                        "n_trainable_params": manifest.get("n_trainable_params")},
        "study_images_file": str(STUDY_IMAGES_JSON.relative_to(ROOT)), "study_images_sha256": study_sha,
        "proposals_file": str(PROPOSALS_JSON.relative_to(ROOT)), "proposals_sha256": sha256_of(PROPOSALS_JSON),
        "model_eval_manifest_sha256": sha256_of(MODEL_EVAL_MANIFEST),
    }
    _audit_and_assert(experiment, p, imgs, prac, proposals, manifest)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(EXPERIMENT_JSON, "w", encoding="utf-8") as f:
        json.dump(experiment, f, ensure_ascii=False, indent=1)
    print(f"\nWrote {EXPERIMENT_JSON}\nsha256 {sha256_of(EXPERIMENT_JSON)}")


def _audit_and_assert(exp, p, study, prac, proposals, manifest):
    S, G, A = p["n_slots"], p["group_size"], p["n_annotators"]
    nf, npp = p["n_frontal_per_group"], p["n_peripheral_per_group"]
    P, n_sess = p["session_size"], p["n_sessions"]
    study_ids = {r["image_id"] for r in study}
    prac_ids = {r["image_id"] for r in prac}
    groups, runs = exp["groups"], exp["runs"]
    print("=== experiment.json v2 audit ===")
    print(f"annotators={A} slots={S} (manual x{p['n_manual_slots']}) group_size={G} "
          f"sessions={n_sess}x{P} study={len(study_ids)} practice={len(prac_ids)}")

    # groups: S groups x (nf F + npp P), union = all study images
    assert len(groups) == S
    union = set()
    for g, items in groups.items():
        assert len(items) == G, g
        assert Counter(i["gaze"] for i in items) == {"frontal": nf, "peripheral": npp}, g
        union |= {i["image_id"] for i in items}
    assert union == study_ids and len(union) == S * G
    assert not (prac_ids & study_ids)

    # practice
    pr = exp["practice"]
    assert [ps["is_hitl"] for ps in pr] == [False, True]
    pitems = [it for ps in pr for it in ps["items"]]
    assert {it["image_id"] for it in pitems} == prac_ids and len(pitems) == len(prac_ids)
    assert all(it["n"] == 0 for it in pr[0]["items"]) and all(it["n"] > 0 for it in pr[1]["items"])
    for ps in pr:
        assert any(it["gaze"] == "peripheral" for it in ps["items"]), ps["key"]

    # per annotator
    slot_sets: dict[int, list[str]] = defaultdict(list)   # image_id -> slots across annotators
    manual_count: Counter = Counter()
    seed_total: dict[str, Counter] = defaultdict(Counter)
    for a, annot in enumerate(exp["annotators"]):
        sessions = runs[annot]["sessions"]
        assert [s["session_index"] for s in sessions] == list(range(n_sess)), annot
        seen: list[int] = []
        per_slot: Counter = Counter()
        per_n_gaze: dict[str, Counter] = defaultdict(Counter)
        per_n_seed: dict[str, Counter] = defaultdict(Counter)
        per_session_p, per_session_m = [], []
        slot_omissions: Counter = Counter()
        for s in sessions:
            assert s["is_hitl"] and len(s["items"]) == P, (annot, s["key"])
            assert [it["order_in_session"] for it in s["items"]] == list(range(P))
            conds = Counter(it["condition"] for it in s["items"])
            # each n-level at most once per session; manual = the slots not omitted
            assert all(v == 1 for k, v in conds.items() if k != MANUAL), (annot, s["key"], conds)
            assert len(s["items"]) == sum(conds.values()) and set(conds) <= set(p["slots"])
            for n in p["n_levels"]:
                slot_omissions[f"n{n}"] += conds.get(f"n{n}", 0) == 0
            per_session_m.append(conds.get(MANUAL, 0))
            per_session_p.append(sum(it["gaze"] == "peripheral" for it in s["items"]))
            for it in s["items"]:
                seen.append(it["image_id"])
                per_slot[it["condition"]] += 1
                per_n_gaze[it["condition"]][it["gaze"]] += 1
                assert it["train_size"] == it["n"]
                assert exp["slot_assignment"][annot][it["group"]] == it["condition"]
                if it["n"] == 0:
                    assert it["seed"] is None and it["model"] is None and it["proposal_key"] is None
                    manual_count[it["image_id"]] += 1
                else:
                    assert it["seed"] in p["seeds"] and it["model"] == f"lora_s{it['seed']}_n{it['n']}"
                    per_n_seed[it["condition"]][it["seed"]] += 1
                    seed_total[it["condition"]][it["seed"]] += 1
                slot_sets[it["image_id"]].append(it["condition"])
        assert max(per_session_m) - min(per_session_m) <= 1, (annot, per_session_m)
        assert set(slot_omissions.values()) <= {n_sess - G}, (annot, slot_omissions)
        assert sorted(seen) == sorted(study_ids), f"{annot}: image set != study images / duplicates"
        for n in p["n_levels"]:
            key = f"n{n}"
            assert per_slot[key] == G and per_n_gaze[key] == {"frontal": nf, "peripheral": npp}, (annot, key)
            cnt = per_n_seed[key]
            assert max(cnt.values()) - min(cnt.get(sd, 0) for sd in p["seeds"]) <= 1, (annot, key, cnt)
        assert per_slot[MANUAL] == p["manual_per_annotator"]
        assert max(per_session_p) - min(per_session_p) <= 2, (annot, per_session_p)
        print(f"  {annot}: sessions={n_sess}x{P} manual={per_slot[MANUAL]} manual/session={per_session_m} "
              f"peripheral/session={per_session_p}")
    # across annotators
    for iid, slots in slot_sets.items():
        assert len(slots) == A and len(set(s for s in slots if s != MANUAL)) == len([s for s in slots if s != MANUAL]), iid
        assert manual_count[iid] == p["manual_per_image"], (iid, manual_count[iid])
    for n in p["n_levels"]:
        tot = seed_total[f"n{n}"]
        assert max(tot.values()) - min(tot.values()) <= A // len(p["seeds"]) + 1, (n, tot)
    print(f"  seed totals per n: {dict(seed_total['n1'])} (identical pattern for all n)")

    # proposals present for every n>0 item (runs + practice)
    all_items = [it for r in runs.values() for s in r["sessions"] for it in s["items"]] + pitems
    for it in all_items:
        if it["n"]:
            e = proposals["images"][it["filename"]]["proposals"][f"n{it['n']}"][f"s{it['seed']}"]
            assert "shapes" in e and "metrics" in e, it["proposal_key"]

    # patient disjointness: study patients vs training orders and model-eval set (both ways)
    study_pat = {r["patient_id"] for r in study} | {r["patient_id"] for r in prac}
    train_pat = {i.split("-")[0] for o in manifest["orders"].values() for i in o}
    eval_pat = {i.split("-")[0] for i in manifest["eval_ids"]}
    assert not (study_pat & train_pat), study_pat & train_pat
    assert not (study_pat & eval_pat), study_pat & eval_pat
    assert not (train_pat & eval_pat)
    assert study_pat <= set(manifest["excluded_patients"])
    print(f"  patients: study={len(study_pat)} train={len(train_pat)} eval={len(eval_pat)} (disjoint)")
    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
