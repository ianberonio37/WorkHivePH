"""
AI Companion Intelligence Validator (turns #25-#34)
====================================================
Forward-only L0 ratchet for the third 10-turn flywheel batch (2026-05-21).
Different dimension again — covers CONTEXT AWARENESS (shift, worker
discipline, repeated issues, standards), VOICE COMMANDS (shortcuts +
goodbye), CONFIDENCE CALIBRATION (hedge on small samples), SESSION
PACING (long-session nudge), ALERTS PRIORITIZATION (override on
critical), and QUALITY FEEDBACK (thumbs UI + rating persist).

  T25  Time-aware shift context anchor
  T26  Repeated-issue surface helper + prompt injection
  T27  Standards lookup detector + anchor
  T28  Voice command shortcuts (open <page>)
  T29  AI quality thumbs feedback (UI + persist)
  T30  Worker-discipline biasing anchor
  T31  Goodbye / wrap-up detector
  T32  Confidence calibration anchor
  T33  Long-session pacing anchor
  T34  Proactive alerts override anchor

10-layer audit.
"""

from __future__ import annotations

import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


def check_shift_context(c: str) -> list[dict]:
    """T25 — SHIFT CONTEXT anchor + PH timezone offset."""
    if "SHIFT CONTEXT" not in c:
        return [{"check": "shift_context",
                 "reason": "SHIFT CONTEXT anchor missing — replies don't match time-of-day, night-shift workers get morning-energy openers."}]
    if "phHour" not in c and "getUTCHours" not in c:
        return [{"check": "shift_context",
                 "reason": "Shift derivation does not use UTC+8 math — falls back to device timezone which is wrong for workers on the road."}]
    return []


def check_repeated_issue_surface(c: str) -> list[dict]:
    """T26 — _fetchRepeatedIssueFlag exists and is invoked + queries v_logbook_truth."""
    issues: list[dict] = []
    if "_fetchRepeatedIssueFlag" not in c:
        issues.append({"check": "repeated_issue_surface",
                       "reason": "_fetchRepeatedIssueFlag missing — chronic machines (≥3 corrective in 30d) never surface to the LLM."})
    if "_fetchRepeatedIssueFlag(db" not in c:
        issues.append({"check": "repeated_issue_surface",
                       "reason": "Call site does not invoke _fetchRepeatedIssueFlag — helper exists but is never called."})
    if "v_logbook_truth" not in c:
        issues.append({"check": "repeated_issue_surface",
                       "reason": "Helper does not query v_logbook_truth — must use the canonical view, not raw table."})
    if "REPEATED ISSUES" not in c:
        issues.append({"check": "repeated_issue_surface",
                       "reason": "Anchor text 'REPEATED ISSUES' missing — LLM has no instruction to surface chronic machines."})
    return issues


def check_standards_lookup(c: str) -> list[dict]:
    """T27 — _detectStandardsMention + STANDARDS QUERY anchor."""
    issues: list[dict] = []
    if "_detectStandardsMention" not in c:
        issues.append({"check": "standards_lookup",
                       "reason": "_detectStandardsMention missing — ISO/SAE/SMRP mentions in transcript don't trigger standards-aware grounding."})
    if "_STANDARDS_RE" not in c:
        issues.append({"check": "standards_lookup",
                       "reason": "_STANDARDS_RE regex missing — vocabulary detector has no pattern."})
    # Regex must cover ISO + SAE + SMRP at minimum.
    m = re.search(r"_STANDARDS_RE\s*=\s*/([^/]+)/", c)
    if m:
        body = m.group(1).upper()
        for kw in ("ISO", "SAE", "SMRP"):
            if kw not in body:
                issues.append({"check": "standards_lookup",
                               "reason": f"_STANDARDS_RE doesn't include {kw} — workers reference this standard regularly."})
    if "STANDARDS QUERY" not in c:
        issues.append({"check": "standards_lookup",
                       "reason": "STANDARDS QUERY anchor missing — detection happens but the LLM gets no instruction to use industry_standards_chunks."})
    return issues


def check_voice_shortcut(c: str) -> list[dict]:
    """T28 — _isVoiceShortcut + _VOICE_SHORTCUT_MAP + call-site nav."""
    issues: list[dict] = []
    for sym in ("_isVoiceShortcut", "_VOICE_SHORTCUT_MAP"):
        if sym not in c:
            issues.append({"check": "voice_shortcut",
                           "reason": f"{sym} missing — direct nav requests ('open logbook') run through the LLM unnecessarily."})
    # Required shortcut keys (must cover the streak-ceiling answer set).
    if "_VOICE_SHORTCUT_MAP" in c:
        m = re.search(r"_VOICE_SHORTCUT_MAP\s*=\s*\{([^}]+)\}", c, re.DOTALL)
        if m:
            body = m.group(1).lower()
            for need in ("open logbook", "open analytics", "open inventory"):
                if need not in body:
                    issues.append({"check": "voice_shortcut",
                                   "reason": f"_VOICE_SHORTCUT_MAP missing '{need}' — common navigation phrase ignored."})
    if "window.location.href = shortcutTarget" not in c:
        issues.append({"check": "voice_shortcut",
                       "reason": "Call site does not navigate to shortcutTarget — detector fires but no page-swap happens."})
    return issues


def check_quality_feedback(c: str) -> list[dict]:
    """T29 — _recordReplyRating + thumbs UI in reply bubble + ai_cost_log target."""
    issues: list[dict] = []
    if "_recordReplyRating" not in c:
        issues.append({"check": "quality_feedback",
                       "reason": "_recordReplyRating missing — thumbs feedback has no persistence path."})
    if "data-rate" not in c:
        issues.append({"check": "quality_feedback",
                       "reason": "Reply bubble has no data-rate buttons — workers can't rate replies in one tap."})
    if "ai_cost_log" not in c and "record_ai_reply_rating" not in c:
        issues.append({"check": "quality_feedback",
                       "reason": "Rating helper does not target ai_cost_log (direct UPDATE) or record_ai_reply_rating (RPC) — ratings vanish."})
    if "quality_rating" not in c:
        issues.append({"check": "quality_feedback",
                       "reason": "Rating helper does not write to a quality_rating field — ratings would be uncorrelated with the cost-log row."})
    return issues


def check_discipline_biasing(c: str) -> list[dict]:
    """T30 — WORKER DISCIPLINE anchor + workerDiscipline variable."""
    if "WORKER DISCIPLINE" not in c:
        return [{"check": "discipline_biasing",
                 "reason": "WORKER DISCIPLINE anchor missing — electrical workers get mechanical examples and vice versa."}]
    if "workerDiscipline" not in c:
        return [{"check": "discipline_biasing",
                 "reason": "workerDiscipline variable missing — anchor has no source value to inject."}]
    return []


def check_goodbye(c: str) -> list[dict]:
    """T31 — _isGoodbye detector + call-site clean exit."""
    issues: list[dict] = []
    for sym in ("_isGoodbye", "_GOODBYE_RE"):
        if sym not in c:
            issues.append({"check": "goodbye",
                           "reason": f"{sym} missing — 'yun lang' / 'I'm done' / 'tapos na' don't end the session cleanly."})
    if "_isGoodbye(transcript)" not in c:
        issues.append({"check": "goodbye",
                       "reason": "Call site does not invoke _isGoodbye — detector exists but is never called."})
    # Goodbye vocab must cover PH closers. We look for the headword
    # ('tapos', 'wala') rather than the literal whitespace-form because
    # regex bodies use `\s+` for inter-word space which doesn't
    # substring-match a literal space.
    if "_GOODBYE_RE" in c:
        m = re.search(r"_GOODBYE_RE\s*=\s*/([^/]+)/", c)
        if m:
            body = m.group(1).lower()
            for kw in ("tapos", "wala"):
                if kw not in body:
                    issues.append({"check": "goodbye",
                                   "reason": f"_GOODBYE_RE missing PH closer headword '{kw}' — workers using Tagalog can't cleanly end the session."})
    return issues


def check_confidence_calibration(c: str) -> list[dict]:
    """T32 — CONFIDENCE CALIBRATION anchor with small-sample hedge."""
    if "CONFIDENCE CALIBRATION" not in c:
        return [{"check": "confidence_calibration",
                 "reason": "CONFIDENCE CALIBRATION anchor missing — model may state small-sample findings as verified patterns."}]
    if "hedge" not in c.lower():
        return [{"check": "confidence_calibration",
                 "reason": "Anchor exists but doesn't tell the model to HEDGE on thin data — hedging is the actual mechanism."}]
    return []


def check_long_session_pacing(c: str) -> list[dict]:
    """T33 — SESSION PACING anchor conditional on _sessionTurns.length >= 10."""
    if "SESSION PACING" not in c:
        return [{"check": "long_session_pacing",
                 "reason": "SESSION PACING anchor missing — no fatigue-aware wrap-up nudge."}]
    if not re.search(r"_sessionTurns\.length\s*>=\s*10", c):
        return [{"check": "long_session_pacing",
                 "reason": "Pacing anchor not gated on _sessionTurns.length >= 10 — would fire on every turn or never."}]
    return []


def check_alerts_override(c: str) -> list[dict]:
    """T34 — ALERTS OVERRIDE anchor."""
    if "ALERTS OVERRIDE" not in c:
        return [{"check": "alerts_override",
                 "reason": "ALERTS OVERRIDE anchor missing — critical alerts can be buried under the answer to the worker's question."}]
    if "FIRST sentence" not in c and "first sentence" not in c.lower():
        return [{"check": "alerts_override",
                 "reason": "ALERTS OVERRIDE anchor doesn't require surfacing in the FIRST sentence — vague instruction."}]
    return []


CHECK_NAMES = [
    "shift_context", "repeated_issue_surface", "standards_lookup",
    "voice_shortcut", "quality_feedback", "discipline_biasing",
    "goodbye", "confidence_calibration", "long_session_pacing",
    "alerts_override",
]

CHECK_LABELS = {
    "shift_context":          "T25 SHIFT CONTEXT anchor + PH UTC+8 timezone math",
    "repeated_issue_surface": "T26 _fetchRepeatedIssueFlag queries v_logbook_truth + 'REPEATED ISSUES' anchor",
    "standards_lookup":       "T27 _detectStandardsMention + ISO/SAE/SMRP vocabulary + STANDARDS QUERY anchor",
    "voice_shortcut":         "T28 _isVoiceShortcut covers logbook/analytics/inventory + call-site navigates",
    "quality_feedback":       "T29 _recordReplyRating + data-rate thumbs UI + ai_cost_log target",
    "discipline_biasing":     "T30 WORKER DISCIPLINE anchor reads workerDiscipline value",
    "goodbye":                "T31 _isGoodbye covers PH closers (tapos / wala na) + call-site clean exit",
    "confidence_calibration": "T32 CONFIDENCE CALIBRATION anchor instructs model to hedge on small samples",
    "long_session_pacing":    "T33 SESSION PACING anchor gated on _sessionTurns.length >= 10",
    "alerts_override":        "T34 ALERTS OVERRIDE anchor requires critical alerts in the FIRST sentence",
}


def main() -> int:
    print("\033[1m\nAI Companion Intelligence Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_shift_context(c)
    issues += check_repeated_issue_surface(c)
    issues += check_standards_lookup(c)
    issues += check_voice_shortcut(c)
    issues += check_quality_feedback(c)
    issues += check_discipline_biasing(c)
    issues += check_goodbye(c)
    issues += check_confidence_calibration(c)
    issues += check_long_session_pacing(c)
    issues += check_alerts_override(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
