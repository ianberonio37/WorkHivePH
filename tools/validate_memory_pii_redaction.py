#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D25
r"""
validate_memory_pii_redaction.py — regression guard for the MULTI-TURN PII egress
rail in the ai-gateway (K2, live-caught 2026-07-12).

WHY: the current-turn message + context are fully scrubbed by redactPIIWithMap
(email/phone -> <email_N>/<phone_N>), but a worker who stated an EMAIL or PHONE in
a PRIOR turn has that value carried verbatim in the agent_memory turn_text AND the
semantic journal recall. The forwarded `memory_block` and the summariser transcript
were scrubbed ONLY by redactKnownNames (worker FULL-NAMES), so those emails/phones
reached the model provider RAW. Live-proven: `pii.leak.test@plant.ph` + a PH mobile
survived twice in the forwarded memory_block. Fix = `redactMemoryText(text, names)`
(names via redactKnownNames + email/phone via the same scrubExceptISO/EMAIL_RE/PHONE_RE
as the single-turn path, in a distinct <mem*_N> hydration namespace), wired into BOTH
egress sites in ai-gateway/index.ts.

WHAT THIS CHECKS (structural + behavioral, all deterministic, $0, no deno/DB/model):
  1. STRUCTURAL (redactPII.ts) — `export function redactMemoryText` exists and its
     body references redactKnownNames + scrubExceptISO + EMAIL_RE + PHONE_RE, so it
     can never silently degrade to a NAME-ONLY stub (which would reopen the leak).
  2. STRUCTURAL (ai-gateway/index.ts) — BOTH the forwarded memory_block AND the
     summariser transcript are scrubbed by redactMemoryText(...), and NEITHER site
     regresses to a bare redactKnownNames(memory_block / transcript, ...) call.
  3. BEHAVIORAL — extract the real EMAIL_RE / PHONE_RE / ISO_DATETIME_RE sources from
     redactPII.ts and re-run the memory scrub in Python on a memory-shaped block:
     the stated email + PH mobile are redacted, and an ISO timestamp survives
     (the carve-out must not blind the scrubber and must not eat the date).

Exit 0 = PASS, 1 = FAIL. No file is ever edited.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REDACT = ROOT / "supabase" / "functions" / "_shared" / "redactPII.ts"
GATEWAY = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"

GRN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

fails: list[str] = []
passes: list[str] = []


def _extract_regex(src: str, name: str) -> str:
    m = re.search(rf"const\s+{name}\s*=\s*/(.+?)/[gimsuy]*\s*;", src, re.DOTALL)
    if not m:
        raise ValueError(f"{name} not found in redactPII.ts")
    return m.group(1)


def _extract_fn_body(src: str, name: str) -> str:
    """Return the source of `export function NAME(...)` from its declaration up to
    the NEXT top-level function declaration. Slicing to the next `function` boundary
    (rather than brace-matching) avoids the return-type-annotation brace trap:
    `): { redacted: string; ... } {` would otherwise close on the return type, not
    the body. Whole-function slice is sufficient for token-presence checks."""
    start = src.find(f"export function {name}")
    if start == -1:
        return ""
    rest = src[start + len(f"export function {name}"):]
    m = re.search(r"\n(?:export\s+)?function\s", rest)
    end = m.start() if m else len(rest)
    return rest[:end]


def main() -> int:
    if not REDACT.exists():
        print(f"{RED}FAIL{RST} redactPII.ts not found at {REDACT}")
        return 1
    if not GATEWAY.exists():
        print(f"{RED}FAIL{RST} ai-gateway/index.ts not found at {GATEWAY}")
        return 1

    rsrc = REDACT.read_text(encoding="utf-8")
    gsrc = GATEWAY.read_text(encoding="utf-8")

    # ---- 1. STRUCTURAL: redactMemoryText exists + is not a name-only stub --------
    body = _extract_fn_body(rsrc, "redactMemoryText")
    if not body:
        fails.append("redactPII.ts: `export function redactMemoryText` is MISSING "
                     "(the multi-turn memory scrubber that adds email/phone on top of names)")
    else:
        for tok in ("redactKnownNames", "scrubExceptISO", "EMAIL_RE", "PHONE_RE"):
            if tok not in body:
                fails.append(f"redactMemoryText body no longer references `{tok}` — it may have "
                             f"degraded to a NAME-ONLY stub, reopening the email/phone memory leak")
        if not fails:
            passes.append("redactMemoryText present + scrubs names AND email/phone (scrubExceptISO)")

    # ---- 2. STRUCTURAL: BOTH gateway egress sites use redactMemoryText -----------
    # memory_block forward
    if re.search(r"redactMemoryText\s*\(\s*memory_block", gsrc):
        passes.append("ai-gateway: forwarded memory_block scrubbed by redactMemoryText(memory_block, ...)")
    else:
        fails.append("ai-gateway: forwarded memory_block is NOT scrubbed by redactMemoryText(memory_block, ...) "
                     "— multi-turn email/phone would leak to the specialist LLM")
    if re.search(r"redactKnownNames\s*\(\s*memory_block", gsrc):
        fails.append("ai-gateway: memory_block still uses the WEAKER redactKnownNames(memory_block, ...) "
                     "(names only) — regression: use redactMemoryText")

    # summariser transcript
    if re.search(r"redactMemoryText\s*\(\s*transcript", gsrc):
        passes.append("ai-gateway: summariser transcript scrubbed by redactMemoryText(transcript, ...)")
    else:
        fails.append("ai-gateway: summariser transcript is NOT scrubbed by redactMemoryText(transcript, ...) "
                     "— an earlier-stated email/phone would reach the summariser model AND bake into the summary row")
    if re.search(r"redactKnownNames\s*\(\s*transcript", gsrc):
        fails.append("ai-gateway: summariser transcript still uses the WEAKER redactKnownNames(transcript, ...) "
                     "(names only) — regression: use redactMemoryText")

    # ---- 3. BEHAVIORAL: re-run the scrub from the real regex sources -------------
    try:
        email_re = re.compile(_extract_regex(rsrc, "EMAIL_RE"))
        phone_re = re.compile(_extract_regex(rsrc, "PHONE_RE"))
        iso_re = re.compile(_extract_regex(rsrc, "ISO_DATETIME_RE"))

        def scrub_except_iso(s: str) -> str:
            out, last = [], 0
            for m in iso_re.finditer(s):
                gap = phone_re.sub("<memphone>", email_re.sub("<mememail>", s[last:m.start()]))
                out.append(gap)
                out.append(m.group(0))
                last = m.end()
            out.append(phone_re.sub("<memphone>", email_re.sub("<mememail>", s[last:])))
            return "".join(out)

        sample = ("Recent turns:\nWorker: For the report (logged 2026-07-12T09:44:25), my "
                  "contact email is pii.leak.test@plant.ph and my mobile is +63 917 555 0199.")
        scrubbed = scrub_except_iso(sample)
        if "pii.leak.test@plant.ph" in scrubbed:
            fails.append("BEHAVIORAL: a memory-block email survived the scrub (email leak)")
        elif "555 0199" in scrubbed or "5550199" in scrubbed:
            fails.append("BEHAVIORAL: a memory-block PH mobile survived the scrub (phone leak)")
        elif "2026-07-12T09:44:25" not in scrubbed:
            fails.append("BEHAVIORAL: the ISO timestamp was eaten by the scrub (carve-out regressed)")
        else:
            passes.append("BEHAVIORAL: memory email+phone redacted, ISO timestamp preserved")
    except Exception as e:  # noqa: BLE001
        fails.append(f"BEHAVIORAL: could not re-run the scrub from redactPII.ts regexes: {e}")

    # ---- verdict ----------------------------------------------------------------
    for p in passes:
        print(f"{GRN}PASS{RST} {p}")
    for f in fails:
        print(f"{RED}FAIL{RST} {f}")
    if fails:
        print(f"\n{RED}validate_memory_pii_redaction: {len(fails)} FAIL{RST}")
        return 1
    print(f"\n{GRN}validate_memory_pii_redaction: multi-turn PII egress rail intact "
          f"({len(passes)} checks){RST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
