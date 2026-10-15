#!/usr/bin/env python3
"""validate_handler_values_escaped.py - SL S4 (2026-10-15): no value is interpolated into an inline event handler
(onclick="...", onkeydown="...") without escJsAttr.

FOUND BY THE S4 POISON WALK. logbook drew every entry card with onclick="openModal('${e.id}')". logbook.id is a TEXT
column (its default is a uuid, but the client writes its own ids - 'pm-<time><random>' - and nothing constrains what an
id may contain), so any active member of a hive could store an entry whose id closes the attribute and adds a handler
of its own, run for every colleague who opens the logbook. The walk saw it happen: four handler runs, two payload
elements, on a page whose every TEXT field it had shown safely.

WHY escHtml IS NOT ENOUGH THERE. Inside an HTML attribute the browser decodes entities BEFORE the JavaScript runs:
escHtml turns ' into &#39;, the attribute hands the handler a plain ', and the string it was meant to stay inside is
closed. escJsAttr (utils.js) escapes for the JS string first and the attribute second - the one escaper for a value
inside a JS string inside an HTML attribute. A number passes through it unchanged, so the rule has no exceptions to
remember: every ${...} in an inline handler is escJsAttr(...), or JSON.stringify(...) (already a JS literal).

  python tools/validate_handler_values_escaped.py              # the gate: 0 raw interpolations in inline handlers
  python tools/validate_handler_values_escaped.py --self-test
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTR = re.compile(r"""\son[a-z]+\s*=\s*"([^"]*\$\{[^"]*)\"""")
INTERP = re.compile(r"\$\{([^}]+)\}")
SAFE = re.compile(r"^\s*(escJsAttr|JSON\.stringify)\s*\(")


def raw_sites(text: str, name: str) -> list[str]:
    out = []
    for m in ATTR.finditer(text):
        for e in INTERP.findall(m.group(1)):
            if not SAFE.match(e):
                out.append(f"{name}:{text[: m.start()].count(chr(10)) + 1}: ${{{e.strip()}}} in an inline handler")
    return out


def files() -> list[Path]:
    pats = ("*.html", "*.js", "tools/*/index.html", "learn/*/index.html", "learn/index.html")
    return sorted({Path(f) for p in pats for f in glob.glob(str(ROOT / p))})


def self_test() -> int:
    bad = 'el.innerHTML = `<div onclick="openModal(\'${e.id}\')">x</div>`;'
    html = 'el.innerHTML = `<div onclick="openModal(\'${e(e.id)}\')">x</div>`;'
    good = 'el.innerHTML = `<div onclick="openModal(\'${escJsAttr(e.id)}\')" onkeydown="go(${JSON.stringify(n)})">x</div>`;'
    outside = 'el.innerHTML = `<div data-id="${e(e.id)}">${e(e.name)}</div>`;'
    ok = (len(raw_sites(bad, "bad")) == 1 and len(raw_sites(html, "html")) == 1
          and not raw_sites(good, "good") and not raw_sites(outside, "outside"))
    print(("PASS" if ok else "FAIL") + " handler-values-escaped self-test - a raw id and an escHtml'd id in a handler are "
          "caught; escJsAttr, JSON.stringify and values outside handlers are not")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    hits = []
    for f in files():
        hits += raw_sites(f.read_text(encoding="utf-8", errors="replace"), f.relative_to(ROOT).as_posix())
    if hits:
        print(f"FAIL handler-values-escaped - {len(hits)} value(s) interpolated into an inline handler without escJsAttr:")
        for h in hits[:25]:
            print("    " + h)
        return 1
    print(f"PASS handler-values-escaped - every value in an inline event handler across {len(files())} files goes through "
          f"escJsAttr (or is a JSON literal)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
