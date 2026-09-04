#!/usr/bin/env python3
"""fil-parity lint — T45's translation-parity gate (2026-08-26).

Scans every _t('en','fil') call site for IDENTICAL en/fil arguments — the
signature of a string that was ADDED to the EN branch without a Filipino
translation (my 2026-08-25 error-taxonomy sweep created exactly this debt:
new taxonomy strings landed EN-only inside _t() calls).

Not every identical pair is debt: proper nouns, codes, and ALL-CAPS tokens
("OK", "PM", "QR") legitimately read the same in both languages — those are
excluded by shape (short, or all caps/digits/punct). Everything else counts.

Forward-only ratchet: the count may only fall. Baseline stored inline in
fil_parity_baseline.json (created on first run with the measured count).

Usage: python tools/validate_fil_parity.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "fil_parity_baseline.json"

PAIR_RE = re.compile(r"_t\(\s*'((?:[^'\\]|\\.)*)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*\)")
# shapes that legitimately read the same in EN and FIL
EXEMPT_RE = re.compile(r"^[A-Z0-9 %./:+&()\-]*$")


def scan() -> list[tuple[str, str]]:
    hits = []
    files = sorted(glob.glob(str(ROOT / "*.html"))) + [str(ROOT / "utils.js"), str(ROOT / "nav-hub.js")]
    for f in files:
        try:
            s = io.open(f, encoding="utf-8").read()
        except OSError:
            continue
        for m in PAIR_RE.finditer(s):
            en, fil = m.group(1), m.group(2)
            if en == fil and len(en) > 3 and not EXEMPT_RE.fullmatch(en):
                hits.append((Path(f).name, en))
    return hits


def main() -> int:
    hits = scan()
    count = len(hits)
    per_file: dict[str, int] = {}
    for f, _ in hits:
        per_file[f] = per_file.get(f, 0) + 1
    for f, n in sorted(per_file.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {f}: {n}")
    if BASELINE.exists():
        base = json.loads(BASELINE.read_text(encoding="utf-8")).get("count", 0)
    else:
        BASELINE.write_text(json.dumps({"count": count, "established": "2026-08-26"}, indent=1), encoding="utf-8")
        print(f"BASELINE established: {count} identical en/fil pairs (forward-only; translate to shrink)")
        return 0
    if count > base:
        print(f"FAIL fil-parity — identical en/fil pairs GREW {base} -> {count}: new strings shipped without Filipino.")
        return 1
    if count < base:
        BASELINE.write_text(json.dumps({"count": count, "ratcheted": "auto"}, indent=1), encoding="utf-8")
        print(f"PASS fil-parity — improved {base} -> {count}; ratchet lowered.")
        return 0
    print(f"PASS fil-parity — held at {count} identical en/fil pairs (baseline {base}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
