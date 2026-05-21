"""
AI Companion Multi-Language NLU Validator (turns #205-#214)
"""
from __future__ import annotations
import os, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str: return read_file(VOICE_HANDLER_JS) or ""


SYMBOLS = {
    "cebuano":     ["_CEBUANO_MARKERS", "_isCebuanoLeaning", "'unsa'", "'asa'", "'kinsa'"],
    "ilonggo":     ["_ILONGGO_MARKERS", "_isIlonggoLeaning", "'gid'", "'bala'"],
    "imperative":  ["_TGL_IMPERATIVE_RE", "_isTagalogImperative"],
    "code_switch": ["_PH_WORDS_SAMPLE", "_codeSwitchRatio"],
    "politeness":  ["_classifyPolitenessRegister", "'formal'", "'casual'", "'mixed'"],
    "time":        ["_PH_TIME_PHRASES", "_parsePhTimeExpression", "umaga", "tanghali", "hapon", "gabi"],
    "numbers":     ["_NUMBER_WORDS", "_wordToNumber", "'isa'", "'dalawa'", "'tatlo'"],
    "fillers":     ["_stripFillers"],
    "stop_words":  ["_STOP_WORDS", "_removeStopWords"],
    "slang":       ["_SLANG_DICT", "_slangToCanonical", "'broken'", "'overheat'", "'leak'"],
    "wires":       ["TAGALOG IMPERATIVE", "_isTagalogImperative(transcript)", "POLITENESS REGISTER", "_classifyPolitenessRegister(transcript)", "DIALECT NOTE", "_isCebuanoLeaning(transcript)", "_isIlonggoLeaning(transcript)"],
}
LABELS = {
    "cebuano":     "T205 _CEBUANO_MARKERS (unsa/asa/kinsa)",
    "ilonggo":     "T206 _ILONGGO_MARKERS (gid/bala)",
    "imperative":  "T207 _isTagalogImperative",
    "code_switch": "T208 _codeSwitchRatio",
    "politeness":  "T209 _classifyPolitenessRegister (formal/casual/mixed)",
    "time":        "T210 _PH_TIME_PHRASES (umaga/tanghali/hapon/gabi)",
    "numbers":     "T211 _NUMBER_WORDS (PH+EN 0-20)",
    "fillers":     "T212 _stripFillers",
    "stop_words":  "T213 _STOP_WORDS bilingual",
    "slang":       "T214 _SLANG_DICT (sira→broken etc)",
    "wires":       "PHASE A wires — T207 TAGALOG IMPERATIVE + T209 POLITENESS REGISTER + T205/T206 DIALECT NOTE anchors live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Multi-Language NLU Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    issues = []
    for k, syms in SYMBOLS.items():
        for s in syms:
            if s not in c:
                issues.append({"check": k, "reason": f"{s} missing."})
    n_pass, n_skip, n_fail = format_result(list(SYMBOLS.keys()), LABELS, issues)
    print()
    if n_fail == 0: print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
