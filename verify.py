#!/usr/bin/env python3
"""Check the Upfront Investment picks ledger for yourself.

Every set of picks The Upfront Model publishes is recorded the day it goes out, fingerprinted
with SHA-256, and chained to the entry before it. Holdings open 30 days later. This script
downloads the public ledger and checks two things, with nothing to trust but the arithmetic:

  1. The chain: every entry's prev_sha256 equals the sha256 of the entry before it.
  2. The fingerprints: for every entry whose holdings are open, recompute
        sha256(prev_sha256 + "\\n" + payload)
     and compare it with the published sha256. If the payload had been edited after the
     fact, this would not match, and every fingerprint after it would break too.

Usage:
    python3 verify.py                 # checks the live ledger
    python3 verify.py ledger.json     # checks a saved copy (from /api/model/ledger)

No dependencies beyond the Python standard library.
"""
import hashlib
import json
import sys
import urllib.request

LEDGER_URL = "https://www.upfrontinvestment.com/api/model/ledger"


def load(source):
    if source and source != "-":
        with open(source, encoding="utf-8") as f:
            return json.load(f)
    with urllib.request.urlopen(LEDGER_URL, timeout=30) as r:
        return json.load(r)


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify(ledger):
    entries = ledger["entries"]
    problems = []
    prev = ""
    for i, e in enumerate(entries, 1):
        # 1. chain
        if e["prev_sha256"] != prev:
            problems.append(f"entry {i} ({e['book_date']}): prev_sha256 does not match the previous entry")
        # 2. fingerprint, when the holdings are open
        if e.get("revealed"):
            recomputed = sha256_hex(e["prev_sha256"] + "\n" + e["payload"])
            if recomputed != e["sha256"]:
                problems.append(f"entry {i} ({e['book_date']}): recomputed sha256 {recomputed[:16]}… "
                                f"differs from the published {e['sha256'][:16]}…")
        prev = e["sha256"]
    return problems


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else None
    ledger = load(source)
    entries = ledger["entries"]
    print(f"Ledger rule: {ledger.get('hash_rule')}")
    print(f"Holdings open after {ledger.get('reveal_after_days')} days\n")
    for e in entries:
        state = "open, fingerprint recomputed" if e.get("revealed") else f"sealed until {e['reveals_on']}"
        print(f"  {e['book_date']}  {e['sha256'][:16]}…  {e['n_positions']:>3} positions  {state}")
    problems = verify(ledger)
    print()
    if problems:
        for p in problems:
            print("FAIL", p)
        sys.exit(1)
    opened = sum(1 for e in entries if e.get("revealed"))
    print(f"OK: {len(entries)} entries, chain intact, {opened} fingerprint(s) recomputed and matching.")


if __name__ == "__main__":
    main()
