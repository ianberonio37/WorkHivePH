#!/usr/bin/env python3
"""derive_page_matrix.py — v3 bug-hunt matrix skeleton generator (PER_PAGE_BUGHUNT_ROADMAP §7).

Reads a page's substrate card (substrate/page/<page>.md) and emits its 12-dimension x 6-layer grid,
resolving every conditional (△) cell to LIVE or N/A(reason) from the page's real footprint — so the
matrix is deterministic, not hand-guessed.

Usage:  python tools/derive_page_matrix.py hive            # one page, human table
        python tools/derive_page_matrix.py --all --json    # every page, machine skeleton
"""
import re, sys, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = ROOT / "substrate" / "page"

DIMS = ["P1 smoke", "P2 console", "P3 crud", "P4 inputs", "P5 role", "P6 concur",
        "P7 locks", "P8 visual", "P9 a11y", "P10 perf", "P11 i18n", "P12 error"]
LAYERS = ["L1 ui", "L2 js", "L3 rls", "L4 view/rpc", "L5 trig", "L6 edge"]

# applicability grid: '#'=always-live, '?'=conditional on footprint, '-'=N/A(fixed reason).
# rows = DIMS order, cols = LAYERS order.
GRID = {
    "P1 smoke":   "###?-?",  "P2 console": "###?-?",  "P3 crud":  "?###??",
    "P4 inputs":  "?##???",  "P5 role":    "??###?",  "P6 concur":"-####?",
    "P7 locks":   "###--?",  "P8 visual":  "#?----",  "P9 a11y":  "#?----",
    "P10 perf":   "#####?",  "P11 i18n":   "##---?",  "P12 error":"####??",
}
# fixed N/A reasons per layer for the '-' cells
NA_FIXED = {
    "L3 rls": "no API surface for this dimension", "L4 view/rpc": "no view/rpc surface",
    "L5 trig": "no write→trigger on this dimension", "L6 edge": "no edge surface",
    "L1 ui": "not a render concern", "L2 js": "not a client-logic concern",
}

# placeholder tokens a substrate card uses for an EMPTY footprint section — must NOT count as a real item.
_PLACEHOLDER = re.compile(r"^\(?\s*(none|n/?a|nil|-)\b", re.I)

def _clean(items: list[str]) -> list[str]:
    return [x for x in items if x and not _PLACEHOLDER.match(x)]

def footprint(md: str) -> dict:
    def grab(label):
        m = re.search(rf"\*\*{re.escape(label)}\*\*[^:]*:\s*(.+)", md)
        if not m: return []
        return _clean([x.strip(" `") for x in re.split(r"[,·]", m.group(1)) if x.strip(" `")])
    fns = re.search(r"\*\*Functions\*\*:\s*([\s\S]+?)(?:\n\n|\nLinks:|$)", md)
    return {
        "db_writes":  grab("DB writes"),
        "rpcs":       grab("RPC calls"),
        "views":      grab("Truth views read"),
        "edge":       grab("Edge invokes"),
        "functions":  _clean([f.strip(" `") for f in re.split(r"[,·]", fns.group(1))])[:200] if fns else [],
    }

def layer_present(layer: str, fp: dict) -> bool:
    return {
        "L1 ui": True, "L2 js": bool(fp["functions"]),
        "L3 rls": bool(fp["db_writes"]),
        "L4 view/rpc": bool(fp["rpcs"] or fp["views"]),
        "L5 trig": bool(fp["db_writes"]),            # writes MAY fire triggers → hunt to confirm
        "L6 edge": bool(fp["edge"]),
    }[layer]

def build(page: str):
    f = PAGES / f"{page}.md"
    if not f.exists():
        return None, f"no substrate card: {f.relative_to(ROOT)}"
    md = f.read_text(encoding="utf-8", errors="replace")
    fp = footprint(md)
    present = {L: layer_present(L, fp) for L in LAYERS}
    cells, live = {}, 0
    for d in DIMS:
        row = GRID[d]
        for i, L in enumerate(LAYERS):
            mark = row[i]
            if mark == "#":
                cells[f"{d} × {L}"] = "LIVE"; live += 1
            elif mark == "?":
                if present[L]:
                    cells[f"{d} × {L}"] = "LIVE"; live += 1
                else:
                    cells[f"{d} × {L}"] = f"N/A({NA_FIXED.get(L,'no footprint')})"
            else:
                cells[f"{d} × {L}"] = f"N/A({NA_FIXED.get(L,'n/a')})"
    return {"page": page, "footprint": fp, "live_cells": live, "total": len(DIMS)*len(LAYERS), "cells": cells}, None

def print_table(m):
    print(f"\n=== {m['page']}  —  {m['live_cells']} LIVE cells / {m['total']} ===")
    fp = m["footprint"]
    print(f"  footprint: L2 {len(fp['functions'])} fns · L3 {len(fp['db_writes'])} write-tables · "
          f"L4 {len(fp['rpcs'])} rpc + {len(fp['views'])} views · L6 {len(fp['edge'])} edge")
    hdr = "  Dim \\ Layer   " + "".join(f"{L.split()[0]:>6}" for L in LAYERS)
    print(hdr)
    for d in DIMS:
        row = "  " + f"{d:<13}"
        for L in LAYERS:
            v = m["cells"][f"{d} × {L}"]
            row += f"{'LIVE' if v=='LIVE' else '—':>6}"
        print(row)

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if "--all" in sys.argv:
        out = {}
        for f in sorted(PAGES.glob("*.md")):
            m, err = build(f.stem)
            if m: out[f.stem] = {"live_cells": m["live_cells"], "cells": m["cells"]}
        if as_json: print(json.dumps(out, indent=1))
        else:
            for p, v in out.items(): print(f"{p:<28} {v['live_cells']:>3} live cells")
            print(f"\n{len(out)} pages · {sum(v['live_cells'] for v in out.values())} total live cells to hunt")
    else:
        page = args[0] if args else "hive"
        m, err = build(page)
        if err: print("ERROR:", err); sys.exit(1)
        print(json.dumps(m, indent=1)) if as_json else print_table(m)
