"""
api_adoption_census.py — Layer A (APIs) adoption census, A-P0.
================================================================================
The Layer-A instantiation of the P0 template proven on Layer F
(FULLSTACK_COMPONENT_LIBRARY_ROADMAP §1): which edge functions that NEED a
canonical `_shared/` module actually IMPORT it?

SSOT: api_component_registry.json  (canonical modules + detect/need rules)
Surfaces: supabase/functions/*/index.ts  (58 at opening; _shared/tests skipped)

DETECTION: import-based — a function adopts a module when its index.ts imports
it (directly; re-exports via other _shared modules count for THAT module, not
transitively — v1 keeps the honest, simple reading).

NEED rules (∪ adopters, same union law as Layer F):
  family         every function
  tenant-data    touches tenant rows (hive_id / from('…') on tenant tables)
  llm            calls an LLM (chat/completions, model:, messages:)
  outbound-fetch fetch( to a non-supabase URL
  census-only    optional vocabulary (no denominator)

Floors only ratchet UP from ANY writer (Layer F lesson). Gate: a future
validate_api_adoption.py (A-P2) reads these floors.

OUTPUT: api_adoption_baseline.json + api_adoption_report.md
USAGE:  python tools/api_adoption_census.py
"""

from __future__ import annotations

import datetime
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "api_component_registry.json"
OUT_JSON = ROOT / "api_adoption_baseline.json"
OUT_MD = ROOT / "api_adoption_report.md"
FN_DIR = ROOT / "supabase" / "functions"

BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.M)


def strip_comments(src: str) -> str:
    return LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub("", src))


def imports_module(src: str, module: str) -> bool:
    # import … from "../_shared/<module>"  (any quote style, ./ or ../ path)
    return re.search(r"from\s+['\"][./]*_shared/" + re.escape(module) + r"['\"]", src) is not None


NEED_FNS = {
    "family":         lambda s: True,
    "tenant-data":    lambda s: re.search(r"hive_id|\.from\(\s*['\"]", s) is not None,
    "llm":            lambda s: re.search(r"chat/completions|['\"]model['\"]\s*:|messages\s*:|generateContent", s) is not None,
    "outbound-fetch": lambda s: re.search(r"fetch\(\s*[`'\"]https?://(?!.*supabase)", s) is not None,
}


def run_census():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fns = {}
    for d in sorted(FN_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name == "tests":
            continue
        idx = d / "index.ts"
        if idx.exists():
            fns[d.name] = strip_comments(idx.read_text(encoding="utf-8", errors="ignore"))

    rows = []
    for comp in reg["components"]:
        adopters = [n for n, src in fns.items()
                    if any(imports_module(src, det["module"]) for det in comp["detect"])]
        exempt = set(comp.get("exempt", []))
        adopters = [a for a in adopters if a not in exempt]
        if comp["need"] == "census-only":
            rows.append({"id": comp["id"], "class": comp["class"], "name": comp["name"],
                         "satisfies": comp["satisfies"], "mode": "census-only",
                         "adopters_n": len(adopters), "adopters": sorted(adopters)})
            continue
        need_fn = NEED_FNS[comp["need"]]
        need = sorted(({n for n, src in fns.items() if need_fn(src)} | set(adopters)) - exempt)
        gap = sorted(set(need) - set(adopters))
        pct = round(100 * len(adopters) / len(need)) if need else None
        rows.append({"id": comp["id"], "class": comp["class"], "name": comp["name"],
                     "satisfies": comp["satisfies"], "mode": "measured", "need_rule": comp["need"],
                     "adopters_n": len(adopters), "need_n": len(need), "pct": pct,
                     "adopters": sorted(adopters), "gap": gap})
    return rows, len(fns)


def main() -> int:
    rows, n_fns = run_census()
    measured = [r for r in rows if r["mode"] == "measured"]
    prior = {}
    if OUT_JSON.exists():
        try:
            prior = json.loads(OUT_JSON.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            prior = {}
    floors = {r["id"]: max(r["adopters_n"], prior.get(r["id"], 0)) for r in measured}
    OUT_JSON.write_text(json.dumps({
        "_doc": "Layer A adoption baseline. Floors are FORWARD-ONLY from any writer (Layer F law).",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "functions": n_fns, "rows": rows, "floors": floors,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    L = ["# API Adoption Report — Layer A (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §1)\n",
         f"> MEASURED {datetime.date.today().isoformat()} over **{n_fns}** edge functions "
         "(import-based; need ∪ adopters; census-only rows carry no %).\n",
         "| ID | Class | Canonical module | Adoption | % | Gap (first 6) |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["mode"] == "census-only":
            L.append(f"| {r['id']} | {r['class']} | {r['name']} | {r['adopters_n']} fn(s) | n/a | — |")
        else:
            gap_s = ", ".join(r["gap"][:6]) + (" …" if len(r["gap"]) > 6 else "")
            L.append(f"| {r['id']} | {r['class']} | {r['name']} | **{r['adopters_n']}/{r['need_n']}** "
                     f"({r['need_rule']}) | **{r['pct']}%** | {gap_s or '—'} |")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"API adoption census -- {n_fns} functions, {len(rows)} registry rows")
    for r in measured:
        print(f"  {r['id']:4s} {r['name'][:44]:44s} {r['adopters_n']:3d}/{r['need_n']:<3d} {str(r['pct'])+'%':>5s}")
    print("  -> api_adoption_baseline.json + api_adoption_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
