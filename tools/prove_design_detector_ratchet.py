#!/usr/bin/env python3
"""prove_design_detector_ratchet.py - the platform-wide anti-slop ratchet (2026-09-15).

Ian: "your own designing skills are all slop, AI Sloppiness so to speak." The slop is measurable: Impeccable's
mechanical detector (`impeccable detect --json`) found 305 warnings on five shell files alone - undersized text,
low contrast, tiny body text, clipped containers, all-caps body, nested cards, dark glows, gradient text, kickers.
This gate runs the detector over EVERY served page and the shared chrome, counts findings per (file, antipattern),
and compares with `design_detector_baseline.json` (repo root): any count that ROSE fails the gate. A fix lowers the
baseline (`--rebase` writes the new, lower counts; it refuses to write a higher one). So the number can only fall.

  python tools/prove_design_detector_ratchet.py --check      # the gate: fail on any (file, antipattern) increase
  python tools/prove_design_detector_ratchet.py --rebase     # after fixes: lower the baseline to today's counts
  python tools/prove_design_detector_ratchet.py --report     # the top antipatterns and files, no verdict
  python tools/prove_design_detector_ratchet.py --self-test  # a 9px label in a temp file must be caught

The detector's own advisory findings are excluded (they never count as failures, by its contract); only primary
findings ratchet. The detector reads DESIGN.md and .impeccable/ config when present - the same context a design
walk uses - so the gate and the walks see the same findings.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "design_detector_baseline.json"
SHARED_CHROME = ["utils.js", "nav-hub.js", "wayfinding.js", "offline-banner.js", "wh-consent.js", "learn-link.js",
                 "wh-i18n-lite.js"]
DETECTOR = Path(os.environ.get("IMPECCABLE_HOME", str(Path.home() / ".claude" / "skills" / "impeccable"))) / "scripts" / (
    "impeccable.cmd" if os.name == "nt" else "impeccable")


# ★THE CHROME IS WHAT THE CODE DOES, NOT A LIST (BRH-K+, 2026-10-15). SHARED_CHROME was written by hand and held 7
# files; 16 root scripts create or inject their own styles, so 11 were never read - voice-handler.js's forever-pulsing
# recording dot was found only by a live probe, and the 11 held 35 findings. Every root script that builds a <style>,
# assigns a style sheet's text, or inserts a rule is chrome, and is scanned; SHARED_CHROME stays as the named floor.
_INJECTS_STYLE = re.compile(r"""createElement\(\s*['"]style['"]\)|<style[\s>]|\.textContent\s*=\s*(?:STYLE|CSS|css|styles)\b|insertRule\(""")


def style_injecting_scripts(root: Path = ROOT) -> list[str]:
    out = []
    for p in sorted(root.glob("*.js")):
        try:
            if _INJECTS_STYLE.search(p.read_text(encoding="utf-8", errors="replace")):
                out.append(p.name)
        except OSError:
            pass
    return out


def served_files() -> list[str]:
    sys.path.insert(0, str(ROOT / "tools"))
    from seed_expansion_wave4 import served_pages  # noqa: E402
    classes = served_pages()
    files = [p for cls in classes.values() for p in cls]
    # ★THE FOUNDER SURFACES ARE SERVED TOO (CI4, 2026-10-15): the served roster is the production + public set, so the
    # five founder pages the SL program walks (founder-console, marketplace-admin, the two observability dashboards,
    # design-system) were never scanned - a page the ratchet does not read is a page whose count can rise unseen.
    from sublayer_inventory import page_classes  # noqa: E402
    files += [p for p in page_classes().get("founder", []) if p not in files and (ROOT / p).exists()]
    chrome = [c for c in SHARED_CHROME if (ROOT / c).exists()]
    files += chrome + [c for c in style_injecting_scripts() if c not in chrome]
    return files


def detect(files: list[str], cwd: Path = ROOT) -> list[dict]:
    """Run the detector once over all files; JSON on stdout, human text on stderr (the detector's contract)."""
    if not DETECTOR.exists():
        raise RuntimeError(f"detector not installed at {DETECTOR} (npx impeccable install --providers=claude --scope=global)")
    out: list[dict] = []
    # the Windows command line has a length ceiling; batch the argument list
    for i in range(0, len(files), 40):
        batch = files[i:i + 40]
        r = subprocess.run([str(DETECTOR), "detect", "--json", "--no-advisory", *batch], cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        text = (r.stdout or "").strip()
        if not text:
            if r.returncode == 1:
                raise RuntimeError(f"a target could not be scanned: {(r.stderr or '')[-300:]}")
            continue
        try:
            out.extend(json.loads(text))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"detector output was not JSON ({e}): {text[:200]}")
    return out


def counts(findings: list[dict]) -> dict[str, int]:
    c: Counter = Counter()
    for f in findings:
        if f.get("severity") == "advisory":
            continue
        if is_measurement_artifact(f):
            continue          # measured on paper's colour against the screen's background
        rel = os.path.relpath(f.get("file") or "?", ROOT).replace("\\", "/")
        c[f"{rel} :: {f.get('antipattern')}"] += 1
    return dict(sorted(c.items()))


def load_baseline() -> dict[str, int] | None:
    if not BASELINE.exists():
        return None
    return json.loads(BASELINE.read_text(encoding="utf-8")).get("counts") or {}


def write_baseline(c: dict[str, int], note: str) -> None:
    import datetime as _dt
    doc = {"_doc": ("Per-(file :: antipattern) primary-finding counts from `impeccable detect --json` over every served "
                    "page + the shared chrome. tools/prove_design_detector_ratchet.py --check fails on any increase; "
                    "--rebase lowers it after fixes. Regenerated, never hand-edited."),
           "generated": _dt.datetime.now().isoformat(timespec="seconds"), "note": note,
           "total": sum(c.values()), "counts": c}
    tmp = BASELINE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, BASELINE)


def compare(now: dict[str, int], base: dict[str, int]) -> tuple[list[str], list[str]]:
    rose = [f"{k}: {base.get(k, 0)} -> {v}" for k, v in now.items() if v > base.get(k, 0)]
    fell = [f"{k}: {base.get(k, 0)} -> {now.get(k, 0)}" for k in base if now.get(k, 0) < base[k]]
    return rose, fell


def report(c: dict[str, int]) -> str:
    by_ap: Counter = Counter()
    by_file: Counter = Counter()
    for k, v in c.items():
        f, ap = k.split(" :: ", 1)
        by_ap[ap] += v
        by_file[f] += v
    lines = [f"  total primary findings: {sum(c.values())} across {len(by_file)} files",
             "  by antipattern: " + " · ".join(f"{a} {n}" for a, n in by_ap.most_common(14)),
             "  worst files:    " + " · ".join(f"{f} {n}" for f, n in by_file.most_common(10))]
    return "\n".join(lines)


# ── print-only colours ────────────────────────────────────────────────────────────────────────
# A STATIC DETECTOR CANNOT SEE A MEDIA CONTEXT. `@media print { body * { color:#111 } }` paints every
# element black for PAPER, against a `background:#fff` set in the same block - and the detector
# measures that colour against the SCREEN background, reporting 1.1:1 on text that is 17.9:1 where it
# actually renders. logbook.html alone carried 92 such findings.
_PRINT_COLOR_CACHE: dict = {}


def _norm_hex(h: str) -> str:
    h = h.lower().lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    return "#" + h[:6]


def _media_print_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of every `@media print { … }` body, matched by counting braces."""
    spans, i = [], 0
    while True:
        i = text.find("@media print", i)
        if i < 0:
            return spans
        b = text.find("{", i)
        if b < 0:
            return spans
        depth, j = 0, b
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        spans.append((b, j))
        i = j + 1


def print_only_colors(path: str) -> set:
    """Hex colours this file uses INSIDE `@media print` and nowhere outside it.

    A colour used on screen too is NOT returned: the finding may be real, and suppressing a whole
    class because part of it is an artifact is the over-correction this wave already learned to
    refuse. The mechanism is checkable per file, so it is checked per file.
    """
    if path in _PRINT_COLOR_CACHE:
        return _PRINT_COLOR_CACHE[path]
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        _PRINT_COLOR_CACHE[path] = set()
        return _PRINT_COLOR_CACHE[path]
    spans = _media_print_spans(text)
    inside, outside, last = set(), set(), 0
    hexes = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b")
    for s, e in spans:
        outside |= {_norm_hex(m.group()) for m in hexes.finditer(text, last, s)}
        inside |= {_norm_hex(m.group()) for m in hexes.finditer(text, s, e)}
        last = e
    outside |= {_norm_hex(m.group()) for m in hexes.finditer(text, last)}
    _PRINT_COLOR_CACHE[path] = inside - outside
    return _PRINT_COLOR_CACHE[path]


_FG_RE = re.compile(r"text\s+(#[0-9a-fA-F]{3,6})\s+on\s+(#[0-9a-fA-F]{3,6})")


def is_print_artifact(f: dict) -> bool:
    """A low-contrast finding whose FOREGROUND exists only inside this file's @media print block."""
    if f.get("antipattern") != "low-contrast":
        return False
    m = _FG_RE.search(str(f.get("snippet") or ""))
    if not m:
        return False
    return _norm_hex(m.group(1)) in print_only_colors(f.get("file") or "")


# "<h2> "Voice, Filipino, and Taglish" followed by <h4> "Ask Hezekiah or Zaniah on any p"
# The quoted texts are truncated by the detector, so they are matched as prefixes, never whole.
_SKIP_RE = re.compile(r'<h([1-6])>\s*"(.*?)"\s+followed by\s+<h([1-6])>\s*"(.*?)(?:"|$)', re.S)
_HEADING_RE = re.compile(r"<h([1-6])\b([^>]*)>(.*?)</h\1\s*>", re.S | re.I)
_ARIA_LEVEL = re.compile(r"""aria-level\s*=\s*["']?\s*([1-6])""", re.I)
_HEADINGS_CACHE: dict[str, list[tuple[int, int, str]]] = {}


def _headings(path: str) -> list[tuple[int, int, str]]:
    """(tag level, EFFECTIVE level, text) for every heading in the file, in document order.

    The effective level is what assistive technology and axe compute: `aria-level` when present,
    otherwise the tag. `<h4 aria-level="2">` is announced as a level-2 heading by every screen
    reader, which is exactly why this codebase uses it - the styling is keyed to h4 and the outline
    is declared in ARIA (tools/fix_learn_heading_order.py, and the platform's own heading oracle
    tools/validate_content_page_hygiene.py, which reads the same way).
    """
    if path in _HEADINGS_CACHE:
        return _HEADINGS_CACHE[path]
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        _HEADINGS_CACHE[path] = []
        return []
    out = []
    for m in _HEADING_RE.finditer(src):
        tag = int(m.group(1))
        a = _ARIA_LEVEL.search(m.group(2))
        text = html.unescape(re.sub(r"<[^>]+>", " ", m.group(3)))
        out.append((tag, int(a.group(1)) if a else tag, " ".join(text.split())))
    _HEADINGS_CACHE[path] = out
    return out


def _starts(text: str, prefix: str) -> bool:
    p = " ".join(html.unescape(prefix).split())[:28]
    return bool(p) and " ".join(text.split()).startswith(p)


def is_aria_level_heading(f: dict) -> bool:
    """A skipped-heading finding on a pair whose EFFECTIVE (ARIA) levels do not skip.

    The detector reads tag names. This project deliberately styles some headings as <h4> and declares
    the real outline with `aria-level` - so the detector reports "h1 followed by h4" on markup that
    every screen reader announces as level 1 followed by level 2. All 69 of the learn corpus's
    skipped-heading findings are that shape, while the aria-aware platform gate passes 57/57
    ([[feedback_an_oracles_vocabulary_is_part_of_the_oracle]] - a check that rejects an ARIA semantic
    is catching the wrong thing).

    Refuted PER FINDING, not per antipattern: the two headings the snippet names are located in the
    file and their effective levels compared. A bare <h4> after an <h2> still has effective levels
    2 -> 4 and is still a finding. Anything unparseable or unlocatable keeps the finding.
    """
    if f.get("antipattern") != "skipped-heading":
        return False
    m = _SKIP_RE.search(str(f.get("snippet") or ""))
    if not m:
        return False
    tag_a, text_a, tag_b, text_b = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
    hs = _headings(f.get("file") or "")
    for i, (tag, eff, text) in enumerate(hs):
        if i == 0 or tag != tag_b or not _starts(text, text_b):
            continue
        p_tag, p_eff, p_text = hs[i - 1]
        if p_tag != tag_a or not _starts(p_text, text_a):
            continue
        return eff <= p_eff + 1
    return False


# ── the root's axis guard ──────────────────────────────────────────────────────────────────────────
# tokens.css R2: `html { overflow-x: clip; }` (html AND body until 2026-10-23, when body's own clip box turned out to stop
# Chrome's scroll anchoring - SL.19) - deliberately CLIP, not hidden: it stops off-screen decorations
# (the feedback panel parked at translateX(100%)) from widening the page, without making either element a scroll
# container, so position:sticky keeps working. The detector reports it as "html clips a positioned child" whenever a
# page has a position:fixed nav - but a fixed box's containing block is the VIEWPORT, so an ancestor's overflow never
# clips it. Exempt ONLY when the file links tokens.css and nothing on that element overrides the clip: a body that
# carries overflow-x-hidden (index.html did - Tailwind's class beat the clip and made body a scroll container) still
# counts, because then the finding is true.
_ROOT_CLIP = re.compile(r"^(html|body)(\.[^\s]+)?\s+clips a positioned child")


def is_root_axis_clip(f: dict) -> bool:
    if f.get("antipattern") != "clipped-overflow-container":
        return False
    snip = f.get("snippet") or ""
    m = _ROOT_CLIP.match(snip)
    if not m or "overflow" in (m.group(2) or ""):
        return False
    try:
        src = Path(f.get("file") or "").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if not re.search(r"""<link[^>]+href=["'](?:\./)?tokens\.css["']""", src):
        return False
    if m.group(1) == "html":
        # the ROOT's overflow is propagated to the viewport: hidden or clip, it never makes a scroll container and
        # never clips a fixed box - it is the axis guard either way (index.html also sets it inline, pre-tokens)
        return True
    # BODY is different: hidden on body (with html not visible) makes body a scroll container and breaks sticky -
    # so a body that overrides the clip in its own tag still counts
    tag = re.search(r"<body\b[^>]*>", src)
    return not (tag and "overflow" in tag.group(0))


# ── the modal scrim read as a card ─────────────────────────────────────────────────────────────────
# The platform's modal contract (validate_modal_a11y.py, critique C7; utils.js whModalA11y and whConfirm) puts
# role="dialog" + aria-modal on the FULL-BLEED OVERLAY, whose background is the scrim. The detector treats a
# role="dialog" element with a background as a card, so every styled panel inside a scrim reads "card inside card"
# (measured 2026-10-15 on fixtures: role + background -> flagged; background without the role, or the role without a
# background -> not). The scrim is not a card. This is DIFFERENTIAL, not a count of dialogs: the detector re-runs on a
# copy of the page whose full-bleed dialog overlays carry no background, and only the nested-cards that DISAPPEAR are
# the scrim's. A dialog that IS the panel (not full-bleed) is never touched, so a card nested in it still counts.
_DIV_OPEN_RX = re.compile(r"<div\b[^>]*>", re.I)


def _is_fullbleed_dialog(tag: str) -> bool:
    if not re.search(r"""role\s*=\s*["']dialog["']""", tag, re.I):
        return False
    cls = (re.search(r"""class\s*=\s*["']([^"']*)["']""", tag) or [None, ""])[1]
    sty = (re.search(r"""style\s*=\s*["']([^"']*)["']""", tag) or [None, ""])[1].replace(" ", "")
    return ("fixed" in cls.split() and "inset-0" in cls.split()) or ("position:fixed" in sty and "inset:0" in sty)


def _strip_scrim_backgrounds(src: str) -> str:
    def fix(m: re.Match) -> str:
        tag = m.group(0)
        if not _is_fullbleed_dialog(tag):
            return tag
        return re.sub(r"""(style\s*=\s*["'])([^"']*)""",
                      lambda s: s.group(1) + re.sub(r"(?:-webkit-)?(?:backdrop-filter|background(?:-color)?)\s*:[^;\"']*;?", "", s.group(2)),
                      tag, count=1)
    return _DIV_OPEN_RX.sub(fix, src)


def scrim_artifacts(now: dict[str, int], root: Path = ROOT) -> dict[str, int]:
    """Per 'file :: nested-cards' key, how many of its findings are the modal scrim (see above)."""
    keys = [k for k, v in now.items() if k.endswith(" :: nested-cards") and v]
    variants: dict[str, Path] = {}
    try:
        for k in keys:
            rel = k.split(" :: ", 1)[0]
            src_path = root / rel
            try:
                src = src_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = _strip_scrim_backgrounds(src)
            if stripped == src:
                continue
            v = src_path.with_name("zz_scrimtest_" + src_path.name)     # beside it: its stylesheets resolve
            v.write_text(stripped, encoding="utf-8")
            variants[k] = v
        if not variants:
            return {}
        found = detect([str(v) for v in variants.values()], cwd=root)
        per = Counter(Path(f.get("file") or "").name for f in found if f.get("antipattern") == "nested-cards")
        return {k: max(0, now[k] - per.get(v.name, 0)) for k, v in variants.items()}
    finally:
        for v in variants.values():
            try:
                v.unlink()
            except OSError:
                pass


def without_scrim_artifacts(now: dict[str, int], root: Path = ROOT) -> dict[str, int]:
    art = scrim_artifacts(now, root)
    out = {k: v - art.get(k, 0) for k, v in now.items()}
    return {k: v for k, v in out.items() if v > 0}


# ★A DOT THAT PULSES FOREVER IS USUALLY BUILT BY A SCRIPT, WHERE THE DETECTOR CANNOT SEE IT (BRH-K+, 2026-10-15). The
# K walk found eight on analytics (4), engineering-design (3) and offline-fallback (1) by probing the live render; the
# detector had read 0, because each dot was a style attribute inside a JS template string or a rule the page only
# paints later. And after K+ the companion's own typing indicator - three 6px dots pulsing in a rule companion-launcher
# injects - still read 0. So the ratchet reads the DECLARATION too: one style attribute or one rule block that makes
# a round element of 12px or less animate forever. A spinner is not a dot: a rotation shows work that ends, so any
# block whose animation turns (spin / rotate) is left out, as is a larger element whose infinite motion is a signal.
_DECL_BLOCK = re.compile(r"""style\s*=\s*(["'])(.*?)\1|\{([^{}]*)\}""", re.S)
_DOT_SIZE = re.compile(r"(?<![-\w])(?:width|height)\s*:\s*(\d+(?:\.\d+)?)px", re.I)
_ROUND = re.compile(r"border-radius\s*:\s*(?:50%|100%|9999px|999px)", re.I)
_FOREVER = re.compile(r"animation(?:-iteration-count)?\s*:[^;\"'}]*\binfinite\b", re.I)
_TURNS = re.compile(r"animation(?:-name)?\s*:[^;\"'}]*(?:spin|rotat)", re.I)
DECLARED_DOT = "pulsing-dot-declared"


def declared_pulsing_dots(files: list[str], root: Path = ROOT) -> dict[str, int]:
    c: Counter = Counter()
    for f in files:
        p = Path(f) if Path(f).is_absolute() else root / f
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _DECL_BLOCK.finditer(text):
            body = m.group(2) if m.group(2) is not None else m.group(3)
            if not body or not _FOREVER.search(body) or not _ROUND.search(body) or _TURNS.search(body):
                continue
            sizes = [float(x) for x in _DOT_SIZE.findall(body)]
            if sizes and max(sizes) <= 12:
                c[f"{os.path.relpath(p, root).replace(chr(92), '/')} :: {DECLARED_DOT}"] += 1
    return dict(c)


def with_declared_dots(now: dict[str, int], files: list[str], root: Path = ROOT) -> dict[str, int]:
    out = dict(now)
    for k, v in declared_pulsing_dots(files, root).items():
        out[k] = out.get(k, 0) + v
    return dict(sorted(out.items()))


def is_measurement_artifact(f: dict) -> bool:
    """One predicate, four consumers: a finding the page's own semantics or media already refute."""
    return is_print_artifact(f) or is_aria_level_heading(f) or is_root_axis_clip(f)


def self_test() -> int:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "slop.html"
        p.write_text("<!doctype html><html><body><p style='font-size:9px'>XP this week</p>"
                     "<button style='font-size:9px'>Save</button></body></html>", encoding="utf-8")
        found = detect([str(p)], cwd=Path(d))
        aps = {f.get("antipattern") for f in found}
        if not any(a in aps for a in ("tiny-text", "undersized-ui-text")):
            print(f"FAIL self-test: a 9px label was not caught ({sorted(aps)})")
            return 1
        now = counts(found)
        rose, _ = compare(now, {})
        if not rose:
            print("FAIL self-test: a finding against an empty baseline did not register as an increase")
            return 1
    # A colour that exists ONLY inside @media print is an artifact and must not ratchet; the same
    # colour used on screen as well must still count, or the exemption becomes a blanket amnesty.
    with tempfile.TemporaryDirectory() as d:
        only = Path(d) / "printonly.html"
        only.write_text("<style>body{background:#161f31;color:#eee}"
                        "@media print{body{background:#fff}body *{color:#111}}</style><p>x</p>",
                        encoding="utf-8")
        if _norm_hex("#111") not in print_only_colors(str(only)):
            print("FAIL self-test: a colour used only inside @media print was not recognised")
            return 1
        both = Path(d) / "both.html"
        both.write_text("<style>body{background:#161f31;color:#111}"
                        "@media print{body *{color:#111}}</style><p>x</p>", encoding="utf-8")
        if print_only_colors(str(both)):
            print("FAIL self-test: a colour used ON SCREEN too must NOT be exempt")
            return 1
        art = {"antipattern": "low-contrast", "file": str(only),
               "snippet": "1.1:1 (need 3:1) \u00b7 text #111111 on #161f31"}
        if not is_print_artifact(art):
            print("FAIL self-test: a print-only foreground was not treated as an artifact")
            return 1
        real = dict(art, file=str(both))
        if is_print_artifact(real):
            print("FAIL self-test: a screen-used colour was wrongly treated as an artifact")
            return 1
        other = dict(art, antipattern="tiny-text")
        if is_print_artifact(other):
            print("FAIL self-test: only low-contrast may be exempted")
            return 1
    # A heading whose ARIA level keeps the outline continuous is not a skip; a BARE one still is.
    # The detector is run for real here rather than hand-fed a snippet, so the snippet grammar the
    # predicate parses is the grammar the detector actually emits.
    with tempfile.TemporaryDirectory() as d:
        # a FULL document: the detector reports no heading order on a fragment
        doc = ("<!doctype html><html lang=\"en\"><head><title>T</title></head><body><main>"
               "<h1>The guide to everything</h1><h4{attrs}>What is in this guide</h4>"
               "<p>Body prose long enough for the page to read as a page.</p>"
               "<h2>A section</h2><p>More prose, so the outline has somewhere to go.</p>"
               "</main></body></html>")
        declared = Path(d) / "declared.html"
        declared.write_text(doc.format(attrs=" aria-level=\"2\""), encoding="utf-8")
        bare = Path(d) / "bare.html"
        bare.write_text(doc.format(attrs=""), encoding="utf-8")
        found = detect([str(declared), str(bare)], cwd=Path(d))
        skips = [f for f in found if f.get("antipattern") == "skipped-heading"]
        if len(skips) != 2:
            print(f"FAIL self-test: expected the detector to flag both pages, got {len(skips)} "
                  "skipped-heading finding(s) - the snippet grammar may have changed")
            return 1
        by_file = {Path(f.get("file") or "").name: f for f in skips}
        if not is_aria_level_heading(by_file.get("declared.html", {})):
            print("FAIL self-test: an h4 carrying aria-level=\"2\" after an h1 was not recognised as "
                  "an outline the page declares in ARIA")
            return 1
        if is_aria_level_heading(by_file.get("bare.html", {})):
            print("FAIL self-test: a BARE h4 after an h1 is a real skip and must still count")
            return 1
    # The root's axis guard: tokens.css's clip on html/body is exempt; a body that overrides it with a hidden class,
    # a page that does not link tokens.css, and a CARD that clips its child all still count.
    with tempfile.TemporaryDirectory() as d:
        ok = Path(d) / "rootclip.html"
        ok.write_text('<link rel="stylesheet" href="tokens.css"><body class="text-white"><nav>x</nav></body>', encoding="utf-8")
        over = Path(d) / "rootover.html"
        over.write_text('<link rel="stylesheet" href="tokens.css"><body class="overflow-x-hidden"><nav>x</nav></body>', encoding="utf-8")
        bare = Path(d) / "roottokenless.html"
        bare.write_text('<body class="text-white"><nav>x</nav></body>', encoding="utf-8")
        ca = "clipped-overflow-container"
        if not is_root_axis_clip({"antipattern": ca, "file": str(ok), "snippet": "html clips a positioned child"}) or \
           not is_root_axis_clip({"antipattern": ca, "file": str(ok), "snippet": "body.text-white clips a positioned child"}):
            print("FAIL self-test: tokens.css's clip on html/body was not recognised as the root's axis guard")
            return 1
        if is_root_axis_clip({"antipattern": ca, "file": str(over), "snippet": "body.overflow-x-hidden clips a positioned child"}) or \
           is_root_axis_clip({"antipattern": ca, "file": str(bare), "snippet": "html clips a positioned child"}) or \
           is_root_axis_clip({"antipattern": ca, "file": str(ok), "snippet": "div.stage-card clips a positioned child"}):
            print("FAIL self-test: an overriding body, a page without tokens.css, or a card clipping its child was exempted")
            return 1
    # The modal scrim: a card inside a FULL-BLEED role="dialog" overlay is the scrim's artifact and is exempt; the same
    # card inside a dialog that IS the panel still counts. Built beside the real pages with inventory.html's own head,
    # because the detector reads the page's stylesheets to call something a card (a bare temp fixture never fires).
    head = (ROOT / "inventory.html").read_text(encoding="utf-8")
    head = head[:head.index("<body")]
    card = '<div class="card w-full max-w-lg p-7 relative"><span>Part Number</span></div></div>'
    scrim, panel = ROOT / "zz_selftest_scrim.html", ROOT / "zz_selftest_panel.html"
    try:
        scrim.write_text(head + '<body><div role="dialog" aria-modal="true" aria-label="Add part" class="fixed inset-0 z-50 '
                         'p-4" style="display:none; background:rgba(0,0,0,0.75);">' + card + "</body></html>", encoding="utf-8")
        panel.write_text(head + '<body><div role="dialog" aria-modal="true" aria-label="Add part" class="w-full max-w-lg p-4 '
                         'rounded-2xl" style="background:rgba(0,0,0,0.75);">' + card + "</body></html>", encoding="utf-8")
        raw = counts(detect([str(scrim), str(panel)]))
        net = without_scrim_artifacts(raw)
        k_s, k_p = "zz_selftest_scrim.html :: nested-cards", "zz_selftest_panel.html :: nested-cards"
        if raw.get(k_s, 0) < 1 or raw.get(k_p, 0) < 1:
            print(f"FAIL self-test: the detector no longer flags the scrim/panel fixtures ({raw}) - its nested-cards rule changed")
            return 1
        if net.get(k_s, 0) != 0:
            print("FAIL self-test: a card inside a full-bleed role=dialog scrim was not recognised as the scrim's artifact")
            return 1
        if net.get(k_p, 0) < 1:
            print("FAIL self-test: a card nested in a dialog that IS the panel was exempted - it must still count")
            return 1
    finally:
        for f in (scrim, panel):
            try:
                f.unlink()
            except OSError:
                pass
    # The declared pulsing dot: a 7px round dot in a JS-built style attribute and a 6px dot in an injected rule count;
    # a 10px spinner ring (it turns), a 56px trigger's infinite nudge and a dot that pulses a bounded number of times do not.
    with tempfile.TemporaryDirectory() as d:
        js = Path(d) / "dots.js"
        js.write_text(
            "el.innerHTML = `<div style=\"width:7px;height:7px;border-radius:50%;animation:dotPulse 1.4s ease-in-out infinite;\"></div>`;\n"
            "const css = `.typing span { width: 6px; height: 6px; border-radius: 50%; animation: wh-dot 1.2s infinite; }\n"
            ".ring { width: 10px; height: 10px; border-radius: 50%; border-top-color: #f7a21b; animation: spin 0.8s linear infinite; }\n"
            "#trigger.nudge { width: 56px; height: 56px; border-radius: 50%; animation: nudge 1.6s ease-in-out infinite; }\n"
            ".once { width: 8px; height: 8px; border-radius: 50%; animation: pop 0.4s ease-out 2; }`;\n", encoding="utf-8")
        got = declared_pulsing_dots([str(js)], root=Path(d)).get(f"dots.js :: {DECLARED_DOT}", 0)
        if got != 2:
            print(f"FAIL self-test: the declared-dot leg counted {got} in a fixture holding exactly 2 forever-pulsing dots "
                  "(beside a turning spinner, a 56px nudge and a bounded pulse, none of which is one)")
            return 1
        merged = with_declared_dots({"dots.js :: tiny-text": 1}, [str(js)], root=Path(d))
        if merged.get(f"dots.js :: {DECLARED_DOT}") != 2 or merged.get("dots.js :: tiny-text") != 1:
            print(f"FAIL self-test: the declared dots were not merged beside the detector's counts ({merged})")
            return 1
    print("PASS design-detector-ratchet self-test - a 9px label is caught and counts as an increase, "
          "a print-only colour is not measured against the screen, an ARIA-declared heading level "
          "is honoured while a bare one still fails, tokens.css's root clip is exempt while an override still counts, "
          "a modal scrim is not a card while a dialog panel's nested card still counts, and a dot a script declares "
          "pulsing forever is counted while a spinner, a large nudge and a bounded pulse are not")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rebase", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    # ★THE FLOOR IS RE-MEASURED ONLY WHEN THE INSTRUMENT CHANGED, AND IT SAYS WHY (2026-09-15). Recording DESIGN.md
    # gave the detector a rule it did not have when the first baseline was written (design-system-font: a page whose
    # face is not the system's), so 93 counts "rose" with no page touched. A rise that comes from the detector reading
    # more is not a regression, but it may not be waved through silently either: --reseed requires a --reason, writes
    # it into the baseline's note, and prints the before/after so the audit trail shows a re-measure, not a bypass.
    ap.add_argument("--reseed", action="store_true", help="re-measure the floor after the DETECTOR's inputs changed (needs --reason)")
    ap.add_argument("--reason", default="", help="why the floor is re-measured (stored in the baseline)")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    files = served_files()
    now = with_declared_dots(without_scrim_artifacts(counts(detect(files))), files)
    base = load_baseline()
    if a.reseed:
        if not a.reason.strip():
            print("REFUSED --reseed: say why the floor is re-measured (--reason '...')")
            return 1
        before = sum(base.values()) if base else 0
        write_baseline(now, f"reseeded: {a.reason.strip()} (was {before})")
        print(f"reseeded the floor: {before} -> {sum(now.values())} primary findings; reason recorded in the baseline")
        return 0
    if a.report:
        print(report(now))
        return 0
    if base is None:
        write_baseline(now, "first baseline - today's measured slop; the number can only fall from here")
        print(f"wrote the first baseline: {sum(now.values())} primary findings over {len(files)} files")
        print(report(now))
        return 0
    rose, fell = compare(now, base)
    if a.rebase:
        if rose:
            print(f"REFUSED --rebase: {len(rose)} count(s) rose; fix them first:")
            for r in rose[:20]:
                print("   ", r)
            return 1
        write_baseline(now, f"rebased: {len(fell)} count(s) fell")
        print(f"rebased: {sum(base.values())} -> {sum(now.values())} primary findings ({len(fell)} count(s) fell)")
        return 0
    if rose:
        print(f"FAIL design-detector-ratchet: {len(rose)} (file :: antipattern) count(s) ROSE against the baseline "
              f"({sum(base.values())} -> {sum(now.values())}):")
        for r in rose[:40]:
            print("   ", r)
        return 1
    print(f"PASS design-detector-ratchet: {sum(now.values())} primary findings, none rose against the baseline of "
          f"{sum(base.values())}" + (f" ({len(fell)} fell - run --rebase to lower the floor)" if fell else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
