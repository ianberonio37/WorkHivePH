"""
prove_article_ui_claims.py — an article may only tell a reader to press something real.
=======================================================================================
WHY THIS EXISTS (2026-09-21, W46181). learn/philippine-plants-now-pay-the-highest-power-rates
walked out of the audit lens measuring perfect — contrastLow 0 across 163 nodes, rhythmOffGrid
0, 10 headings with 0 skips — while instructing the reader, five separate times and in
numbered steps, to "Press the ⚡ Electrical 14 button", then claiming the tool "flags any
machine over the limit", "pulls the DOE's current rate" and "applies the RA 11285 audit rule".
None of that exists. The string "Electrical 14" occurs exactly once in the whole repository:
inside an HTML COMMENT in engineering-design.html listing discipline counts. An LLM read the
comment and turned it into a button.

★THE GUARD THAT ALREADY EXISTED WAS POINTED AT THE CHEAPER SURFACE. tools/topic_post.py
carries a real, self-tested fabrication guard — `numbers_sourced` traces every figure back to
the notes Ian supplied, and it earned its place on run one by catching an invented
"11.8 cent per kilowatt-hour" in the wrong currency. But it runs on the FACEBOOK CAPTION.
The /learn article, which is the durable surface — indexed, linked from the hub, mirrored into
a markdown twin, quoted by answer engines — goes out through scaffold_article with no
equivalent check. The ephemeral thing was guarded and the permanent one was not. This closes
that half for the claims a machine can actually adjudicate: whether a named control exists.

WHAT IT CAN AND CANNOT DO, stated plainly so nobody mistakes a green run for a true article.
It checks one thing: a control an article tells you to press is a control the app renders.
It cannot check that a statistic is real (authority_link_gate checks that the citation
RESOLVES, which is the closest mechanical proxy), that arithmetic is sound — the same page
claimed a 500-kW boiler room drawing 12 kWh an hour saved ₱3,000 a day, which is off by about
ten times — or that a described behaviour exists. Those need a reader. This catches the
specific, repeatable failure of an LLM inventing an affordance.

MEASURED AT FIRST RUN: 21 instructed controls across 5 articles, and after the W46181 repair
all 21 resolve. So this registers GREEN and works as a ratchet: it does not have a backlog to
burn down, it stops the next generated article from reintroducing the defect.

RUN:  python tools/prove_article_ui_claims.py            # report
      python tools/prove_article_ui_claims.py --check    # exit 1 if any control is invented
      python tools/prove_article_ui_claims.py --self-test
"""
from __future__ import annotations

import glob
import html
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# A control the prose tells the reader to operate: a <strong> span that either follows an
# imperative, or carries the emoji/arrow the app puts on its own buttons.
UI_RE = re.compile(r"<strong>([^<]{2,42})</strong>")
VERB_RE = re.compile(r"(press|click|open|select|pick|tap|choose|hit)\s+(the\s+)?$", re.I)
GLYPH_RE = re.compile(r"[←-➿\U0001f300-\U0001faff]")
# Leading glyphs/space/quotes are decoration, not the label.
_STRIP = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)

# Words that are prose emphasis rather than a control name, even after an imperative.
NOT_A_CONTROL = {"the", "and", "or", "not", "now", "first", "next", "free", "yes", "no"}


_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
# ★`accept="image/*"` IS NOT A COMMENT OPENER. A bare /\*.*?\*/ paired the `/*` inside that
# attribute with the next real `*/` and deleted 10,553 characters of resume.html — including
# the genuine `✨ Polish my experience wording` button — which made this gate report a real
# control as invented. That is this project's own recorded lesson repeating itself verbatim
# ([[feedback_accept_image_star_broke_comment_stripping]]), so the opener is anchored: a
# comment starts at a line start or after whitespace/;/{/}, never mid-token inside a quoted
# attribute value. Block comments are also stripped from .js only; HTML has no /*…*/ of its
# own, and a CSS comment inside <style> cannot plausibly name a button.
_BLOCK_COMMENT = re.compile(r"(?:(?<=^)|(?<=[\s;{}]))/\*.*?\*/", re.S | re.M)
_LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")


def app_surface() -> str:
    """Every shipped page and script EXCEPT the articles themselves, and EXCEPT comments.

    The articles are excluded deliberately: if an article could satisfy this check with its
    own prose, a fabricated control would prove itself. The claim has to be paid for by the
    application, not by the sentence making it.

    ★COMMENTS ARE STRIPPED, AND THAT IS THE WHOLE POINT OF THE GATE. The first version of
    this file kept them, and its own teeth test failed: "Electrical 14" — the invented button
    that caused all this — IS present in the repository, inside an HTML comment in
    engineering-design.html listing discipline counts. An LLM read that comment and promoted
    it to a button; a gate that also reads comments would bless the result. A control that
    exists only in a comment is not a control. This is the same discipline as reading the
    ACTIVE cache_name in sw.js instead of the commented history above it: a comment is not
    the code, and quoting one is not reading it.
    """
    buf = []
    for pat in ("*.js", "*.html"):
        for f in sorted(glob.glob(str(ROOT / pat))):
            src = Path(f).read_text(encoding="utf-8", errors="replace")
            src = _HTML_COMMENT.sub(" ", src)
            if f.endswith(".js"):
                src = _BLOCK_COMMENT.sub(" ", src)
                src = _LINE_COMMENT.sub(" ", src)
            buf.append(src)
    return re.sub(r"\s+", " ", html.unescape("\n".join(buf))).lower()


def instructed_controls(pages: list[str] | None = None) -> list[tuple[str, str, str]]:
    """[(page, label_as_written, normalised_core)] for every control an article names."""
    out: list[tuple[str, str, str]] = []
    pages = pages if pages is not None else sorted(glob.glob(str(ROOT / "learn/*/index.html")))
    for f in pages:
        text = Path(f).read_text(encoding="utf-8", errors="replace")
        rel = os.path.relpath(f, ROOT).replace("\\", "/")
        for m in UI_RE.finditer(text):
            before = re.sub(r"<[^>]+>", "", text[max(0, m.start() - 40):m.start()])
            label = m.group(1).strip()
            if not (VERB_RE.search(before) or GLYPH_RE.search(label)):
                continue
            core = _STRIP.sub("", html.unescape(label)).strip()
            if not core or core.lower() in NOT_A_CONTROL:
                continue
            out.append((rel, label, core))
    return out


def audit(surface: str | None = None, pages: list[str] | None = None) -> dict:
    surface = surface if surface is not None else app_surface()
    rows = []
    for page, label, core in instructed_controls(pages):
        rows.append({"page": page, "label": label, "core": core,
                     "exists": core.lower() in surface})
    return {"rows": rows,
            "missing": [r for r in rows if not r["exists"]],
            "total": len(rows),
            "pages": len({r["page"] for r in rows})}


def run(check: bool = False) -> int:
    rep = audit()
    print("=" * 70)
    print("  ARTICLE UI CLAIMS — is the button we tell them to press a real button?")
    print("=" * 70)
    print("  %d instructed control(s) across %d article(s)   invented: %d"
          % (rep["total"], rep["pages"], len(rep["missing"])))
    for r in rep["missing"]:
        print("    INVENTED  %r" % r["label"])
        print("              %s" % r["page"])
    if rep["missing"]:
        print("-" * 70)
        print("  FAIL — an article names a control this app does not render.")
        print("  FIX: correct the label to the control that exists, or delete the")
        print("       instruction. Do not add the button to make the article true.")
        print("=" * 70)
        return 1 if check else 0
    print("-" * 70)
    print("  PASS — every control an article tells a reader to press exists.")
    print("=" * 70)
    return 0


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print("  %s  %s" % ("PASS" if c else "FAIL", m))

    surface = app_surface()
    ck(len(surface) > 50_000, "the app surface is actually loaded (%d chars)" % len(surface))

    rows = instructed_controls()
    ck(len(rows) >= 5, "finds controls that articles instruct the reader to press (%d)" % len(rows))

    # TEETH. A fabricated control must fail, and the real one beside it must pass.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        good = Path(d) / "good.html"
        bad = Path(d) / "bad.html"
        good.write_text("<p>Press the <strong>Download PDF</strong> button.</p>", encoding="utf-8")
        bad.write_text("<p>Press the <strong>⚡ Electrical 14</strong> button.</p>", encoding="utf-8")
        g = audit(surface, [str(good)])
        b = audit(surface, [str(bad)])
        ck(g["total"] == 1 and not g["missing"], "a real control passes")
        ck(b["total"] == 1 and len(b["missing"]) == 1,
           "the exact fabricated control that shipped ('Electrical 14') is caught")

    # The comment that fooled the model must NOT be able to satisfy the check. This is the
    # assertion that failed on the first draft and forced the comment-stripping above.
    ck("electrical 14" not in surface,
       "the HTML comment that invented the label is NOT part of the surface")
    ck("download pdf" in surface, "a genuinely rendered control still is")
    # ★the false positive that comment-stripping caused, pinned so it cannot come back
    ck("polish my experience wording" in surface,
       "a real button is NOT eaten by the `/*` inside accept=\"image/*\"")
    ck(_BLOCK_COMMENT.sub(" ", 'x accept="image/*" y */ z') == 'x accept="image/*" y */ z',
       "`/*` inside a quoted attribute does not open a comment")
    ck(_BLOCK_COMMENT.sub(" ", "a /* real */ b").split() == ["a", "b"],
       "a real block comment is still stripped")

    ck(not audit(surface)["missing"], "the live corpus is clean, so this registers as a ratchet")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--self-test" in argv:
        raise SystemExit(self_test())
    raise SystemExit(run(check="--check" in argv))
