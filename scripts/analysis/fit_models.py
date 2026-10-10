"""Pre-specified analyses for the n-shot dose-response HITL study (analysis_plan v2).

Input: every outputs/results/<annotator>_<session>_a<attempt>_<stamp>/summary.csv
(written by scripts/webapp/backend/session.py). Excludes the `test` pseudo-annotator
and practice sessions; keeps attempt 1 per (annotator, session_key, image_id)
unless --last-attempt.

Models (crossed random intercepts for annotator and image via variance components):
  H1  log(duration_sec) ~ log2(n) + gaze + order_in_session + session_index + C(seed)   [n >= 1]
      one-sided slope < 0; saturation curve a + b*exp(-n/tau) vs linear-in-log2(n), AIC
  H2  per structure: ASSD ~ C(condition, ref=manual) + gaze ; fixed-sequence non-inferiority
      from n=128 downward with margin --delta-<structure> (px); also Dice and HD95 (reported)
  H3  automation bias: final ASSD ~ proposal ASSD (+ manual ASSD of the same image by others)
  NOV proposal-quality -> effort: log(duration) ~ mean proposal ASSD (all structures) with / without log2(n)
  DESC manual baseline per annotator, inter-annotator agreement on manual items, gate failure rate

Run:  python scripts/analysis/fit_models.py [--results outputs/results] [--out outputs/analysis]
Dry-run on developer data:  python scripts/analysis/fit_models.py --include-test
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STRUCTS = ["eyelid", "iris", "pupil"]
N_LEVELS = [1, 2, 4, 8, 16, 32, 64, 128]
warnings.filterwarnings("ignore")


def load_results(results_dir: Path, include_test: bool, last_attempt: bool) -> pd.DataFrame:
    frames = []
    for csv in sorted(results_dir.glob("*/summary.csv")):
        resc = csv.with_name("summary_rescored.csv")     # scripts/analysis/rescore_records.py output
        d = pd.read_csv(resc if resc.exists() else csv)
        d["src"] = csv.parent.name
        frames.append(d)
    if not frames:
        raise SystemExit(f"no summary.csv under {results_dir}")
    df = pd.concat(frames, ignore_index=True)
    if not include_test:
        df = df[df.annotator.astype(str) != "test"]
    df = df[df.is_practice.astype(str).str.lower() != "true"]
    if "n" not in df:                       # pre-v2 records (SegFormer pilot) -> treat as manual
        df["n"] = 0
        df["seed"] = np.nan
    df["n"] = df["n"].fillna(0).astype(int)
    df["condition"] = df["condition"].where(df["n"] > 0, "manual")
    df["attempt"] = df["attempt"].fillna(1).astype(int)
    key = ["annotator", "session_key", "image_id"]
    df = df.sort_values(key + ["attempt", "timestamp"])
    df = df.groupby(key, as_index=False).tail(1) if last_attempt else df[df.attempt == df.groupby(key)["attempt"].transform("min")]
    df = df.drop_duplicates(key, keep="last").reset_index(drop=True)
    df["log_dur"] = np.log(df["duration_sec"].astype(float))
    df["log2n"] = np.log2(df["n"].where(df["n"] > 0, np.nan))
    df["gaze_p"] = (df["gaze"] == "peripheral").astype(int)
    df["one"] = 1
    return df


def synthetic(n_annotators: int = 6, seed: int = 0) -> pd.DataFrame:
    """Fake v2-schema dataset (for exercising every model before real data exist)."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from study_design import design_params, slot_of, MANUAL
    p = design_params(n_annotators)
    rng = np.random.default_rng(seed)
    rows = []
    for a in range(p["n_annotators"]):
        for g in range(p["n_slots"]):
            slot = slot_of(a, g, p)
            n = 0 if slot == MANUAL else int(slot[1:])
            for i in range(p["group_size"]):
                img = g * p["group_size"] + i
                prop = {s: (np.nan if n == 0 else max(0.3, 8.0 * 2 ** (-np.log2(n) * 0.4) + rng.normal(0, 1))) for s in STRUCTS}
                row = {"annotator": f"a{a}", "session_key": f"s{rng.integers(p['group_size']) + 1:02d}",
                       "session_index": rng.integers(p["group_size"]), "image_id": img, "attempt": 1,
                       "timestamp": "t", "is_practice": False, "condition": slot, "n": n,
                       "seed": np.nan if n == 0 else rng.integers(3), "gaze": rng.choice(["frontal", "peripheral"]),
                       "order_in_session": rng.integers(p["n_slots"]),
                       "duration_sec": float(np.exp(np.log(130) - 0.05 * (np.log2(n) if n else 0) + rng.normal(0, 0.5)))}
                for s in STRUCTS:
                    row[f"{s}_assd"] = 2.3 + (0.2 * prop[s] if n else 0) + abs(rng.normal(0, 0.8))
                    row[f"{s}_dice"] = 0.97 - 0.002 * row[f"{s}_assd"]
                    row[f"{s}_hd95"] = 3 * row[f"{s}_assd"]
                    row[f"{s}_prop_assd"] = prop[s]
                rows.append(row)
    return pd.DataFrame(rows)


def mixed(formula: str, d: pd.DataFrame, extra_vc: dict | None = None):
    import statsmodels.formula.api as smf
    vc = {"annotator": "0 + C(annotator)", "image": "0 + C(image_id)"}
    if extra_vc:
        vc.update(extra_vc)
    m = smf.mixedlm(formula, d, groups="one", vc_formula=vc)
    return m.fit(reml=True, method="lbfgs")


def h1(df: pd.DataFrame, out: dict):
    d = df[df.n > 0].dropna(subset=["log_dur"]).copy()
    d["seed"] = d["seed"].fillna(-1).astype(int)
    r = mixed("log_dur ~ log2n + gaze_p + order_in_session + session_index + C(seed)", d)
    b, se = float(r.params["log2n"]), float(r.bse["log2n"])
    from scipy.stats import norm
    p_one = float(norm.cdf(b / se))
    out["H1"] = {"n_obs": int(len(d)), "slope_log2n": b, "se": se, "z": b / se, "p_one_sided": p_one,
                 "time_ratio_per_doubling": float(np.exp(b)),
                 "time_ratio_n128_vs_n1": float(np.exp(b * 7)), "fixed_effects": {k: float(v) for k, v in r.params.items()}}
    # saturation curve on per-n means (log scale): a + b*exp(-n/tau) vs a + b*log2(n)
    from scipy.optimize import curve_fit
    g = d.groupby("n")["log_dur"].mean()
    x, y = g.index.values.astype(float), g.values
    try:
        popt, _ = curve_fit(lambda n, a, b_, tau: a + b_ * np.exp(-n / tau), x, y, p0=[y.min(), y.max() - y.min(), 8.0], maxfev=20000)
        rss_exp = float(((y - (popt[0] + popt[1] * np.exp(-x / popt[2]))) ** 2).sum())
        lin = np.polyfit(np.log2(x), y, 1)
        rss_lin = float(((y - np.polyval(lin, np.log2(x))) ** 2).sum())
        k = len(y)
        out["H1"]["saturation"] = {"tau": float(popt[2]), "aic_exp": k * np.log(rss_exp / k) + 6,
                                   "aic_linear_log2n": k * np.log(rss_lin / k) + 4,
                                   "n90": float(-popt[2] * np.log(0.1)) if popt[2] > 0 else None}
    except Exception as e:  # noqa: BLE001
        out["H1"]["saturation"] = {"error": str(e)}


def h2(df: pd.DataFrame, deltas: dict, out: dict):
    from scipy.stats import norm
    z = norm.ppf(0.95)
    res = {}
    for s in STRUCTS:
        col = f"{s}_assd"
        d = df.dropna(subset=[col]).copy()
        d["cond"] = pd.Categorical(d["condition"], categories=["manual"] + [f"n{n}" for n in N_LEVELS])
        r = mixed(f"{col} ~ C(cond, Treatment('manual')) + gaze_p", d)
        seq, n_star = [], None
        for n in reversed(N_LEVELS):
            term = f"C(cond, Treatment('manual'))[T.n{n}]"
            est, se = float(r.params[term]), float(r.bse[term])
            ok = (est + z * se) < deltas[s]
            seq.append({"n": n, "diff_px": est, "se": se, "ci95_upper": est + z * se, "non_inferior": bool(ok)})
            if ok:
                n_star = n
            else:
                break            # fixed sequence stops at the first failure
        res[s] = {"delta_px": deltas[s], "sequence": seq, "n_star_noninferior_from": n_star,
                  "manual_mean_assd": float(d.loc[d.n == 0, col].mean())}
        for extra in ("dice", "hd95"):
            c2 = f"{s}_{extra}"
            if c2 in d:
                r2 = mixed(f"{c2} ~ C(cond, Treatment('manual')) + gaze_p", d.dropna(subset=[c2]))
                res[s][f"{extra}_diff_vs_manual"] = {f"n{n}": float(r2.params[f"C(cond, Treatment('manual'))[T.n{n}]"])
                                                     for n in N_LEVELS if f"C(cond, Treatment('manual'))[T.n{n}]" in r2.params}
    out["H2"] = res


def h3(df: pd.DataFrame, out: dict):
    res = {}
    man = df[df.n == 0].groupby("image_id")[[f"{s}_assd" for s in STRUCTS]].mean()
    for s in STRUCTS:
        d = df[df.n > 0].dropna(subset=[f"{s}_assd", f"{s}_prop_assd"]).copy()
        d["manual_assd_same_image"] = d["image_id"].map(man[f"{s}_assd"])
        f = f"{s}_assd ~ {s}_prop_assd + gaze_p"
        if d["manual_assd_same_image"].notna().sum() > 10:
            f += " + manual_assd_same_image"
            d = d.dropna(subset=["manual_assd_same_image"])
        r = mixed(f, d)
        res[s] = {"n_obs": int(len(d)), "slope_final_on_proposal": float(r.params[f"{s}_prop_assd"]),
                  "se": float(r.bse[f"{s}_prop_assd"]), "p": float(r.pvalues[f"{s}_prop_assd"])}
    out["H3_automation_bias"] = res


def novelty(df: pd.DataFrame, out: dict):
    d = df[df.n > 0].dropna(subset=["log_dur"]).copy()
    d["prop_assd_mean"] = d[[f"{s}_prop_assd" for s in STRUCTS]].mean(axis=1)
    d = d.dropna(subset=["prop_assd_mean"])
    d["seed"] = d["seed"].fillna(-1).astype(int)
    r_q = mixed("log_dur ~ prop_assd_mean + gaze_p + order_in_session + session_index", d)
    r_qn = mixed("log_dur ~ prop_assd_mean + log2n + gaze_p + order_in_session + session_index", d)
    r_n = mixed("log_dur ~ log2n + gaze_p + order_in_session + session_index", d)
    out["novelty_proposal_quality"] = {
        "n_obs": int(len(d)),
        "slope_log_dur_per_px_assd": float(r_q.params["prop_assd_mean"]), "se": float(r_q.bse["prop_assd_mean"]),
        "llf_quality_only": float(r_q.llf), "llf_n_only": float(r_n.llf), "llf_quality_plus_n": float(r_qn.llf),
        "log2n_slope_after_quality": float(r_qn.params["log2n"]), "log2n_se_after_quality": float(r_qn.bse["log2n"]),
    }


def descriptives(df: pd.DataFrame, gate_px: dict, out: dict):
    man = df[df.n == 0]
    out["manual_baseline_sec"] = man.groupby("annotator")["duration_sec"].median().to_dict()
    out["median_duration_by_n"] = df.groupby("n")["duration_sec"].median().to_dict()
    # inter-annotator agreement on manual items (images annotated manually by >= 2 annotators)
    agree = {}
    for s in STRUCTS:
        g = man.groupby("image_id")[f"{s}_assd"]
        agree[s] = {"images_with_2plus_manual": int((g.count() >= 2).sum()),
                    "assd_vs_gt_mean": float(man[f"{s}_assd"].mean()),
                    "assd_vs_gt_p90": float(man[f"{s}_assd"].quantile(0.9))}
    out["manual_vs_gt"] = agree
    fails = {}
    for s in STRUCTS:
        fails[s] = df.assign(fail=df[f"{s}_assd"] > gate_px[s]).groupby("n")["fail"].mean().round(3).to_dict()
    out["gate_failure_rate_by_n"] = fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "outputs" / "results"))
    ap.add_argument("--out", default=str(ROOT / "outputs" / "analysis"))
    ap.add_argument("--include-test", action="store_true", help="dry-run on the developer's test_* records")
    ap.add_argument("--last-attempt", action="store_true")
    ap.add_argument("--synthetic", action="store_true", help="exercise all models on a fake v2 dataset")
    ap.add_argument("--delta-eyelid", type=float, default=1.0, help="non-inferiority margin ASSD px")
    ap.add_argument("--delta-iris", type=float, default=1.0)
    ap.add_argument("--delta-pupil", type=float, default=1.0)
    ap.add_argument("--gate-eyelid", type=float, default=4.6, help="descriptive gate = 2x inter-rater ASSD")
    ap.add_argument("--gate-iris", type=float, default=4.6)
    ap.add_argument("--gate-pupil", type=float, default=4.6)
    args = ap.parse_args()
    if args.synthetic:
        df = synthetic()
        df["log_dur"] = np.log(df["duration_sec"]); df["log2n"] = np.log2(df["n"].where(df["n"] > 0, np.nan))
        df["gaze_p"] = (df["gaze"] == "peripheral").astype(int); df["one"] = 1
    else:
        df = load_results(Path(args.results), args.include_test, args.last_attempt)
    print(f"{len(df)} records, annotators={sorted(df.annotator.astype(str).unique())}, "
          f"n counts={df.n.value_counts().sort_index().to_dict()}")
    out: dict = {"n_records": int(len(df)), "annotators": sorted(df.annotator.astype(str).unique())}
    deltas = {"eyelid": args.delta_eyelid, "iris": args.delta_iris, "pupil": args.delta_pupil}
    gates = {"eyelid": args.gate_eyelid, "iris": args.gate_iris, "pupil": args.gate_pupil}
    for name, fn in (("descriptives", lambda: descriptives(df, gates, out)), ("H1", lambda: h1(df, out)),
                     ("H2", lambda: h2(df, deltas, out)), ("H3", lambda: h3(df, out)),
                     ("novelty", lambda: novelty(df, out))):
        try:
            fn()
            print(f"[ok] {name}")
        except Exception as e:  # noqa: BLE001 — a dry run on tiny data will hit singular fits
            out[f"{name}_error"] = repr(e)
            print(f"[skip] {name}: {e!r}"[:200])
    od = Path(args.out)
    od.mkdir(parents=True, exist_ok=True)
    tag = "_synthetic" if args.synthetic else ("_test" if args.include_test else "")
    (od / f"fit_models{tag}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    df.to_csv(od / f"records_used{tag}.csv", index=False)
    print(f"Wrote {od / f'fit_models{tag}.json'}")


if __name__ == "__main__":
    main()
