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
    python3 verify.py --repo          # also compares the live ledger with the copies in ledger/

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
    try:
        with urllib.request.urlopen(LEDGER_URL, timeout=30) as r:
            return json.load(r)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            sys.exit("Your Python cannot verify HTTPS certificates (common with python.org builds on macOS).\n"
                     f"Save the ledger with:  curl -s {LEDGER_URL} > ledger.json\n"
                     "then run:              python3 verify.py ledger.json")
        raise


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify(ledger):
    entries = ledger["entries"]
    problems = []
    prev = ""
    for i, e in enumerate(entries, 1):
        # The API sends null for the first entry's prev_sha256; the hash rule treats it as "".
        prev_field = e["prev_sha256"] or ""
        # 1. chain
        if prev_field != prev:
            problems.append(f"entry {i} ({e['book_date']}): prev_sha256 does not match the previous entry")
        # 2. fingerprint, when the holdings are open
        if e.get("revealed"):
            recomputed = sha256_hex(prev_field + "\n" + e["payload"])
            if recomputed != e["sha256"]:
                problems.append(f"entry {i} ({e['book_date']}): recomputed sha256 {recomputed[:16]}… "
                                f"differs from the published {e['sha256'][:16]}…")
        prev = e["sha256"]
    return problems


def compare_with_repo(ledger, folder="ledger"):
    """Fingerprints in the live ledger must match the committed copies here, file by file."""
    import os

    problems = []
    for e in ledger["entries"]:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder, f"{e['book_date']}.json")
        if not os.path.exists(path):
            problems.append(f"{e['book_date']}: no copy in {folder}/ yet")
            continue
        with open(path, encoding="utf-8") as f:
            copy = json.load(f)
        for key in ("sha256", "prev_sha256"):
            if copy.get(key) != e.get(key):
                problems.append(f"{e['book_date']}: {key} differs between the live ledger and {folder}/")
        if copy.get("payload") and e.get("payload") and copy["payload"] != e["payload"]:
            problems.append(f"{e['book_date']}: payload differs between the live ledger and {folder}/")
    return problems


def main():
    args = [a for a in sys.argv[1:] if a != "--repo"]
    source = args[0] if args else None
    ledger = load(source)
    entries = ledger["entries"]
    print(f"Ledger rule: {ledger.get('hash_rule')}")
    print(f"Holdings open after {ledger.get('reveal_after_days')} days\n")
    for e in entries:
        state = "open, fingerprint recomputed" if e.get("revealed") else f"sealed until {e['reveals_on']}"
        print(f"  {e['book_date']}  {e['sha256'][:16]}…  {e['n_positions']:>3} positions  {state}")
    problems = verify(ledger)
    if "--repo" in sys.argv:
        problems += compare_with_repo(ledger)
    print()
    if problems:
        for p in problems:
            print("FAIL", p)
        sys.exit(1)
    opened = sum(1 for e in entries if e.get("revealed"))
    print(f"OK: {len(entries)} entries, chain intact, {opened} fingerprint(s) recomputed and matching.")


if __name__ == "__main__":
    main()
