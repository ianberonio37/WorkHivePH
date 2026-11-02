#!/usr/bin/env python3
"""repatch_calc_page.py - carry a corrected worked example onto a SHIPPED calculator door page, in place (2026-11-02).

A door page (tools/<slug>/index.html) is built once by tools/build_calc_pages.py and then hand-fixed many times (em
dashes, og tags, font-display, padding). Re-running the generator over a shipped page reverts those fixes (memory: a
generator over shipped pages reverts their fixes), so a change to a page's example_inputs is carried by hand.

This does that hand edit mechanically: it runs the page's module on the example as committed (HEAD's CALC_DATA) and as
it stands now, formats both headline sets exactly as the generator does (_fmt), and swaps ONLY those strings - the
lede's "Label = value unit" and the result table's <td>value unit</td> beside its label. Anything it cannot find is
reported, never guessed; the page is left untouched unless every headline was found.

    python tools/repatch_calc_page.py <slug> [<slug> ...]      # then: python tools/refresh_public_page.py tools/<slug> --stamp
"""
from __future__ import annotations

import importlib
import io
import re
import subprocess
import sys
import types
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python-api"))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


def head_calc_data() -> dict:
    src = subprocess.run(["git", "show", "HEAD:tools/build_calc_pages.py"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8").stdout
    mod = types.ModuleType("bcp_head")
    mod.__file__ = str(ROOT / "tools" / "build_calc_pages.py")
    exec(compile(src, "bcp_head", "exec"), mod.__dict__)   # noqa: S102 - our own committed source
    return mod.CALC_DATA


def rows(bcp, spec: dict) -> list[tuple[str, str, str]]:
    m = importlib.import_module(f"calcs.{spec['module']}")
    r = m.calculate(dict(spec["example_inputs"]))
    return [(label, bcp._fmt(bcp._resolve(r, key)), unit) for label, key, unit in spec["headline"]]


def patch(slug: str, bcp, head: dict) -> bool:
    page = ROOT / "tools" / slug / "index.html"
    old_rows, new_rows = rows(bcp, head[slug]), rows(bcp, bcp.CALC_DATA[slug])
    html = page.read_text(encoding="utf-8")
    out, missing = html, []
    for (label, ov, unit), (_, nv, _) in zip(old_rows, new_rows):
        u = f" {unit}" if unit else ""
        lede_old, lede_new = f"{label} = {ov}{u}", f"{label} = {nv}{u}"
        cell = re.compile(r"(<td>" + re.escape(label) + r"</td>\s*<td>)" + re.escape(f"{ov}{u}") + r"(</td>)")
        if lede_old not in out or not cell.search(out):
            missing.append(f"{label} = {ov}{u}")
            continue
        out = out.replace(lede_old, lede_new)
        out = cell.sub(lambda m: m.group(1) + f"{nv}{u}" + m.group(2), out)
    changed = [(o, n) for o, n in zip(old_rows, new_rows) if o[1] != n[1]]
    if missing:
        print(f"  HELD {slug}: not found on the page as the generator writes it - {'; '.join(missing)}")
        return False
    page.write_text(out, encoding="utf-8", newline="")
    print(f"  {slug}: " + (", ".join(f"{o[0]} {o[1]} -> {n[1]}" for o, n in changed) if changed else "headline figures unchanged"))
    return True


def main() -> int:
    warnings.filterwarnings("ignore")
    import logging
    logging.disable(logging.WARNING)
    import build_calc_pages as bcp
    head = head_calc_data()
    ok = all([patch(s, bcp, head) for s in sys.argv[1:]])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
