#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D25
r"""
validate_redact_iso.py — regression guard for the PII-redaction ISO-timestamp
carve-out in supabase/functions/_shared/redactPII.ts.

WHY: PHONE_RE (`\+?\d[\d\s().-]{8,}\d`) is deliberately loose so it catches
PH mobile/landline shapes. But it ALSO eats the `YYYY-MM-DD` head of an ISO-8601
timestamp, so `2026-06-13T01:29:44` was redacted to `<phone>T01:29:44`. That leaked
through asset-brain answers once they routed through the ai-gateway (STREAMLINE
S7/A2). Fix = `scrubExceptISO(s, scrub)` carves ISO date/datetime substrings out
of the scrub pass entirely, wired into BOTH string paths (redactPII's redactString
and redactPIIWithMap's walk()).

WHAT THIS CHECKS (two layers, all deterministic, $0, no deno/DB/model):
  1. STRUCTURAL — `ISO_DATETIME_RE` + `scrubExceptISO` are defined, and
     scrubExceptISO is referenced in BOTH redaction string paths (so neither
     can silently regress to a raw `.replace(PHONE_RE, ...)`).
  2. BEHAVIORAL — extract the THREE real regex sources from the .ts file and
     re-run the carve-out in Python: ISO timestamps survive (5 shapes), real
     phones + emails still redact (the protection must not blind the scrubber).

Exit 0 = PASS, 1 = FAIL. No file is ever edited.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "supabase" / "functions" / "_shared" / "redactPII.ts"

GRN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def _extract_regex(src: str, name: str) -> str:
    """Pull the literal body of `const NAME = /.../flags;` (may span lines)."""
    m = re.search(rf"const\s+{name}\s*=\s*/(.+?)/[gimsuy]*\s*;", src, re.DOTALL)
    if not m:
        raise ValueError(f"{name} not found in redactPII.ts")
    # Collapse the line-continuation whitespace the TS pretty-printer may add.
    return m.group(1)


def _scrub_except_iso(s, email_re, phone_re, iso_re):
    """Python mirror of scrubExceptISO: scrub only the gaps BETWEEN ISO dates."""
    out, last = [], 0
    for m in iso_re.finditer(s):
        gap = phone_re.sub("<phone>", email_re.sub("<email>", s[last:m.start()]))
        out.append(gap)
        out.append(m.group(0))
        last = m.end()
    tail = phone_re.sub("<phone>", email_re.sub("<email>", s[last:]))
    out.append(tail)
    return "".join(out)


def main() -> int:
    if not SRC.exists():
        print(f"{RED}FAIL{RST} redactPII.ts not found at {SRC}")
        return 1
    src = SRC.read_text(encoding="utf-8")
    fails = []

    # ---- Layer 1: structural ------------------------------------------------
    if "ISO_DATETIME_RE" not in src:
        fails.append("ISO_DATETIME_RE constant missing")
    if "function scrubExceptISO" not in src:
        fails.append("scrubExceptISO helper missing")
    # Both string paths must route through scrubExceptISO. redactString is the
    # bare-redactPII path; the walk() arm is the redactPIIWithMap path.
    refs = src.count("scrubExceptISO(")
    # one definition call-site `function scrubExceptISO` is NOT counted by the
    # `(` form above only if it's `function scrubExceptISO(`; subtract it.
    invocations = refs - src.count("function scrubExceptISO(")
    if invocations < 2:
        fails.append(
            f"scrubExceptISO invoked {invocations}x; expected >=2 "
            "(redactString + walk paths)")

    # ---- Layer 2: behavioral (using the REAL extracted regexes) -------------
    try:
        email_re = re.compile(_extract_regex(src, "EMAIL_RE"))
        phone_re = re.compile(_extract_regex(src, "PHONE_RE"))
        iso_re = re.compile(_extract_regex(src, "ISO_DATETIME_RE"))
    except (ValueError, re.error) as e:
        print(f"{RED}FAIL{RST} could not extract/compile regexes: {e}")
        return 1

    keep = [  # ISO timestamps that must survive verbatim
        ("as of 2026-06-13T01:29:44 today", "T-separated"),
        ("snapshot 2026-06-13 here", "bare date"),
        ("logged 2026-06-13 01:29:44 PHT", "space-separated"),
        ("tz 2026-06-13T01:29:44.500Z end", "fractional+Z"),
        ("off 2026-06-13T01:29:44+08:00 end", "tz offset"),
    ]
    redact = [  # real PII that must still be scrubbed
        ("call +63 917 123 4567 now", "call <phone> now", "intl phone"),
        ("mobile 09171234567 ok", "mobile <phone> ok", "local phone"),
        ("email jane@workhive.ph here", "email <email> here", "email"),
        ("mix 2026-06-13T01:29:44 ring +63 917 123 4567",
         "mix 2026-06-13T01:29:44 ring <phone>", "ts kept + phone redacted"),
    ]
    for inp, label in keep:
        got = _scrub_except_iso(inp, email_re, phone_re, iso_re)
        if got != inp:
            fails.append(f"ISO not preserved [{label}]: {inp!r} -> {got!r}")
    for inp, want, label in redact:
        got = _scrub_except_iso(inp, email_re, phone_re, iso_re)
        if got != want:
            fails.append(f"PII not redacted [{label}]: {inp!r} -> {got!r} (want {want!r})")

    # ---- verdict ------------------------------------------------------------
    if fails:
        print(f"{RED}FAIL{RST} validate_redact_iso — {len(fails)} issue(s):")
        for f in fails:
            print(f"  {RED}-{RST} {f}")
        return 1
    print(f"{GRN}PASS{RST} validate_redact_iso — ISO timestamps carved out of "
          f"PII scrub; phones/emails still redact ({len(keep)} keep + {len(redact)} redact cases).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
