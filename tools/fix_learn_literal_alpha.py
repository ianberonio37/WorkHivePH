#!/usr/bin/env python3
"""fix_learn_literal_alpha.py - carry the platform's contrast ramp to the learn pages' HAND-WRITTEN rgba.

★THE REMAP REACHED ONE MECHANISM OF TWO (walked 2026-09-11, learn/what-is-oee-how-to-calculate,
solo owner, phone-390). tools/fix_learn_contrast_remap.py already carried wh-tw.css's white-opacity
decision to all 54 articles - verified, the marker is in every one. It remaps Tailwind's
`text-white/NN` UTILITY classes. But the learn chrome and prose are ALSO coloured by literal
`rgba(244,246,250,a)` declarations written directly in each page's inline <style>, and those never
heard the decision: 589 text-colour declarations under alpha 0.8 across 54 pages, untouched.

WHAT THE ORACLE SAID, AFTER I READ IT WRONG. C5 reported "101 pass WCAG but miss APCA Lc". Measuring
by hand I found 13 and concluded the failures were the small low-alpha chrome, so the body prose at
0.78 could be left alone. That was BACKWARDS. Exporting the rubric's own offender list (c5_offenders,
added in the same turn - the dim had been spending its list on one clause of a note and dropping it)
showed 97 of the 101 are BODY PROSE at Lc 68-71, and only 4 are nav chrome at Lc 54. The gap was
APCA's Lc 75 floor for "columns of fluent body text" against Lc 60 for a UI label - a distinction only
the oracle applies. Calibration then reproduced its Lc 70 for the 0.78 prose exactly, and solved the
minimum for Lc 75 at 0.82.

WHY THE PLATFORM'S RAMP AND NOT 0.82. 0.82 is the bare minimum for one size; wh-tw.css already
declares this platform's answer (45/50/55/60 -> 0.8, 65/70/75 -> 0.85), and 0.85 clears Lc 75 with
margin. Reusing that ramp keeps ONE contrast decision across both mechanisms instead of inventing a
second number that happens to pass today. 0.4 joins the lower bucket and 0.78 the upper, by neighbour.

SCOPED TO TEXT COLOUR ONLY. The pattern requires `color:` NOT preceded by a hyphen or letter, so
`border-color`, `outline-color`, `background`, `box-shadow`, `fill` and `stroke` are all excluded -
raising a border's alpha would be a design change, not a contrast fix. Measured before writing: of the
589 matches, 0 were decorative, but the guard stays so a future page cannot smuggle one in.

  python tools/fix_learn_literal_alpha.py              # dry run (default)
  python tools/fix_learn_literal_alpha.py --apply
  python tools/fix_learn_literal_alpha.py --self-test
"""
from __future__ import annotations

import glob
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The platform's own ramp, from wh-tw.css (see tools/fix_learn_contrast_remap.py).
# 0.4 joins the lower bucket, 0.78 the upper, by neighbour.
RAMP = {"0.4": "0.8", ".4": "0.8", "0.45": "0.8", "0.5": "0.8", ".5": "0.8",
        "0.55": "0.8", "0.6": "0.8", ".6": "0.8",
        "0.65": "0.85", "0.7": "0.85", ".7": "0.85", "0.75": "0.85", "0.78": "0.85"}

# `color:` only - never border-color / outline-color / -webkit-text-fill-color etc.
DECL = re.compile(
    r"(?<![-a-zA-Z])(color\s*:\s*rgba\(\s*244\s*,\s*246\s*,\s*250\s*,\s*)(0?\.\d+)(\s*\))",
    re.IGNORECASE,
)

# ── the hex half of the same job: the FORMULA blocks ────────────────────────────
# After the alpha remap the article's C5 went 41% -> 94%, and every one of the 11 survivors was a
# formula in `.prose-wh code` / `.prose-wh pre` at brand orange #FDB94A: Lc 67 on the code panel's
# own lighter background [40,42,48], against APCA's Lc 75 content floor.
# WHY THESE ARE NOT EXCUSED WHILE THE OTHER ORANGE IS. The rubric deliberately gives brand-accent
# text the Lc 60 label floor when it sits inside a link, summary, pill or heading - so `.toc a:hover`,
# `.tool-cta a`, `.faq-item[open] summary` and the pills stay at #FDB94A and correctly pass. A formula
# is none of those: it is CONTENT, and code is read glyph by glyph, where a 1/l confusion is the whole
# cost. So it earns the content floor rather than an exemption - the one place where "it's brand
# accent" would have been the comfortable answer and the wrong one.
# #FED38D is #FDB94A blended 37% toward white: Lc 78, matching the platform's own practice that muted
# fixes land at Lc 77+ rather than scraping the 75 line. Same hue, still legibly the brand orange.
# Each entry: (selector pattern, from-hex, to-hex, why). Rule-SCOPED, so the same hex used elsewhere -
# in a link, summary or pill, where the rubric's Lc 60 label floor applies and it already passes - is
# never touched. Both entries were solved numerically against the element's OWN background and then
# checked against the oracle's published Lc, not against my arithmetic alone.
HEX_RULES = [
    (re.compile(r"\.prose-wh\s+(?:code|pre)\b"), "#FDB94A", "#FED38D",
     "formula blocks: Lc 67 on the code panel's ground vs APCA's Lc 75 content floor"),
    (re.compile(r"\.callout\s+strong\b"), "#5FCCE8", "#A4E2F2",
     "the bold lead-in inside a prose callout: Lc 63.6 vs 75 (computed on the callout's own tinted "
     "background rgb(23,41,60); the oracle independently reported 64, which calibrated the formula). "
     "42 pages. NOT the same as .prose-wh a, which is the identical hex inside a LINK and correctly "
     "passes at the Lc 60 label floor - the difference is prose vs label, not the colour."),
]
RULE = re.compile(r"([^{}]*)\{([^{}]*)\}")


def remap(src: str) -> tuple[str, int, list[str]]:
    """Return (new_src, n_changed, skipped_alphas)."""
    changed = 0
    skipped: list[str] = []

    def sub(m: re.Match) -> str:
        nonlocal changed
        head, alpha, tail = m.group(1), m.group(2), m.group(3)
        key = alpha.lstrip("0") if alpha.startswith("0.") else alpha
        target = RAMP.get(alpha) or RAMP.get(key)
        if target is None:
            if float(alpha) < 0.8:
                skipped.append(alpha)
            return m.group(0)
        if float(alpha) >= 0.8:
            return m.group(0)          # already compliant; leave it
        changed += 1
        return f"{head}{target}{tail}"

    new = DECL.sub(sub, src)
    new, n_code = remap_code_hex(new)
    return new, changed + n_code, skipped


def remap_code_hex(src: str) -> tuple[str, int]:
    """Lift the prose colours named in HEX_RULES. Rule-scoped: the same hex inside a link/summary/pill
    rule (correctly excused at the Lc 60 label floor) is never touched, and only `color:` is rewritten
    so a border or background carrying that hex is left alone."""
    changed = 0

    def sub(m: re.Match) -> str:
        nonlocal changed
        sel, body = m.group(1), m.group(2)
        for sel_re, src_hex, dst_hex, _why in HEX_RULES:
            if not sel_re.search(sel):
                continue
            pat = re.compile(r"((?<![-a-zA-Z])color\s*:\s*)" + re.escape(src_hex), re.IGNORECASE)
            body, n = pat.subn(lambda mm: mm.group(1) + dst_hex, body)
            changed += n
        return f"{sel}{{{body}}}"

    return RULE.sub(sub, src), changed


def targets() -> list[Path]:
    out = [Path(p) for p in sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))]
    idx = ROOT / "learn" / "index.html"
    if idx.exists():
        out.append(idx)
    return out


def self_test() -> int:
    cases = [
        # (input, expected-substring, must-not-contain)
        ("color: rgba(244,246,250,0.78)", "250,0.85)", "0.78)"),
        ("color: rgba(244, 246, 250, 0.65)", "250, 0.85)", "0.65)"),
        ("color: rgba(244,246,250,0.55)", "250,0.8)", "0.55)"),
        # decorative properties must be untouched
        ("border-color: rgba(244,246,250,0.55)", "0.55)", "0.8)"),
        ("outline-color: rgba(244,246,250,0.5)", "0.5)", "0.8)"),
        ("-webkit-text-fill-color: rgba(244,246,250,0.5)", "0.5)", "0.8)"),
        # already compliant stays put
        ("color: rgba(244,246,250,0.85)", "0.85)", "0.9)"),
        ("color: rgba(244,246,250,0.8)", "0.8)", "0.85)"),
        # the formula blocks are lifted to the content floor...
        (".prose-wh code { font-size: 0.92rem; color: #FDB94A; }", "#FED38D", "#FDB94A"),
        (".prose-wh pre { color: #FDB94A; line-height: 1.6; }", "#FED38D", "#FDB94A"),
        # ...while brand accent inside a link / summary / pill is CORRECTLY excused at Lc 60 and stays
        (".toc a:hover { color: #FDB94A; }", "#FDB94A", "#FED38D"),
        (".tool-cta a { color: #FDB94A; }", "#FDB94A", "#FED38D"),
        (".faq-item[open] summary { color: #FDB94A; }", "#FDB94A", "#FED38D"),
        # and a non-text use of the same hex is never touched
        (".author-card .avatar { background: linear-gradient(135deg, #F7A21B, #FDB94A); }",
         "#FDB94A", "#FED38D"),
        (".prose-wh code { border-color: #FDB94A; }", "#FDB94A", "#FED38D"),
        # the callout's bold lead-in is prose (Lc 75 floor) and is lifted...
        (".callout strong { color: #5FCCE8; }", "#A4E2F2", "#5FCCE8"),
        # ...while the SAME hex inside a link is a label (Lc 60) and correctly stays
        (".prose-wh a { color: #5FCCE8; }", "#5FCCE8", "#A4E2F2"),
        (".callout { border-left: 3px solid #5FCCE8; }", "#5FCCE8", "#A4E2F2"),
    ]
    bad = 0
    for src, want, forbid in cases:
        got, _, _ = remap(src)
        ok = want in got and forbid not in got
        if not ok:
            bad += 1
            print(f"  FAIL  {src!r} -> {got!r}  (want {want!r}, forbid {forbid!r})")
        else:
            print(f"  ok    {src!r} -> {got!r}")
    # idempotency: a second pass must change nothing
    once, n1, _ = remap("color: rgba(244,246,250,0.78)")
    twice, n2, _ = remap(once)
    if n2 != 0 or once != twice:
        bad += 1
        print(f"  FAIL  not idempotent: {once!r} -> {twice!r}")
    else:
        print("  ok    idempotent on a second pass")
    print(f"\n  {'PASS' if not bad else 'FAIL'} — {len(cases) + 1 - bad}/{len(cases) + 1} self-test cases")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    apply = "--apply" in argv
    files = targets()
    total, touched, skipped_all = 0, 0, []
    for path in files:
        src = path.read_text(encoding="utf-8", errors="replace")
        new, n, skipped = remap(src)
        skipped_all += skipped
        if n:
            total += n
            touched += 1
            if apply:
                fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
                os.replace(tmp, path)
    verb = "remapped" if apply else "would remap"
    print(f"  {verb} {total} text-colour declaration(s) across {touched}/{len(files)} learn page(s)")
    print("  ramp: 0.4/0.45/0.5/0.55/0.6 -> 0.8   0.65/0.7/0.75/0.78 -> 0.85   (wh-tw.css)")
    if skipped_all:
        uniq = sorted(set(skipped_all))
        print(f"  NOT in the ramp, left alone: {uniq} — extend RAMP deliberately, do not guess")
    if not apply:
        print("\n  dry run — re-run with --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
