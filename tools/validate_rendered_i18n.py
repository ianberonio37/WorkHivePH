#!/usr/bin/env python3
"""validate_rendered_i18n.py — the i18n gates count STAMPS; this one counts what the reader SEES.

★WHY THIS EXISTS (walked 2026-09-11, Ricardo Morales, worker in Lucena Pharmaceutical Mfg., wh_lang=fil).
asset-hub read 100% on the full rubric while its PRIMARY CTA said "Review 2 pending ->" in English, on a
page whose documentElement.lang is "fil", under a heading that asks the question in Filipino
(p_whattodonext_8ce2 -> "Ano ang susunod na gagawin"). The button even carried a stamp of its own,
p_takeaction_ee0b -> "Kumilos ->", and that translation had SHIPPED. The page's own JavaScript then
overwrote the element's textContent with an English label.

EVERY EXISTING i18n MEASUREMENT WAS BLIND TO IT, for one reason: they count data-i STAMPS.
  * the in-page orphan census reported `orphanCount: 0` — the stamp was still on the element, only the
    RENDERED TEXT had changed;
  * validate_i18n_coverage.py still lists the page as "covered";
  * validate_shared_component_i18n.py scans shared JS, and this JS is in the page.
That is the same lesson as [[feedback_shared_chrome_was_outside_every_i18n_gate]] one layer further in:
a gate's SCOPE is part of what it proves. There the untranslated strings sat outside the scanned pages;
here they sit INSIDE a scanned page, in its script block, where a stamp census cannot reach them.

TWO SHAPES, ONE CAUSE — both are what this gate looks for:
  A. OVERWRITE — JS assigns a bare English literal to .textContent/.innerText/.innerHTML of an element
     that CARRIES a data-i stamp. The stamp says "this text is translated"; the assignment makes that
     false at runtime. This is the strongest signal and is never a false positive worth keeping.
  B. UNWRAPPED — JS assigns a bare English literal (>= MIN_WORDS words) to a user-facing text node
     anywhere on a page that CLAIMS to be bilingual, without going through _t(en, fil).

WHAT IT DELIBERATELY DOES NOT FLAG, so the gate keeps its teeth:
  * pages on the EN-by-design exempt roster (internal/admin consoles, formal docs) — the same roster
    validate_i18n_coverage.py uses, read from that file so the two can never drift apart;
  * pages carrying no data-i stamps at all: a page that never claimed to be bilingual is a coverage
    question for the other gate, not a truthfulness question for this one;
  * literals that are not prose — numbers, units, single words, acronyms, CSS, selectors, URLs, dates;
  * anything already inside a _t( ... ) call, which is the platform's mechanism working correctly.

RATCHET, NOT A CLIFF. The first census is the baseline; the gate FAILS when any page's count RISES, and
prints the drop when it falls. Same idiom as validate_csp.py, and for the same reason: a gate nobody can
pass gets switched off, and this class is large enough that a hard zero on day one would be exactly that.
Re-baseline deliberately with --accept after a wave lands.

    python tools/validate_rendered_i18n.py --check
    python tools/validate_rendered_i18n.py --report     # per-page offenders, with the literal
    python tools/validate_rendered_i18n.py --accept     # re-freeze the baseline (deliberate)
    python tools/validate_rendered_i18n.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "rendered_i18n_baseline.json"
COVERAGE_GATE = ROOT / "tools" / "validate_i18n_coverage.py"

MIN_WORDS = 2          # "Save" is a label; "Review 2 pending" is a sentence to a reader
MIN_LETTERS = 6

SCRIPT = re.compile(r"<script\b[^>]*>([\s\S]*?)</script>", re.I)
# .textContent = "literal"  /  .innerText = `literal`  /  .innerHTML = 'literal'
ASSIGN = re.compile(
    r"\.(textContent|innerText|innerHTML)\s*=\s*(?P<q>['\"`])(?P<lit>(?:\\.|(?!(?P=q))[\s\S]){2,300})(?P=q)"
)
# ★THE LITERAL USUALLY NEVER TOUCHES THE PROPERTY (the defect this gate was built for, 2026-09-11).
# asset-hub's block reads `let text; ... text = 'No assets yet...'; ... actBox.textContent = text;` —
# five branches assigning English prose to a VARIABLE that is written to textContent once at the end.
# A detector that only watches the property itself would have missed every one of them. So: find the
# identifiers that reach a text property, then treat prose assigned to THOSE as user-facing.
SINK_IDENT = re.compile(r"\.(?:textContent|innerText|innerHTML)\s*=\s*([A-Za-z_$][\w$]*)\s*[;,)]")
IDENT_LIT = r"(?:^|[;{}\n])\s*(?:const|let|var)?\s*%s\s*=\s*(?P<q>['\"`])(?P<lit>(?:\\.|(?!(?P=q))[\s\S]){2,300})(?P=q)"
# a label handed straight to a renderer: setCta('Review 2 pending ->', ...), showToast('...'), setLabel(...)
LABEL_CALL = re.compile(
    r"\b(set[A-Z]\w*|showToast|whToast|setLabel|setText)\s*\(\s*(?P<q>['\"`])(?P<lit>(?:\\.|(?!(?P=q))[\s\S]){2,300})(?P=q)"
)
# the id whose element carries a data-i stamp, e.g. <a data-i="p_x" id="ah-action-btn" ...>
STAMPED_ID = re.compile(r"<[^>]*\bdata-i\s*=\s*[\"'][^\"']+[\"'][^>]*\bid\s*=\s*[\"']([^\"']+)[\"']", re.I)
STAMPED_ID_REV = re.compile(r"<[^>]*\bid\s*=\s*[\"']([^\"']+)[\"'][^>]*\bdata-i\s*=\s*[\"'][^\"']+[\"']", re.I)

NOT_PROSE = re.compile(
    r"^(?:[\s\d.,:;%$#@/\\|+*<>()\[\]{}=_~^&!?-]|&[a-z]+;|&#\d+;)*$"
)
# ★INTERPOLATION WAS A CLOAK, AND THE LINE THAT SAID OTHERWISE WAS DEAD CODE (2026-09-11).
# `\$\{` was in this pattern, unanchored, so ANY literal containing a template slot matched
# LOOKS_TECHNICAL and `is_prose` returned False on its first line - two lines BEFORE the branch that
# says "a template slot: the words around it still count, so keep going" could ever run. That branch
# was unreachable for every template literal in the platform. Measured on this gate's own function:
#
#   'Switch Hive (3)'                          -> PROSE      (counted)
#   'Switch Hive (${list.length})'             -> ignored    (same words, invisible)
#   'You have ${n} open jobs waiting for you'  -> ignored
#
# So the gate saw a sentence only while it had no slot in it - and a count appended to a translated
# label is EXACTLY the shape that carries a slot. Both defects found live on the J26 walk were of
# that shape (`btn.textContent = \`Switch Hive (${n})\`` over data-i="switchhive", and the stock CTA
# over data-i="restock"), which is why this gate had never named them and why hive.html's baseline of
# 29 did not include them. `{{` stays - mustache/handlebars really is a template language, not a
# sentence with a number in it. Kin of [[feedback_changing_the_measurement_is_not_drift]]: the count
# rises here because the ruler got better eyes, not because the platform got worse.
LOOKS_TECHNICAL = re.compile(
    r"(?:^\s*[.#\[@]|^https?:|^/|\{\{|^[a-z-]+\s*:\s*[^ ]+;|^\s*<|px\b|rgba?\(|^[A-Z0-9_]{2,}$)"
)
# A STYLE BLOCK IS NOT PROSE. audit-log builds its print stylesheet as a string and assigns it to
# textContent — "@media print { #wh-print-stamp { display:block !important; ..." is CSS, not a sentence
# anyone reads. Declaration punctuation is the reliable tell.
LOOKS_LIKE_CSS = re.compile(r"[{};]\s*[a-z-]+\s*:|@(?:media|page|supports|import|font-face)\b", re.I)
# The EN-by-design DECLARATION, copied in intent from validate_i18n_coverage.py's DISPOSITION_RE: a
# formal engineering document / EN publication whose BODY is EN by design is not a translation gap, and
# flagging it is the declared-a-bug-before-recalling-the-disposition error. project-report.html and
# ph-intelligence.html both declare it inline.
DISPOSITION_RE = re.compile(
    r"EN[-\s]by[-\s]design|EN publication by design|report BODY is (?:an\s+)?EN\b"
    r"|formal engineering document", re.I)


def exempt_pages() -> set[str]:
    """The EN-by-design roster, read from the coverage gate so the two rosters cannot drift."""
    try:
        src = io.open(COVERAGE_GATE, encoding="utf-8").read()
    except OSError:
        return set()
    out: set[str] = set()
    for m in re.finditer(r"[\"']([a-z0-9-]+\.html)[\"']", src):
        out.add(m.group(1))
    # only the ones the gate actually names as exempt/internal, not every html string it mentions
    keep = set()
    for block in re.findall(r"(?:EXEMPT|INTERNAL|EN_ONLY|EN_BY_DESIGN)[^=]*=\s*[\[{]([\s\S]{0,2000}?)[\]}]", src, re.I):
        for m in re.finditer(r"[\"']([a-z0-9-]+\.html)[\"']", block):
            keep.add(m.group(1))
    return keep or out


def is_prose(lit: str) -> bool:
    t = re.sub(r"\\[nrt]", " ", lit).strip()
    if len(t) < MIN_LETTERS or NOT_PROSE.match(t) or LOOKS_TECHNICAL.search(t):
        return False
    if LOOKS_LIKE_CSS.search(t):
        return False
    if "${" in t:                      # a template slot: the words around it still count, so keep going
        t = re.sub(r"\$\{[^}]*\}", " ", t)
    letters = sum(ch.isalpha() for ch in t)
    if letters < MIN_LETTERS or letters < len(t) * 0.45:
        return False
    words = [w for w in re.split(r"\s+", t.strip()) if any(c.isalpha() for c in w)]
    if len(words) < MIN_WORDS:
        return False
    # a bare Filipino string is not an offence — this gate is about ENGLISH shown under lang=fil.
    # The marker is cheap and deliberately loose: Filipino function words the copy always carries.
    fil = re.search(r"\b(ang|ng|mga|sa|para|hindi|walang|wala|kang|mo|ito|iyon|kapag|nang|ay)\b", t, re.I)
    return not fil


def _t_spans(js: str) -> list[tuple[int, int]]:
    """Character ranges covered by a _t( ... ) call, so an assignment inside one is not an offence."""
    spans = []
    for m in re.finditer(r"\b_t\s*\(", js):
        i, depth = m.end() - 1, 0
        while i < len(js):
            if js[i] == "(":
                depth += 1
            elif js[i] == ")":
                depth -= 1
                if depth == 0:
                    spans.append((m.start(), i))
                    break
            i += 1
    return spans


# ── innerHTML TEMPLATES — the blind spot ASSIGN's 300-char cap left open (2026-09-11) ──────────
# ASSIGN matches `.innerHTML = <q>literal</q>` with the literal capped at 300 chars, so a MULTI-LINE
# innerHTML template blows the cap and every bare English TEXT NODE inside it was invisible. Templates
# are how most of this platform renders its states, and the strings hiding there were the empty and
# error states a new person actually meets ("No projects yet", "Could not load your open items"). The
# gate read GREEN over them, which is why that class had to be found by a human walking a page in
# Filipino instead of by the instrument built to police it. Widening the cap was NOT the fix: the
# captured "literal" would be raw markup. This reads the template the way a BROWSER does - mask every
# ${...} interpolation, strip comments and tags, and grade what a person would actually read. A
# `${escHtml(_t('EN','FIL'))}` interpolation is masked with the rest, so a correctly translated
# template contributes nothing and no _t_spans bookkeeping is needed.
#
# ★THE FIRST VERSION OF THIS SCANNER REPORTED JAVASCRIPT AS PROSE. It counted `${` but decremented on
# every `}`, so marketplace's `${(() => { ... })()}` - an IIFE inside an interpolation - closed the
# interpolation on the ARROW FUNCTION'S brace, and 18 lines of `const _sp = ...` plus a /* */ comment
# were read as text a person sees. A gate that reports source code as untranslated copy is worse than
# the blind spot it replaced, so the scanner now tracks what it is actually inside: at template level
# only `${` and the closing backtick matter, and inside an expression EVERY brace counts, quoted
# strings and comments are skipped whole, and a nested template recurses.
# [[feedback_an_oracles_vocabulary_is_part_of_the_oracle]]
TPL_START = re.compile(r"\.(?:innerHTML|outerHTML)\s*=\s*`")
TPL_COMMENT = re.compile(r"<!--[\s\S]*?-->")
TPL_TAG = re.compile(r"<[^>]*>")


def _skip_quoted(js: str, i: int) -> int:
    """i points AT the opening quote; return the index just after the closing one."""
    q = js[i]
    i += 1
    while i < len(js):
        if js[i] == "\\":
            i += 2
            continue
        if js[i] == q:
            return i + 1
        i += 1
    return i


def _scan_template(js: str, i: int, mask: list | None):
    """i points just AFTER an opening backtick. Return the index of its closing backtick.

    When `mask` is given it is a per-character list over `js`; every character belonging to a ${...}
    interpolation is set to a space (newlines kept), so offsets - and line numbers - survive.
    """
    depth = 0                      # brace depth INSIDE ${ }
    while i < len(js):
        c = js[i]
        if c == "\\":
            i += 2
            continue
        if depth == 0:             # template TEXT: only these two characters matter
            if c == "`":
                return i
            if c == "$" and js[i + 1:i + 2] == "{":
                if mask is not None:
                    mask[i] = mask[i + 1] = " "
                depth = 1
                i += 2
                continue
            i += 1
            continue
        # inside a JS expression
        start = i
        if c in "'\"":
            i = _skip_quoted(js, i)
        elif c == "`":
            end = _scan_template(js, i + 1, None)
            i = end + 1
        elif c == "/" and js[i + 1:i + 2] == "*":
            j = js.find("*/", i + 2)
            i = len(js) if j < 0 else j + 2
        elif c == "/" and js[i + 1:i + 2] == "/":
            j = js.find("\n", i)
            i = len(js) if j < 0 else j
        elif c == "{":
            depth += 1
            i += 1
        elif c == "}":
            depth -= 1
            i += 1
        else:
            i += 1
        if mask is not None:
            for k in range(start, min(i, len(js))):
                if mask[k] != "\n":
                    mask[k] = " "
    return i


def _tpl_bodies(js: str):
    """Yield (offset_in_js, body_with_interpolations_masked) per `.innerHTML = `...`` template."""
    consumed_to = -1
    for m in TPL_START.finditer(js):
        if m.end() <= consumed_to:      # a template nested inside one already scanned
            continue
        start = m.end()
        mask = list(js)
        end = _scan_template(js, start, mask)
        consumed_to = end
        yield start, "".join(mask[start:end])


def _tpl_text_nodes(tpl: str):
    """Yield (offset_in_tpl, text) for what a reader would SEE inside the template.

    ★A TEXT NODE WHOSE OWN TAG CARRIES data-i IS ALREADY DECLARED TRANSLATED (2026-09-11). marketplace
    renders `<button ... data-i="clearfilters">Clear filters</button>` and `data-i="contactseller">
    Contact Seller` INSIDE a template: the English in the source is the FALLBACK that whI18nApply swaps,
    which is the platform's normal static contract, not an untranslated string. Blanking every tag
    uniformly threw that away and reported both as gaps. The stamped case is the sibling of ASSIGN's
    `_t_spans` exemption - one mechanism per shape, the stamp for markup and `_t()` for runtime strings.
    Whether a stamp actually TOOK EFFECT is a live question a static gate cannot answer and the N1 dim
    already owns ([[feedback_the_ruler_graded_the_wiring_not_the_words]]); here the declaration is the
    contract, and a string with neither a stamp nor a `_t()` has no contract at all.
    """
    def blank_run(s, a, b):
        return s[:a] + re.sub(r"\S", " ", s[a:b]) + s[b:]

    s = TPL_COMMENT.sub(lambda mm: re.sub(r"\S", " ", mm.group(0)), tpl)
    stamped = bytearray(len(s))          # 1 where a character sits inside a data-i element's text
    out = []
    for mm in TPL_TAG.finditer(s):
        tag = mm.group(0)
        if re.match(r"<\s*[A-Za-z]", tag) and "data-i" in tag and not tag.rstrip().endswith("/>"):
            # mark up to the next tag: that run is this element's own text
            nxt = TPL_TAG.search(s, mm.end())
            for k in range(mm.end(), nxt.start() if nxt else len(s)):
                stamped[k] = 1
        out.append((mm.start(), mm.end()))
    for a, b in out:
        s = blank_run(s, a, b)
    pos = 0
    for line in s.split("\n"):
        stripped = line.strip()
        if stripped:
            off = pos + (len(line) - len(line.lstrip()))
            if not stamped[off]:
                yield off, stripped
        pos += len(line) + 1


def scan_page(path: Path) -> list[dict]:
    html = io.open(path, encoding="utf-8", errors="replace").read()
    if "data-i=" not in html:                 # never claimed to be bilingual
        return []
    if DISPOSITION_RE.search(html):           # the page DECLARES an EN body (formal doc / EN publication)
        return []
    stamped = set(STAMPED_ID.findall(html)) | set(STAMPED_ID_REV.findall(html))
    out: list[dict] = []
    for sm in SCRIPT.finditer(html):
        js, base = sm.group(1), sm.start(1)
        safe = _t_spans(js)

        def emit(m, prop, kind):
            # the LITERAL's position decides, not the statement's: in
            # `b.textContent = _t('English','Filipino')` the statement starts BEFORE the _t( call
            # and only the string sits inside it.
            if any(a <= m.start("lit") <= b for a, b in safe):
                return
            lit = m.group("lit")
            if not is_prose(lit):
                return
            window = js[max(0, m.start() - 400):m.start()]
            hit_id = next((i for i in stamped if f"'{i}'" in window or f'"{i}"' in window), None)
            out.append({
                "line": html[:base + m.start()].count("\n") + 1,
                "shape": "overwrite" if hit_id else kind,
                "stamped_id": hit_id or "",
                "prop": prop,
                "literal": re.sub(r"\s+", " ", lit)[:110],
            })

        for m in ASSIGN.finditer(js):
            emit(m, m.group(1), "unwrapped")
        # follow the variables that reach a text property
        for ident in sorted(set(SINK_IDENT.findall(js))):
            if len(ident) < 2 or ident in ("e", "html", "s"):
                continue
            for m in re.finditer(IDENT_LIT % re.escape(ident), js):
                emit(m, f"{ident}->textContent", "via-variable")
        for m in LABEL_CALL.finditer(js):
            emit(m, m.group(1) + "()", "label-call")
        # bare English TEXT NODES inside an innerHTML template (see _tpl_bodies above)
        for toff, tpl in _tpl_bodies(js):
            for rel, text in _tpl_text_nodes(tpl):
                if not is_prose(text):
                    continue
                out.append({
                    "line": html[:base + toff + rel].count("\n") + 1,
                    "shape": "template-text",
                    "stamped_id": "",
                    "prop": "innerHTML`...`",
                    "literal": re.sub(r"\s+", " ", text)[:110],
                })
    # one literal can be reached by two rules (a variable that is also a label arg); keep it once
    seen, uniq = set(), []
    for h in sorted(out, key=lambda h: (h["line"], h["shape"] != "overwrite")):
        k = (h["line"], h["literal"])
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    return uniq


def census() -> dict[str, list[dict]]:
    ex = exempt_pages()
    out = {}
    for p in sorted(ROOT.glob("*.html")):
        if p.name in ex:
            continue
        hits = scan_page(p)
        if hits:
            out[p.name] = hits
    return out


def load_baseline() -> dict:
    try:
        return json.loads(io.open(BASELINE, encoding="utf-8").read())
    except (OSError, ValueError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    c = census()
    counts = {k: len(v) for k, v in c.items()}
    total = sum(counts.values())
    overwrites = sum(1 for v in c.values() for h in v if h["shape"] == "overwrite")

    if a.report:
        for page, hits in sorted(c.items(), key=lambda kv: -len(kv[1])):
            print(f"\n{page}  ({len(hits)})")
            for h in hits:
                tag = f"OVERWRITE via #{h['stamped_id']}" if h["shape"] == "overwrite" else "unwrapped"
                line = f"  L{h['line']:<6} {tag:<34} .{h['prop']} = {h['literal']!r}"
                print(line.encode("ascii", "replace").decode("ascii"))
        print(f"\n  {total} literal(s) across {len(c)} page(s) · {overwrites} overwrite a stamped element")
        return 0

    if a.accept:
        io.open(BASELINE, "w", encoding="utf-8").write(
            json.dumps({"counts": counts, "total": total, "overwrites": overwrites}, indent=1, sort_keys=True) + "\n")
        print(f"baseline frozen: {total} literal(s) across {len(c)} page(s) ({overwrites} overwrites)")
        return 0

    base = load_baseline()
    bc = base.get("counts", {})
    print("rendered-i18n — English prose written by JS onto pages that claim to be bilingual")
    print(f"  pages: {len(c)}  ·  literals: {total} (baseline {base.get('total', '?')})"
          f"  ·  overwriting a stamped element: {overwrites} (baseline {base.get('overwrites', '?')})")
    if not base:
        print("  no baseline yet — run --accept once to freeze the current census")
        return 0
    risen = {k: (bc.get(k, 0), v) for k, v in counts.items() if v > bc.get(k, 0)}
    fell = sum(max(0, bc.get(k, 0) - counts.get(k, 0)) for k in bc)
    if risen:
        print("  FAIL — these pages gained English JS prose since the baseline:")
        for k, (was, now) in sorted(risen.items()):
            print(f"    {k}: {was} -> {now}")
        print("  wrap the new string in _t('English','Filipino'), or re-baseline with --accept if intended.")
        return 1
    if fell:
        print(f"  PASS - ratchet held; {fell} literal(s) fewer than the baseline. Re-freeze with --accept.")
    else:
        print("  PASS - ratchet held.")
    return 0


def self_test() -> int:
    fails = []
    # is_prose
    for good in ["Review 2 pending", "No assets yet. Add equipment.", "Order the long-lead parts first."]:
        if not is_prose(good):
            fails.append(f"is_prose rejected prose: {good!r}")
    for bad in ["OK", "12", "  ", "#pending-assets-card", "https://x.y/z", "font-size: 12px;",
                "Wala pang asset dito", "Ano ang susunod na gagawin"]:
        if is_prose(bad):
            fails.append(f"is_prose accepted non-offence: {bad!r}")
    # A _t()-wrapped assignment must never be an offence. The plain form is safe by CONSTRUCTION -
    # `_t(` sits between the `=` and the quote, so ASSIGN does not match it at all. _t_spans is the net
    # for the mixed forms that DO match, e.g. a ternary whose other arm is a bare literal.
    js = "b.textContent = _t('Review 2 pending', 'Suriin ang 2 pending');"
    if ASSIGN.search(js):
        fails.append("a plainly _t()-wrapped assignment was matched as a bare literal")
    # ★THE REAL SHAPE: the literal is assigned to a VARIABLE that reaches textContent once at the end.
    # This is exactly asset-hub's block, and the first version of this gate could not see it.
    tmp = ROOT / ".tmp" / "_rendered_i18n_selftest.html"
    tmp.parent.mkdir(exist_ok=True)
    io.open(tmp, "w", encoding="utf-8").write(
        '<p data-i="p_x" id="ah-action-text">x</p><script>'
        "let text; if (a) { text = 'No assets yet. Add equipment from PM Scheduler.'; }"
        " else { text = _t('Registry looks complete now', 'Kumpleto na ang registry'); }"
        " actBox.textContent = text;</script>")
    hits = scan_page(tmp)
    lits = [h["literal"] for h in hits]
    if lits != ["No assets yet. Add equipment from PM Scheduler."]:
        fails.append(f"variable-to-textContent shape not detected cleanly, got {lits}")
    # a label handed straight to a renderer
    io.open(tmp, "w", encoding="utf-8").write(
        '<a data-i="p_y" id="b">y</a><script>setCta(\'Review 2 pending now\', {});</script>')
    if not any(h["literal"] == "Review 2 pending now" for h in scan_page(tmp)):
        fails.append("a bare label passed to setCta() was not caught")
    # an unwrapped one is caught
    js2 = "b.textContent = 'Review 2 pending';"
    m2 = ASSIGN.search(js2)
    if not (m2 and is_prose(m2.group("lit")) and not _t_spans(js2)):
        fails.append("an unwrapped assignment was not caught")
    # shape A needs the stamped id in the preceding window
    html = ('<a data-i="p_takeaction_ee0b" id="ah-action-btn">Take action</a>'
            "<script>const b=document.getElementById('ah-action-btn'); b.textContent = 'Review 2 pending';</script>")
    tmp = ROOT / ".tmp" / "_rendered_i18n_selftest.html"
    tmp.parent.mkdir(exist_ok=True)
    io.open(tmp, "w", encoding="utf-8").write(html)
    hits = scan_page(tmp)
    if not (len(hits) == 1 and hits[0]["shape"] == "overwrite" and hits[0]["stamped_id"] == "ah-action-btn"):
        fails.append(f"overwrite shape not detected: {hits}")
    # a page with no stamps is not this gate's business
    io.open(tmp, "w", encoding="utf-8").write("<script>x.textContent = 'Review 2 pending';</script>")
    if scan_page(tmp):
        fails.append("flagged a page that never claimed to be bilingual")
    tmp.unlink(missing_ok=True)
    print("PASS validate_rendered_i18n self-test - 5/5" if not fails
          else "FAIL validate_rendered_i18n self-test - " + "; ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
