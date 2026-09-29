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


def served_files() -> list[str]:
    sys.path.insert(0, str(ROOT / "tools"))
    from seed_expansion_wave4 import served_pages  # noqa: E402
    classes = served_pages()
    files = [p for cls in classes.values() for p in cls]
    files += [c for c in SHARED_CHROME if (ROOT / c).exists()]
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


def is_measurement_artifact(f: dict) -> bool:
    """One predicate, four consumers: a finding the page's own semantics or media already refute."""
    return is_print_artifact(f) or is_aria_level_heading(f)


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
    print("PASS design-detector-ratchet self-test - a 9px label is caught and counts as an increase, "
          "a print-only colour is not measured against the screen, and an ARIA-declared heading level "
          "is honoured while a bare one still fails")
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
    now = counts(detect(files))
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
