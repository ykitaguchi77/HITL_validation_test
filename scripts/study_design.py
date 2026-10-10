"""Design parameters shared by select_study_images.py and prepare_experiment.py.

Dose-response n-shot design: every annotator sees every condition slot once
per session. Slots = the 8 n-levels (n = 1,2,4,...,128 fixed LoRA checkpoints)
plus k manual (n = 0) slots. Images are partitioned into S groups of G; annotator
a works group g under slot[(g + step*a) mod S] with step = S / A, so the A
annotators see each image under A distinct slots. Every image is annotated
manually exactly k*A/S times, which must be an integer -> S is the smallest
multiple of A (> 8) satisfying that.

  A=6 -> S=12 (k=4), each image manual by 2 annotators, 60 imgs/annotator @ G=5
  A=5 -> S=10 (k=2), manual x1,                          60 imgs/annotator @ G=6
  A=3 -> S=12 (k=4), manual x1,                         120 imgs/annotator @ G=10
Sessions hold SESSION_SIZE (10) images; when S > 10 the surplus slots are omitted
in rotation (see session_slots) so every session still mixes conditions evenly.
"""
from __future__ import annotations

N_LEVELS = [1, 2, 4, 8, 16, 32, 64, 128]
SEEDS = [0, 1, 2]                 # training-order seeds (fixed checkpoints)
MANUAL = "manual"
# default group size (images per condition per annotator) keyed by annotator count
_DEFAULT_G = {3: 10, 5: 6, 6: 5}


def slot_key(n: int) -> str:
    return MANUAL if n == 0 else f"n{n}"


SESSION_SIZE = 10                 # images per session (annotator fatigue; 12 was too long)


def design_params(n_annotators: int, group_size: int | None = None,
                  session_size: int = SESSION_SIZE) -> dict:
    A = n_annotators
    S = None
    for cand in range(A * ((8 // A) + 1), 8 * A + 1, A):   # multiples of A, > 8
        k = cand - len(N_LEVELS)
        if (k * A) % cand == 0:
            S, k_manual = cand, k
            break
    if S is None:
        raise ValueError(f"no slot count works for {A} annotators")
    G = group_size or _DEFAULT_G.get(A)
    if not G:
        raise ValueError(f"group_size required for {A} annotators")
    n_p = int(G * 0.3 + 0.5)          # peripheral per group (5->2, 6->2, 10->3)
    n_f = G - n_p
    slots = [slot_key(n) for n in N_LEVELS] + [MANUAL] * k_manual
    P = session_size
    if (S * G) % P:
        raise ValueError(f"session_size {P} does not divide {S * G} images")
    n_sessions = S * G // P
    if n_sessions < G or (S * (n_sessions - G)) % n_sessions:
        raise ValueError(f"cannot omit slots evenly: S={S} G={G} sessions={n_sessions}")
    return {
        "n_annotators": A, "n_slots": S, "n_manual_slots": k_manual, "step": S // A,
        "group_size": G, "n_frontal_per_group": n_f, "n_peripheral_per_group": n_p,
        "n_study_images": S * G, "n_study_frontal": S * n_f, "n_study_peripheral": S * n_p,
        "images_per_annotator": S * G, "manual_per_annotator": k_manual * G,
        "manual_per_image": k_manual * A // S, "slots": slots,
        "session_size": P, "n_sessions": n_sessions, "omit_per_session": S - P,
        "n_levels": list(N_LEVELS), "seeds": list(SEEDS),
    }


def session_slots(p: dict, a: int = 0) -> list[list[int]]:
    """Which slot indices each session contains (before session-order shuffling).

    A session holds session_size images = one image of each of session_size
    distinct slots; the S - session_size omitted slots rotate cyclically over an
    interleaved slot order (manual slots spread among the n-levels), so every
    slot is omitted equally often (n_sessions - G times) and the manual count per
    session differs by at most 1. The n-level order is rotated by annotator a so
    the n paired with a manual omission varies across annotators.
    """
    S, P, n_sess = p["n_slots"], p["session_size"], p["n_sessions"]
    n_idx = [i for i, sl in enumerate(p["slots"]) if sl != MANUAL]
    m_idx = [i for i, sl in enumerate(p["slots"]) if sl == MANUAL]
    r = a % len(n_idx)
    n_idx = n_idx[r:] + n_idx[:r]
    # interleave: after every len(n)/len(m) n-slots insert one manual slot
    order, mi = [], 0
    stride = max(1, len(n_idx) // max(1, len(m_idx)))
    for j, i in enumerate(n_idx):
        order.append(i)
        if m_idx and mi < len(m_idx) and (j + 1) % stride == 0:
            order.append(m_idx[mi]); mi += 1
    order += m_idx[mi:]
    omit = S - P
    out = []
    for s in range(n_sess):
        omitted = {order[(s * omit + t) % S] for t in range(omit)}
        out.append([i for i in range(S) if i not in omitted])
    return out


def slot_of(a: int, g: int, p: dict) -> str:
    """Condition slot for annotator index a and group index g."""
    return p["slots"][(g + p["step"] * a) % p["n_slots"]]


if __name__ == "__main__":
    for A in (3, 5, 6):
        p = design_params(A)
        print(A, {k: v for k, v in p.items() if k not in ("slots", "n_levels", "seeds")})
        ss = session_slots(p)
        print("   sessions:", [len(x) for x in ss], "manual/session:",
              [sum(p["slots"][i] == MANUAL for i in x) for x in ss])
