"""Generate / list each annotator's personal link for the HITL webapp.

Each real annotator gets one random token (stored in
scripts/webapp/config/annotator_tokens.json, git-ignored). The webapp maps the
token to the annotator on the server, so annotators never pick their ID from a
list: a wrong / mistyped link is rejected instead of running someone else's
assignment. Existing tokens are kept (links stay valid); only annotators without
a token get a new one. Restart the server after adding tokens.

Run:  python scripts/make_annotator_links.py [--base-url https://xxxxx.trycloudflare.com]
      python scripts/make_annotator_links.py --revoke kubota   # issue a fresh token
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "webapp" / "backend"))
from config import TOKENS_JSON, load_experiment, load_tokens  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000",
                    help="public URL of the server (the trycloudflare URL changes on every restart)")
    ap.add_argument("--revoke", nargs="*", default=[],
                    help="annotators whose current token is discarded and reissued")
    args = ap.parse_args()

    annotators = load_experiment().get("annotators", [])
    unknown = sorted(set(args.revoke) - set(annotators))
    if unknown:
        raise SystemExit(f"unknown annotator(s): {unknown}  (known: {annotators})")

    tokens = {t: a for t, a in load_tokens().items() if a not in args.revoke}
    have = set(tokens.values())
    new = [a for a in annotators if a not in have]
    for a in new:
        tokens[secrets.token_urlsafe(12)] = a
    if new:
        TOKENS_JSON.write_text(json.dumps(tokens, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        print(f"[tokens] issued for {new} -> {TOKENS_JSON}  (restart the server)")

    by_name = {a: t for t, a in tokens.items()}
    base = args.base_url.rstrip("/")
    print("\nPersonal links (send each one ONLY to that annotator):")
    for a in annotators:
        print(f"  {a:<12} {base}/?t={by_name[a]}")
    print("\nDeveloper (excluded from analysis):")
    print(f"  {'test':<12} {base}/?t=test")


if __name__ == "__main__":
    main()
