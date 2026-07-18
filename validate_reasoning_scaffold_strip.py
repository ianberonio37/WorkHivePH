"""
Reasoning-scaffold strip gate (AI Companion arc, 2026-07-13)
===========================================================
voice_family_probe caught the companion leaking its persona/chain-of-thought scaffold
verbatim into replies ("We need to respond as Zaniah, strategist, in English, short 1-3
sentences... The worker says:...") — a free-tier model narrating its PLAN as bare prose
with NO <think> tags, so the existing tag-strip missed it. Fix = Case 3 in
_shared/ai-chain.ts stripReasoningBlocks (+ Python mirrors), returning "" so callAI
falls to the next model.

THIS gate is the forward-only teeth: it proves the deterministic strip still
  (1) STRIPS the untagged persona-scaffold leak corpus to "" (→ next model), and
  (2) SPARES real answers (incl. ones that mention a persona name or "we should ..."),
and that the TS + both Python mirrors keep the Case-3 signature (no silent drift).

Cost: $0, hermetic (no network, no LLM) — pure-function + source-marker checks.
Usage:  python validate_reasoning_scaffold_strip.py
Skills: ai-engineer (reasoning-leak), qa (teeth on the strip), security (no scaffold egress).
"""
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools" / "lib"))

# Leaks that MUST strip to "" (verbatim shapes voice_family_probe surfaced + variants).
LEAKS = [
    'We need to respond as Zaniah, strategist, in English, short 1-3 sentences, reacting, '
    'summarizing pattern, quoting KPIs verbatim, using thresholds, trade-off thinking. The worker says: "Ple',
    'We need to respond as Zaniah: strategic, calm, sisterly PH English, short 1-3 sentences. '
    'We need to give a quick status of whole plant: we have snapshot data? The memory block includes...',
    'We need to respond as Hezekiah, the technician, in English, short 1-3 sentences. The worker says: fix the pump',
    "Let me respond as the strategist: I should quote KPIs verbatim and use the snapshot data...",
]
# Real answers that MUST be preserved (persona name / "we should" / status must NOT trip it).
REALS = [
    "I don't have specific repair instructions for a seal issue in my records. Check the Asset Hub or the Logbook.",
    "Logging a breakdown on pump P-001 due to bearing failure. Better get this documented right away.",
    "We should replace the throat bush and inspect the seal for wear — the usual root cause on a slurry pump.",
    "Zaniah here. Your MTBF on P-203 is 14 days, slightly behind the PH median. I'd prioritise the bearing inspection.",
    "Let me give you the status: 1 alert, 30 assets, 1 overdue PM. OEE is 86%.",
    "I can't directly place orders or process payments from here; those need supervisor approval.",
]
# The <think>-tag cases must still work.
THINK = [("<think>internal deliberation</think>The pump needs a new seal.", "The pump needs a new seal."),
         ("<think>unclosed truncated reasoning with no answer", "")]

TS = ROOT / "supabase" / "functions" / "_shared" / "ai-chain.ts"
PY_MIRRORS = [ROOT / "tools" / "lib" / "ai_chain.py", ROOT / "tools" / "ai_chain.py"]


def main() -> int:
    print("\033[1m\nReasoning-scaffold strip gate (AI Companion arc)\033[0m")
    print("=" * 52)
    fails = []

    # 1. pure-function behaviour (single source: tools/lib/ai_chain.py)
    try:
        from ai_chain import _strip_reasoning_blocks as strip
    except Exception as e:
        print(f"\033[91m  FAIL  cannot import _strip_reasoning_blocks: {e}\033[0m")
        return 1
    for t in LEAKS:
        if strip(t) != "":
            fails.append(f"LEAK not stripped: {t[:55]!r}")
    for t in REALS:
        if strip(t).strip() == "" or "respond as" in strip(t).lower():
            fails.append(f"REAL over-stripped: {t[:55]!r}")
    for src, want in THINK:
        if strip(src) != want:
            fails.append(f"THINK case: strip({src[:30]!r}) != {want[:30]!r}")

    # 2. source parity — TS keeps the Case-3 signature (no silent drift)
    ts = TS.read_text(encoding="utf-8") if TS.exists() else ""
    for marker in ("Case 3", "startsWithPlan", "hasScaffoldMeta"):
        if marker not in ts:
            fails.append(f"TS ai-chain.ts missing Case-3 marker: {marker}")
    # 3. both Python mirrors invoke the shared strip
    for p in PY_MIRRORS:
        txt = p.read_text(encoding="utf-8") if p.exists() else ""
        if "_strip_reasoning_blocks" not in txt:
            fails.append(f"Python mirror does not call _strip_reasoning_blocks: {p.name}")

    if fails:
        print(f"\033[91m  FAIL  ({len(fails)})\033[0m")
        for f in fails[:12]:
            print(f"        - {f}")
        return 1
    print(f"\033[92m  PASS\033[0m  strips {len(LEAKS)} scaffold-leaks + {len(THINK)} think-cases, "
          f"spares {len(REALS)} real answers; TS + {len(PY_MIRRORS)} Python mirrors keep the Case-3 strip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
