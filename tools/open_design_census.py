#!/usr/bin/env python3
"""open_design_census.py - how many trajectory rows the open-source design lens owes (2026-11-03).

Ian: "we have to extend the number of our trajectories roadmap through penpot, you have to plan the appropriate and
necessary numbers to add." The count is derived, never typed (the BRH/OWN precedent): population x what each unit
owes - rows the registry already holds.

  OD-P  a page's comp lives in the WorkHive Penpot file, drawn from the token library, at 390 and 1280, and agrees
        with the live page (odiff). Unit: every served root/page file + one per GENERATED family (learn articles,
        calculator pages - their generator is the unit; a fix per page would be reverted by the next build).
  OD-D  a unit's own CSS takes its values from tokens.css, per drift class that is non-zero today:
        colour (exact + tint + off), type (raw font sizes + families), stacking (raw z-indexes).
        Units as OD-P, plus the hand-written shared stylesheets and ONE unit for the Tailwind build (wh-tw*.css are
        generated; their source is the Tailwind config).
  OD-S  the design system owns what the pages keep hard-coding: one row per missing palette token (off-palette
        colours on >= 5 units, near-identical ones merged at delta-E < 3), plus each scale the pages improvise
        (navy -rgb triplets for tints, a neutral overlay/shadow scale, a type scale, a z-index scale) when measured
        non-zero.
  existing  rows already in the registry for the same unit and lens (OD-* waves, and the live W4 figma row) are
        subtracted.

    python tools/open_design_census.py [--root <site>] [--json]
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

FAMILIES = {"learn": "learn/ (generated article family)", "tools": "tools/ (generated calculator family)"}
TAILWIND = "wh-tw*.css (Tailwind build)"


def unit_of(f: str) -> str:
    top = f.split("/", 1)[0] if "/" in f else ""
    if top in FAMILIES and f != "learn/index.html":
        return FAMILIES[top]
    if f.startswith("wh-tw") and f.endswith(".css"):
        return TAILWIND
    return f


def _lab(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in rgb)
    x, y, z = (r * .4124 + g * .3576 + b * .1805) / .95047, r * .2126 + g * .7152 + b * .0722, (r * .0193 + g * .1192 + b * .9505) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def merge_close(colours: dict[str, set]) -> list[tuple[list[str], set]]:
    """Group off-palette RGBs a reader cannot tell apart (CIE76 delta-E < 3) - two near-twins are one missing token."""
    keys = [k for k in colours if k.count(",") == 2]
    groups: list[tuple[list[str], set]] = []
    for k in sorted(keys, key=lambda k: -len(colours[k])):
        lab = _lab([float(x) for x in k.split(",")])
        for g in groups:
            if math.dist(lab, _lab([float(x) for x in g[0][0].split(",")])) < 3:
                g[0].append(k)
                g[1].update(colours[k])
                break
        else:
            groups.append(([k], set(colours[k])))
    return groups


def tint_by(root: Path, files: list[str]) -> dict[str, int]:
    """Hard-coded tints per palette token (the helper's palette, one analyzer pass in node)."""
    import subprocess
    import prove_design_source_drift as dsd  # noqa: E402
    css = [(root / f).read_text(encoding="utf-8", errors="replace") for f in files]
    css = [c if f.endswith(".css") else dsd.page_css(c) for f, c in zip(files, css)]
    js = (r"import { analyze } from '@projectwallace/css-analyzer';"
          r"import { palette, rgbOf, stripFallbacks } from './lib/wallace_drift.mjs';"
          r"let raw='';process.stdin.on('data',d=>raw+=d);process.stdin.on('end',()=>{"
          r"const {tokens,css}=JSON.parse(raw);const pal=palette(tokens);const by={};"
          r"for(const c of css){const r=analyze(stripFallbacks(c));"
          r"for(const [lit,n] of Object.entries(r.values.colors.unique||{})){if(/var\(/.test(lit))continue;"
          r"const x=rgbOf(lit);if(!x||x[3]>=1)continue;const k=x.slice(0,3).join(',');"
          r"if(pal.has(k))by[pal.get(k)]=(by[pal.get(k)]||0)+n;}}console.log(JSON.stringify(by));});")
    here = Path(__file__).resolve().parent
    r = subprocess.run(["node", "--input-type=module", "-e", js], input=json.dumps(
        {"tokens": (root / "tokens.css").read_text(encoding="utf-8"), "css": css}),
        capture_output=True, text=True, encoding="utf-8", cwd=here)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return json.loads(r.stdout)


def census(root: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import prove_design_source_drift as dsd  # noqa: E402
    files = dsd.design_files(root)
    m = dsd.measure(root, files)["files"]

    units = defaultdict(list)
    for f in files:
        units[unit_of(f)].append(f)
    # ★a generated family is ONE unit: its generator writes every member's CSS, so a per-page fix is reverted by the
    # next build. The learn articles carry 24 template generations (each article keeps the template of the day it was
    # stamped) - the counts differ a little, the shape does not; the row closes when the regenerated family measures
    # as one and at zero. Reported, so a family that drifts apart in SHAPE is seen, not assumed.
    generations = {}
    for u, fs in list(units.items()):
        if u in FAMILIES.values():
            sig = Counter(json.dumps({k: m[f].get(k) for k in ("exact", "tint", "off", "fontSizes", "zIndexes")}) for f in fs)
            generations[u] = len(sig)
    members = {k: sorted(units[v]) for k, v in FAMILIES.items() if v in units}

    page_units = sorted(u for u in units if u.endswith(".html") or u in FAMILIES.values())
    css_units = sorted(u for u in units if not (u.endswith(".html") or u in FAMILIES.values()))

    def agg(u):
        t = Counter()
        for f in units[u]:
            for k, v in m[f].items():
                if isinstance(v, int):
                    t[k] = max(t[k], v) if u in FAMILIES.values() else t[k] + v
        return t

    od_d = []
    for u in page_units + css_units:
        t = agg(u)
        # ★typeface is NOT counted here: rubric S1 "Token conformance (radius + typeface)" already owns it (and R1 owns
        # spacing) - an OD row on the same axis would be a duplicate the CX-UX cells close anyway.
        for cls, n in (("colour", t["exact"] + t["tint"] + t["off"]), ("type", t["fontSizes"]),
                       ("stacking", t["zIndexes"])):
            if n:
                od_d.append({"unit": u, "class": cls, "count": n})

    off_by = defaultdict(set)
    for f, v in m.items():
        for rgb in v.get("offRgbs", []):
            off_by[rgb].add(unit_of(f))
    # ★a cluster within delta-E 3 of a colour the palette ALREADY has is a mistyped token, not a missing one
    # (#1d2e44 beside --wh-navy-mid #1F2E45): its fix is "use the token", which the unit's OD-D colour row already
    # owes - so it is not a system row.
    tok_hex = re.findall(r"--[\w-]+\s*:\s*#([0-9a-fA-F]{6})\b", (root / "tokens.css").read_text(encoding="utf-8"))
    pal_lab = [_lab([int(h[i:i + 2], 16) for i in (0, 2, 4)]) for h in tok_hex]

    def near_token(k: str) -> bool:
        lab = _lab([float(x) for x in k.split(",")])
        return any(math.dist(lab, p) < 3 for p in pal_lab)

    groups = [g for g in merge_close(off_by) if len(g[1]) >= 5 and not near_token(g[0][0])]
    tot = Counter()
    for v in m.values():
        for k, n in v.items():
            if isinstance(n, int):
                tot[k] += n
    tokens_css = (root / "tokens.css").read_text(encoding="utf-8", errors="replace")
    scales = []
    # one row per palette colour pages tint by hand (>= 50 uses) that has no -rgb triplet to tint FROM; white folds
    # into the neutral scale, and orange/blue/green already have triplets (their tints are page migrations, OD-D)
    for name, n in sorted(tint_by(root, files).items(), key=lambda x: -x[1]):
        if n >= 50 and name != "--wh-surface-card" and f"{name}-rgb" not in tokens_css:
            scales.append((f"an {name}-rgb triplet, so its tints come from the token", n))
    if tot["neutral"]:
        scales.append(("a neutral overlay + shadow scale (black/white at an alpha)", tot["neutral"]))
    if tot["fontSizes"]:
        scales.append(("a type scale the pages use instead of raw font sizes", tot["fontSizes"]))
    if tot["zIndexes"]:
        scales.append(("a z-index (stacking) scale", tot["zIndexes"]))
    od_s = [{"token": "#" + "".join(f"{int(float(x)):02x}" for x in g[0][0].split(",")), "twins": len(g[0]) - 1,
             "units": len(g[1])} for g in groups] + [{"scale": s, "count": n} for s, n in scales]

    # rows the registry already holds for these lenses
    sys.path.insert(0, str(root / "tools"))
    import registry_io  # noqa: E402
    have = Counter(r.get("wave") for r in registry_io.load_doc()["trajectories"] if str(r.get("wave", "")).startswith("OD"))
    return {"files": len(files), "page_units": page_units, "css_units": css_units, "generations": generations,
            "family_members": members, "OD-P": len(page_units), "OD-D": od_d, "OD-S": od_s, "existing": dict(have)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = census(Path(a.root).resolve())
    if a.json:
        print(json.dumps(c, indent=1))
        return 0
    d_cls = Counter(r["class"] for r in c["OD-D"])
    print(f"open-design census over {c['files']} served files")
    print(f"  OD-P  Penpot comp per page unit ............ {c['OD-P']}  ({len(c['page_units'])} units)")
    print(f"  OD-D  token drift per (unit, class) ........ {len(c['OD-D'])}  {dict(d_cls)}  over "
          f"{len({r['unit'] for r in c['OD-D']})} units")
    print(f"  OD-S  missing tokens + scales .............. {len(c['OD-S'])}")
    for s in c["OD-S"]:
        print("        " + (f"{s['token']} (+{s['twins']} near-twins) on {s['units']} units" if "token" in s
                            else f"{s['scale']} ({s['count']} uses)"))
    print(f"  existing OD rows: {c['existing'] or 'none'}; template generations per family: {c['generations']}")
    total = c["OD-P"] + len(c["OD-D"]) + len(c["OD-S"]) - sum(c["existing"].values())
    print(f"  TO ADD: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
