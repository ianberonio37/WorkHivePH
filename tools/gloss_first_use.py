"""gloss_first_use.py - a domain acronym is explained on the page that uses it (SL F4, 2026-10-16).

The F4 walk read 155 pages as a person reads them (innerText, at 390 and 1280) and found 119 domain acronyms rendered
with nothing on the same page saying what they stand for - "accurate MTBF", "LOTO permits", "Best free CMMS software",
"which KPI to chase" - on 41 learn articles, the two reliability calculators and nine app pages. The platform's own
glossary rule (validate_glossary_registry.py) accepts a term that is taught SOMEWHERE in the learn cluster; a crew
member reading one article does not go and find another. The plain-words rule is: the page that says it, explains it.

What this does, on the STATIC content pages (learn articles, the calculators, about/privacy/terms/feedback):
  * a term is GLOSSED when its expansion appears anywhere a reader can reach on the page (visible text, an <abbr>'s or
    any element's title, an aria-label) - the same test as the walk and as tools/prove_jargon_is_glossed.mjs;
  * an unglossed term is glossed at its FIRST use in body prose (a <p>, <li>, <td>, <dd>, <blockquote> or
    <figcaption>, never inside a heading, a link, a button, code or the site chrome) as "MTBF (mean time between
    failures)" - visible, because a title on a phone is a tooltip nobody can hover;
  * a term that appears only outside prose (a link label, a heading) is wrapped once as <abbr title="...">.
It is idempotent: a glossed page is never touched again.

  python tools/gloss_first_use.py --check            # gate: exit 1 if any static page shows a term it never explains
  python tools/gloss_first_use.py --apply [files]    # gloss every static page (or the files named)
  python tools/gloss_first_use.py --self-test        # teeth
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# acronym -> what a crew calls it. The walk's oracle (f4_walk_template TERMS) checks a SUBSTRING of each, so every
# expansion here contains that substring ("lock-out", "maintenance management", "key performance", "failure mode").
TERMS = {
    "MTBF": "mean time between failures",
    "MTTR": "mean time to repair",
    "OEE": "overall equipment effectiveness",
    "RCM": "reliability-centered maintenance",
    "FMEA": "failure mode and effects analysis",
    "RPN": "risk priority number",
    "LOTO": "lock-out/tag-out",
    "CMMS": "computerized maintenance management system",
    "SOW": "scope of work",
    "BOM": "bill of materials",
    "PPE": "personal protective equipment",
    "KPI": "key performance indicator",
}
PROSE = {"p", "li", "td", "dd", "blockquote", "figcaption"}
NOT_PROSE = {"a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "script", "style", "button", "summary", "label",
             "abbr", "title", "option", "nav", "header", "footer", "sup", "sub", "noscript", "template", "textarea",
             "select", "svg"}
HIDDEN = {"script", "style", "noscript", "template", "title", "head"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
TOKEN = re.compile(r"<!--.*?-->|<[^>]+>|[^<]+", re.S)


def term_re(t: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])")


def abbr(text_html: str) -> str:
    """Wrap each known acronym in already-escaped text with <abbr title> - for a label (a link, a heading) where a
    parenthesis would read badly. Used by the calculator generator for its sibling links."""
    for t, x in TERMS.items():
        text_html = term_re(t).sub(lambda m: f'<abbr title="{x}">{m.group(0)}</abbr>', text_html)
    return text_html


def _walk(src: str):
    """Yield (kind, start, end, token, stack) over the BODY, with the stack of open element names at each token."""
    m = re.search(r"<body\b[^>]*>", src, re.I)
    start = m.end() if m else 0
    end_m = re.search(r"</body\s*>", src, re.I)
    end = end_m.start() if end_m else len(src)
    stack = []
    for tm in TOKEN.finditer(src, start, end):
        tok = tm.group(0)
        if tok.startswith("<!--"):
            continue
        if tok.startswith("<"):
            nm = re.match(r"</?\s*([a-zA-Z][a-zA-Z0-9-]*)", tok)
            if not nm:
                continue
            name = nm.group(1).lower()
            if tok.startswith("</"):
                if name in stack:
                    while stack and stack.pop() != name:
                        pass
            elif name not in VOID and not tok.rstrip().endswith("/>"):
                stack.append(name)
            yield "tag", tm.start(), tm.end(), tok, list(stack)
        else:
            yield "text", tm.start(), tm.end(), tok, list(stack)


def reachable(src: str) -> str:
    """What a reader can reach: visible body text plus every title and aria-label - lowercased, entities decoded."""
    parts = []
    for kind, _s, _e, tok, stack in _walk(src):
        if kind == "text" and not (set(stack) & HIDDEN):
            parts.append(tok)
        elif kind == "tag":
            parts += re.findall(r'\b(?:title|aria-label)\s*=\s*"([^"]*)"', tok, re.I)
    return html.unescape(" ".join(parts)).lower()


def visible_text(src: str) -> str:
    return html.unescape(" ".join(tok for k, _s, _e, tok, st in _walk(src) if k == "text" and not (set(st) & HIDDEN)))


# other spellings of the same words that already gloss a term ("lockout/tagout" is the OSHA spelling of LOTO)
ALSO = {"LOTO": ["lockout"]}


def unglossed(src: str) -> list[str]:
    vis, hay = visible_text(src), reachable(src)
    return [t for t, x in TERMS.items() if term_re(t).search(vis) and x.lower() not in hay
            and not re.search(re.escape(x.split("/")[0].split(" and ")[0]), hay)
            and not any(a in hay for a in ALSO.get(t, []))]


def gloss(src: str) -> tuple[str, list[str]]:
    done = []
    for t in unglossed(src):
        x = TERMS[t]
        rx = term_re(t)
        target = None
        for kind, s, e, tok, stack in _walk(src):           # first use in body prose
            if kind == "text" and set(stack) & PROSE and not (set(stack) & NOT_PROSE) and rx.search(tok):
                m = rx.search(tok)
                target = ("paren", s + m.end())
                break
        if target is None:
            for kind, s, e, tok, stack in _walk(src):       # else: its first visible use, as an <abbr>
                if kind == "text" and not (set(stack) & (HIDDEN | {"abbr", "textarea", "option"})) and rx.search(tok):
                    m = rx.search(tok)
                    target = ("abbr", s + m.start(), s + m.end())
                    break
        if target is None:
            continue
        if target[0] == "paren":
            # a first use already inside parentheses ("…failure pattern (MTBF)") reads "(MTBF: mean time between
            # failures)", never "(MTBF (mean time between failures))"
            inside = src[target[1] - len(t) - 1:target[1] - len(t)] == "(" and src[target[1]:target[1] + 1] == ")"
            src = src[:target[1]] + (f": {x}" if inside else f" ({x})") + src[target[1]:]
        else:
            src = src[:target[1]] + f'<abbr title="{x}">{t}</abbr>' + src[target[2]:]
        done.append(t)
    return src, done


def static_pages() -> list[Path]:
    out = []
    for d in ("learn", "tools", "about", "privacy-policy", "terms-of-service", "feedback"):
        base = ROOT / d
        if base.is_dir():
            out += [p for p in base.rglob("index.html") if "_bak" not in str(p)]
    return sorted(out)


def self_test() -> int:
    fails = []
    page = "<html><head><title>MTBF guide</title></head><body><nav><a>MTBF</a></nav><h1>MTBF basics</h1><p>Track MTBF weekly.</p></body></html>"
    got, done = gloss(page)
    if "Track MTBF (mean time between failures) weekly." not in got or done != ["MTBF"]:
        fails.append("first prose use must gain a visible expansion")
    if "<h1>MTBF basics</h1>" not in got or "<a>MTBF</a>" not in got:
        fails.append("a heading and a link must be left alone when prose carries the gloss")
    if gloss(got)[1]:
        fails.append("a glossed page must not be glossed twice")
    only_link = "<body><p>See the <a href='/x'>OEE calculator</a>.</p></body>"
    got2, _ = gloss(only_link)
    if '<abbr title="overall equipment effectiveness">OEE</abbr>' not in got2:
        fails.append("a term only in a link must be wrapped as <abbr title>")
    already = "<body><p>Mean time between failures (MTBF) is the average.</p><p>MTBF again.</p></body>"
    if gloss(already)[1]:
        fails.append("a page that already spells it out must be left alone")
    plural = "<body><p>Our KPIs and the CMMSs.</p></body>"
    if unglossed(plural):
        fails.append("a plural is not the bare term (the walk reads the exact token)")
    script = "<body><script>var MTBF = 1;</script><p>Nothing here.</p></body>"
    if unglossed(script):
        fails.append("a term inside a script is not rendered text")
    nested = "<body><p>Match the failure pattern (MTBF), not a schedule.</p></body>"
    if "(MTBF: mean time between failures)" not in gloss(nested)[0]:
        fails.append("a first use inside parentheses must read '(MTBF: ...)', not nest a second pair")
    print(f"self-test: {8 - len(fails)}/8 cases read as planted")
    for f in fails:
        print("  WRONG:", f)
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    files = [Path(a) for a in sys.argv[1:] if not a.startswith("--")] or static_pages()
    if "--apply" in sys.argv:
        n = 0
        for p in files:
            src = p.read_text(encoding="utf-8")
            new, done = gloss(src)
            if done:
                p.write_text(new, encoding="utf-8")
                n += 1
                print(f"  {p.relative_to(ROOT).as_posix()}: glossed {', '.join(done)}")
        print(f"glossed {n} page(s)")
        return 0
    # the client twin: utils.js WH_GLOSS glosses the acronyms in rendered text (posts, labels) and must name the same
    # terms with the same words, or a page and an article would explain one acronym two ways
    m = re.search(r"var WH_GLOSS = \{(.*?)\};", (ROOT / "utils.js").read_text(encoding="utf-8"), re.S)
    client = dict(re.findall(r"(\w+):\s*'([^']+)'", m.group(1))) if m else {}
    if client != TERMS:
        drift = sorted(set(client.items()) ^ set(TERMS.items()))
        print(f"FAIL jargon-glossed: utils.js WH_GLOSS and this registry disagree: {drift[:6]}")
        return 1
    bad = [(p, unglossed(p.read_text(encoding="utf-8"))) for p in files]
    bad = [(p, t) for p, t in bad if t]
    if bad:
        print(f"FAIL jargon-glossed: {len(bad)} static page(s) show a domain acronym they never explain")
        for p, t in bad:
            print(f"   {p.relative_to(ROOT).as_posix()}: {', '.join(t)}")
        return 1
    print(f"PASS jargon-glossed: every domain acronym on {len(files)} static pages is explained on the page that uses it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
