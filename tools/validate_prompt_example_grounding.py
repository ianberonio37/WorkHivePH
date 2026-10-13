"""validate_prompt_example_grounding.py - a prompt EXAMPLE never carries a fact a model can pass off as data.

THE CLASS (local eval run, 2026-10-07): the analytics agent's answer repeated, word for word, a SAMPLE line from the
shared persona block (supabase/functions/_shared/persona.ts, narrated-specialist rules): "Naks, line dipped to 71% OEE.
PMP-101 stops are the biggest hit." and "a breakdown on Conveyor 2". None of those exist in the hive it answered for,
so the person read another plant's (or no plant's) numbers as their own. The same class shipped before: the analytics
prescriptive brief named "P-103" / "David Velasco" for every hive (2026-07-24, a few-shot code), and the companion
"recalled" a 410 Nm torque that existed only in Hezekiah's example (2026-06-12). A free-tier model copies a vivid
example token as content, not as a format to fill; an instruction like "match the cadence, not the words" does not
stop it.

THE RULE (static, three checks):
  A. Shared prompt modules (supabase/functions/_shared/*.ts):
     - every few-shot string in an `examples: [...]` array carries NO digit outside a <placeholder> slot;
     - every quoted sample inside prompt text ("..." or '...') carries no asset-tag-like token (ABC-123), no named
       asset with a number (Conveyor 2), no percentage, no ISO date, no digit count of events, no reading with a unit
       unless it is inside a <placeholder> slot.
  B. persona.ts states the rule to the model: CANONICAL_ANCHOR carries the two clauses ("EXAMPLES ARE STYLE, NEVER
     DATA" and "EVERY FIGURE COMES FROM THIS REQUEST"), every speaking-mode prompt (narrated-specialist, companion,
     conversational) interpolates ${CANONICAL_ANCHOR}, and the rendered example block is fenced "STYLE EXAMPLES ONLY".
  C. Edge-function prompts (supabase/functions/*/index.ts template literals): a quoted sample carries no asset-tag-like
     token or named asset with a number, and an "e.g." / example sample carries no percentage, UNLESS the same token
     appears in the example's own INPUT within the three lines above it (an input -> output extraction pair is
     traceable, not invented) or it is a standards/reference code (R-410A, SHA-256, ASME UG-99 ...).

    python tools/validate_prompt_example_grounding.py            # PASS / FAIL
    python tools/validate_prompt_example_grounding.py --selftest # the rule's teeth on fixed fixtures
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN_DIR = ROOT / "supabase" / "functions"
SHARED = FN_DIR / "_shared"
PERSONA = SHARED / "persona.ts"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ---------------------------------------------------------------------------------------------------------------------
# A minimal TS lexer: enough to separate comments, string literals and template literals (with nested ${...}).
# ---------------------------------------------------------------------------------------------------------------------
_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")


def lex_strings(src: str) -> list[dict]:
    """Return every string / template literal as {kind, start, end, text}. Template ${...} slots become "<expr>"
    (a slot is a placeholder by nature) padded with the newlines it spanned, so line numbers stay true."""
    out: list[dict] = []
    i, n = 0, len(src)

    def prev_sig(pos: int) -> str:
        j = pos - 1
        while j >= 0 and src[j] in " \t\r\n":
            j -= 1
        return src[j] if j >= 0 else ""

    def read_quoted(pos: int, q: str) -> int:
        j = pos + 1
        while j < n:
            c = src[j]
            if c == "\\":
                j += 2
                continue
            if c == q or c == "\n":
                return j + 1
            j += 1
        return n

    def read_regex(pos: int) -> int:
        j, in_class = pos + 1, False
        while j < n:
            c = src[j]
            if c == "\\":
                j += 2
                continue
            if c == "\n":
                return j
            if in_class:
                if c == "]":
                    in_class = False
            elif c == "[":
                in_class = True
            elif c == "/":
                j += 1
                while j < n and src[j].isalpha():
                    j += 1
                return j
            j += 1
        return n

    def read_template(pos: int) -> int:
        """pos at the opening backtick. Appends the template (and any nested ones) to out; returns end."""
        j = pos + 1
        buf: list[str] = []
        while j < n:
            c = src[j]
            if c == "\\":
                buf.append(src[j:j + 2])
                j += 2
                continue
            if c == "`":
                out.append({"kind": "tpl", "start": pos, "end": j + 1, "text": "".join(buf)})
                return j + 1
            if c == "$" and j + 1 < n and src[j + 1] == "{":
                k = read_code(j + 2, until="}")
                buf.append("<expr>" + "\n" * src[j:k].count("\n"))
                j = k
                continue
            buf.append(c)
            j += 1
        out.append({"kind": "tpl", "start": pos, "end": n, "text": "".join(buf)})
        return n

    def read_code(pos: int, until: str | None = None) -> int:
        j, depth = pos, 0
        while j < n:
            c = src[j]
            if c == "/" and j + 1 < n and src[j + 1] == "/":
                k = src.find("\n", j)
                j = n if k < 0 else k
                continue
            if c == "/" and j + 1 < n and src[j + 1] == "*":
                k = src.find("*/", j + 2)
                j = n if k < 0 else k + 2
                continue
            if c in "\"'":
                k = read_quoted(j, c)
                out.append({"kind": "str", "start": j, "end": k, "text": src[j + 1:k - 1]})
                j = k
                continue
            if c == "`":
                j = read_template(j)
                continue
            if c == "/" and (prev_sig(j) in _REGEX_PREV or prev_sig(j) == "" or src[max(0, j - 6):j].rstrip().endswith("return")):
                j = read_regex(j)
                continue
            if until:
                if c == "{":
                    depth += 1
                elif c == "}":
                    if depth == 0:
                        return j + 1
                    depth -= 1
            j += 1
        return n

    read_code(0)
    out.sort(key=lambda t: t["start"])
    return out


def line_of(src: str, offset: int) -> int:
    return src.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------------------------------------------------
# What a concrete-looking fact is
# ---------------------------------------------------------------------------------------------------------------------
PLACEHOLDER = re.compile(r"<[A-Za-z_][^<>\n]{0,60}>")
TAG = re.compile(r"\b[A-Z]{1,5}-\d{1,4}[A-Z]?\b")
NAMED = re.compile(r"\b(?:conveyor|pump|compressor|line|boiler|chiller|motor|generator|tank|cooling tower|mixer|kiln|"
                   r"press|fan|blower|dryer|oven|crusher|feeder|hoist|crane|turbine|machine)\s+#?\d+[A-Za-z]?\b", re.I)
PCT = re.compile(r"\d+(?:\.\d+)?\s?%")
DATE = re.compile(r"\b(?:19|20)\d\d-\d\d-\d\d\b")
COUNT = re.compile(r"\b\d+\s+(?:[a-z-]+\s+)?(?:corrective|reactives?|breakdowns?|faults?|failures?|events?|stops?|trips?|"
                   r"jobs?|alerts?|work orders?|times|days|weeks|months|hours|items)\b")
READING = re.compile(r"\b\d+(?:\.\d+)?\s?(?:°C|°F|Nm|N·m|bar|psi|rpm|RPM|mm/s|kW|kVA)(?![A-Za-z])")
HOURS = re.compile(r"\b\d+(?:\.\d+)?\s?(?:h|hrs?|hours?)\b")
DIGIT = re.compile(r"\d")
# Standards / reference codes that share the TAG shape but are not plant data.
STANDARD_TAG = re.compile(r"^(?:R-\d{2,3}[A-Z]?|SHA-\d+|ISO-\d+|UTF-\d+|UG-\d+|UW-\d+|UA-\d+|UCS-\d+|SA-\d+|RS-\d+|IP-\d+|"
                          r"SS-\d+|GRP-\d+|FM-\d+|IG-\d+|UL-\d+|NC-\d+|GG-\d+|G-\d+|F-900|VG-\d+|SP-\d+|BH-\d+|FCU-\d+|"
                          r"STD-\d+|IEC-\d+|EN-\d+|PD-\d+|DO-\d+|ASTM-\d+|API-\d+|NFPA-\d+|ANSI-\d+|ABEC-\d+|PTB-\d+)$")

DQ = re.compile(r'"([^"\n]{1,400})"')
SQ = re.compile(r"(?<![A-Za-z0-9])'([^'\n]{1,400})'(?![A-Za-z0-9])")
EG = re.compile(r"(?:e\.g\.|for example|example|such as|like)\W{0,6}$", re.I)
PAIR_OUTPUT = re.compile(r"^\s*(?:→|->)")
EXAMPLE_HEADER = re.compile(r"^\s*(?:good\s+|bad\s+)?examples?\b", re.I)

# Findings that are real but sit in a file this change may not touch. Each one is printed as OPEN on every run, so it
# stays visible; it does not fail the gate. Remove the entry when the owner lands the placeholder.
KNOWN_OPEN = {}   # 2026-10-07: the ai-gateway memory-summariser example is now "<reading> was <value> <unit>"


def mask(text: str) -> str:
    """Hide <placeholder> slots - but a slot that itself names a concrete tag ("<tag like PUMP-201>") is not a slot."""
    return PLACEHOLDER.sub(lambda m: m.group(0) if _concrete_in_slot(m.group(0)) else "<>", text)


def _concrete_in_slot(slot: str) -> bool:
    return any(not STANDARD_TAG.match(t.group(0)) for t in TAG.finditer(slot)) or bool(NAMED.search(slot))


def quoted_spans(text: str):
    for rx in (DQ, SQ):
        for m in rx.finditer(text):
            yield m.start(1), m.group(1)


def shaped_hits(span: str) -> list[str]:
    s = mask(span)
    hits = []
    for rx, label in ((TAG, "asset tag"), (NAMED, "named asset"), (PCT, "percentage"), (DATE, "date"),
                      (COUNT, "count"), (READING, "reading"), (HOURS, "duration")):
        for m in rx.finditer(s):
            if rx is TAG and STANDARD_TAG.match(m.group(0)):
                continue
            hits.append(f"{label} {m.group(0)!r}")
    return hits


# ---------------------------------------------------------------------------------------------------------------------
# A. shared prompt modules
# ---------------------------------------------------------------------------------------------------------------------
def example_array_ranges(src: str, toks: list[dict]) -> list[tuple[int, int]]:
    """[start, end) offsets of every `examples: [ ... ]` array, skipping brackets inside strings."""
    str_ranges = [(t["start"], t["end"]) for t in toks]

    def in_string(pos: int) -> bool:
        return any(a <= pos < b for a, b in str_ranges)

    ranges = []
    for m in re.finditer(r"\bexamples\s*:\s*\[", src):
        if in_string(m.start()):
            continue
        depth, j = 0, m.end() - 1
        while j < len(src):
            if not in_string(j):
                if src[j] == "[":
                    depth += 1
                elif src[j] == "]":
                    depth -= 1
                    if depth == 0:
                        ranges.append((m.end(), j))
                        break
            j += 1
    return ranges


def scan_shared(src: str, rel: str) -> list[str]:
    toks = lex_strings(src)
    ex_ranges = example_array_ranges(src, toks)
    findings: list[str] = []
    for t in toks:
        body_off = t["start"] + 1
        in_examples = any(a <= t["start"] < b for a, b in ex_ranges)
        if in_examples:
            for ln_i, ln in enumerate(t["text"].split("\n")):
                m = DIGIT.search(mask(ln))
                if m:
                    findings.append(f"{rel}:{line_of(src, body_off) + ln_i}: few-shot example carries a concrete "
                                    f"figure outside a <placeholder>: ...{mask(ln)[max(0, m.start() - 30):m.start() + 30]}...")
            continue
        for off, span in quoted_spans(t["text"]):
            for h in shaped_hits(span):
                findings.append(f"{rel}:{line_of(src, body_off) + t['text'].count(chr(10), 0, off)}: quoted sample "
                                f"carries a concrete {h}: \"{span[:90]}\"")
    return findings


# ---------------------------------------------------------------------------------------------------------------------
# B. persona.ts states the rule
# ---------------------------------------------------------------------------------------------------------------------
STYLE_CLAUSE = "EXAMPLES ARE STYLE, NEVER DATA"
SOURCE_CLAUSE = "EVERY FIGURE COMES FROM THIS REQUEST"
FENCE = "STYLE EXAMPLES ONLY"


def check_persona_contract(src: str, rel: str) -> list[str]:
    findings: list[str] = []
    toks = lex_strings(src)
    m = re.search(r"const\s+CANONICAL_ANCHOR\s*=\s*`", src)
    anchor = next((t for t in toks if m and t["start"] == m.end() - 1), None)
    if anchor is None:
        return [f"{rel}: CANONICAL_ANCHOR template not found"]
    for clause in (STYLE_CLAUSE, SOURCE_CLAUSE):
        if clause not in anchor["text"]:
            findings.append(f"{rel}:{line_of(src, anchor['start'])}: CANONICAL_ANCHOR lacks the clause \"{clause}\"")
    fn = re.search(r"export function buildPersonaBlock\(", src)
    end = src.find("\nexport function", fn.end()) if fn else -1
    if not fn:
        return findings + [f"{rel}: buildPersonaBlock not found"]
    body_toks = [t for t in toks if t["kind"] == "tpl" and fn.start() < t["start"] < (end if end > 0 else len(src))]
    speaking = [t for t in body_toks if src[max(0, t["start"] - 12):t["start"]].rstrip().endswith("return")
                and len(t["text"]) > 300]
    if len(speaking) < 3:
        findings.append(f"{rel}: expected 3 speaking-mode prompts in buildPersonaBlock, found {len(speaking)}")
    for t in speaking:
        if "<expr>" not in t["text"] or "${CANONICAL_ANCHOR}" not in src[t["start"]:t["end"]]:
            findings.append(f"{rel}:{line_of(src, t['start'])}: a speaking-mode prompt does not carry ${{CANONICAL_ANCHOR}}")
    ex_tpl = [t for t in body_toks if "<expr>" in t["text"] and "p.examples" in src[t["start"]:t["end"]]]
    if not ex_tpl:
        findings.append(f"{rel}: the rendered example block was not found")
    for t in ex_tpl:
        if FENCE not in t["text"]:
            findings.append(f"{rel}:{line_of(src, t['start'])}: the rendered example block is not fenced \"{FENCE}\"")
    return findings


def check_client_persona(src: str, rel: str) -> list[str]:
    """wh-persona.js mirrors persona.ts for the floating companion; it must state the same rule and fence."""
    findings = []
    m = re.search(r"const\s+CANONICAL_ANCHOR\s*=", src)
    anchor_end = src.find(";", m.end()) if m else -1
    anchor = src[m.end():anchor_end] if m else ""
    for clause in (STYLE_CLAUSE, SOURCE_CLAUSE):
        if clause not in anchor:
            findings.append(f"{rel}: CANONICAL_ANCHOR lacks the clause \"{clause}\" (mirror of persona.ts)")
    fn = re.search(r"function\s+buildCompanionBlock\s*\(", src)
    body = src[fn.end():src.find("\n  }\n", fn.end())] if fn else ""
    if "CANONICAL_ANCHOR" not in body:
        findings.append(f"{rel}: buildCompanionBlock does not carry CANONICAL_ANCHOR")
    if FENCE not in body:
        findings.append(f"{rel}: buildCompanionBlock's example block is not fenced \"{FENCE}\"")
    return findings


# ---------------------------------------------------------------------------------------------------------------------
# C. edge-function prompts
# ---------------------------------------------------------------------------------------------------------------------
def scan_function_prompt(src: str, rel: str) -> list[str]:
    findings: list[str] = []
    for t in lex_strings(src):
        if t["kind"] != "tpl" or len(t["text"]) < 200:
            continue
        text = t["text"]
        lines = text.split("\n")
        body_line = line_of(src, t["start"] + 1)
        for li, ln in enumerate(lines):
            context_above = "\n".join(lines[max(0, li - 3):li]).lower()
            # the INPUT side of an input -> output extraction pair (the next line is "→ ...") is a sample of what a
            # person says, not an answer; its output is checked for traceability against it instead.
            is_pair_input = any(PAIR_OUTPUT.match(x) for x in lines[li + 1:li + 3])
            example_block = any(EXAMPLE_HEADER.match(x) for x in lines[max(0, li - 6):li])
            for off, span in quoted_spans(ln):
                if is_pair_input:
                    continue
                s = mask(span)
                hits = []
                for rx, label in ((TAG, "asset tag"), (NAMED, "named asset")):
                    for m in rx.finditer(s):
                        tok = m.group(0)
                        if rx is TAG and STANDARD_TAG.match(tok):
                            continue
                        if tok.lower() in context_above:
                            continue  # traceable: the example's own input named it
                        hits.append(f"{label} {tok!r}")
                if EG.search(ln[:off - 1] if off else "") or example_block:
                    for rx, label in ((PCT, "percentage"), (READING, "reading"), (DATE, "date"), (HOURS, "duration")):
                        for m in rx.finditer(s):
                            if m.group(0).lower() not in context_above:
                                hits.append(f"{label} {m.group(0)!r}")
                for h in hits:
                    findings.append(f"{rel}:{body_line + li}: prompt sample carries a concrete {h}: \"{span[:90]}\"")
    return findings


# ---------------------------------------------------------------------------------------------------------------------
def split_known_open(findings: list[str]) -> tuple[list[str], list[str]]:
    failing, open_ = [], []
    for f in findings:
        hit = next((why for (rel, tok), why in KNOWN_OPEN.items() if f.startswith(rel + ":") and repr(tok) in f), None)
        (open_ if hit else failing).append(f + (f"  [OPEN: {hit}]" if hit else ""))
    return failing, open_


def run(root: Path = ROOT) -> list[str]:
    findings: list[str] = []
    shared = root / "supabase" / "functions" / "_shared"
    for p in sorted(shared.glob("*.ts")):
        if p.name.endswith(".test.ts"):
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        findings += scan_shared(src, p.relative_to(root).as_posix())
    persona = shared / "persona.ts"
    if persona.exists():
        findings += check_persona_contract(persona.read_text(encoding="utf-8"), persona.relative_to(root).as_posix())
    else:
        findings.append("supabase/functions/_shared/persona.ts: missing")
    # the client mirror: companion-launcher.js prepends window.getCompanionBlock() to every floating-companion call
    client = root / "wh-persona.js"
    if client.exists():
        csrc = client.read_text(encoding="utf-8")
        findings += scan_shared(csrc, "wh-persona.js")
        findings += check_client_persona(csrc, "wh-persona.js")
    for p in sorted((root / "supabase" / "functions").glob("*/index.ts")):
        src = p.read_text(encoding="utf-8", errors="replace")
        findings += scan_function_prompt(src, p.relative_to(root).as_posix())
    return findings


def selftest() -> int:
    bad_shared = [
        'const P = { examples: [\n  "Worker: hot bearing.\\nZaniah: Line dipped to 71% OEE.",\n] };',
        'const P = { examples: [\n  "Worker: hot bearing on <tag>.\\nHezekiah: M20 dry is ~410 Nm.",\n] };',
        'const R = `- React first, then summarise: "Naks, line dipped to <n>% OEE. PMP-101 stops are the biggest hit."`;',
        'const R = `- Skip the empathy line: "Opening the logbook to log a breakdown on Conveyor 2."`;',
        'const R = `- Quote it: "Three events since 2026-09-01."`;',
        "const R = `- Empathy beat ('hala ka, 3 reactives this month').`;",
    ]
    good_shared = [
        'const P = { examples: [\n  "Worker: hot bearing on <tag>, around <reading>°C.\\nZaniah: Line dipped to <n>% OEE.",\n] };',
        'const R = `- React first, then summarise: "Naks, line dipped to <n>% OEE. <asset tag> stops are the biggest hit."`;',
        'const R = `OEE: >85% world-class, 65-85% typical, <65% needs work. Do NOT cite OSHA (e.g. "OSHA 1910.147").`;',
        "const R = `Empathy beat ('naks, mahirap yan'). Never start with 'You\\'re feeling'.`;",
    ]
    bad_fn = [
        'const S = `' + "x" * 200 + '\n1. hero_finding MUST quote it (e.g. "61% complete with 4 of 7 scope items closed").`;',
        'const S = `' + "x" * 200 + '\n6. refs as they appear (e.g. "Pump P-204", "shaft seal leak").`;',
        'const S = `' + "x" * 200 + '\n  "asset_tag": "<tag like PUMP-201 or null>",`;',
        'const S = `' + "x" * 200 + '\nExamples of reasoning:\n  • "Mechanical MTTR runs 3.2h above the team average."`;',
    ]
    good_fn = [
        'const S = `' + "x" * 200 + '\nExamples:\n"Cooling tower CT-01, fan blade cracked"\n→ machine:"CT-01", status:"Open"`;',
        'const S = `' + "x" * 200 + '\n- "Send PM Overdue to Ian, focus on pump 3"\n  → {"machine_filter":"Pump 3"}`;',
        'const S = `' + "x" * 200 + '\nRefrigerant (e.g. "R-410A", "R-32"); hash "SHA-256".`;',
        'const S = `' + "x" * 200 + '\n1. hero_finding MUST quote it (e.g. "<pct>% complete with <items_done> of <items_total> scope items closed").`;',
        'const S = `' + "x" * 200 + '\nGauge for the vessel: "0 to 17.5 bar" glycerine-filled, per the design pressure above.`;',
    ]
    fails = []
    for i, s in enumerate(bad_shared):
        if not scan_shared(s, f"bad_shared{i}"):
            fails.append(f"bad_shared[{i}] NOT flagged")
    for i, s in enumerate(good_shared):
        f = scan_shared(s, f"good_shared{i}")
        if f:
            fails.append(f"good_shared[{i}] flagged: {f}")
    for i, s in enumerate(bad_fn):
        if not scan_function_prompt(s, f"bad_fn{i}"):
            fails.append(f"bad_fn[{i}] NOT flagged")
    for i, s in enumerate(good_fn):
        f = scan_function_prompt(s, f"good_fn{i}")
        if f:
            fails.append(f"good_fn[{i}] flagged: {f}")
    # B: the contract check bites when the clause or the fence is missing
    persona_src = PERSONA.read_text(encoding="utf-8") if PERSONA.exists() else ""
    if persona_src and not check_persona_contract(persona_src, "persona.ts"):
        for mutant, why in ((persona_src.replace(STYLE_CLAUSE, "EXAMPLES"), "style clause removed"),
                            (persona_src.replace(SOURCE_CLAUSE, "FIGURES"), "source clause removed"),
                            (persona_src.replace(FENCE, "Examples"), "fence removed")):
            if not check_persona_contract(mutant, "persona.ts"):
                fails.append(f"contract check did not bite: {why}")
    for f in fails:
        print("  " + f)
    n_bad, n_good = len(bad_shared) + len(bad_fn), len(good_shared) + len(good_fn)
    print(f"selftest: {n_bad} bad fixtures flagged, {n_good} good fixtures clean, contract mutants bite"
          if not fails else "selftest FAILED")
    return 1 if fails else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    findings, open_ = split_known_open(run())
    for o in open_:
        print("OPEN " + o)
    if findings:
        print(f"FAIL: {len(findings)} prompt example(s) carry a concrete fact a model can pass off as data")
        for f in findings:
            print("  " + f)
        print("  Fix: replace the figure / tag / name with a <placeholder> slot (\"<asset tag>\", \"<n>%\"), and keep"
              " the figures-from-context rule in the prompt (see persona.ts CANONICAL_ANCHOR).")
        return 1
    print("PASS: no prompt example carries a concrete asset tag, figure, date or count outside a <placeholder>; "
          "persona.ts states the style-not-data rule in every speaking mode")
    return 0


if __name__ == "__main__":
    sys.exit(main())
