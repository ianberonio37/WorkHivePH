"""
LLM Cache Adoption Validator (L0, P1 roadmap 2026-05-27).
==========================================================
Closes the (CA, G0) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

Tracks how many edge fns use `cached()` from _shared/cache.ts for their
deterministic LLM calls. This is a *measurement* validator — it does not
fail on low adoption (some fns legitimately can't cache, e.g. anything
with user-content in the prompt). It only fails when adoption REGRESSES:
a fn that used to cache and no longer does.

Adoption counter goes UP over time; baseline is the *floor* not the ceiling.

Exit codes:
  0  adoption count ≥ baseline
  1  adoption count < baseline (a fn dropped caching)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FN_DIR = ROOT / "supabase" / "functions"
REPORT = ROOT / "llm_cache_adoption_report.json"
BASELINE = ROOT / "llm_cache_adoption_baseline.json"

CHECK_NAMES = ["llm_cache_adoption"]

# Match either the explicit import or the `cached(` call site.
CACHED_IMPORT_RE = re.compile(r'from\s+["\']\.\./_shared/cache\.ts["\']')
CACHED_CALL_RE   = re.compile(r"\bcached\s*<|\bcached\s*\(")


def scan() -> dict:
    if not FN_DIR.exists():
        return {"fns": [], "adopters": [], "error": "no functions dir"}
    fns, adopters = [], []
    for entry in sorted(FN_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"): continue
        index = entry / "index.ts"
        if not index.exists(): continue
        text = index.read_text(encoding="utf-8", errors="replace")
        imports = bool(CACHED_IMPORT_RE.search(text))
        calls   = bool(CACHED_CALL_RE.search(text))
        row = {
            "fn":      entry.name,
            "imports": imports,
            "calls":   calls,
        }
        fns.append(row)
        # Real adoption = both imports AND calls cached(). Import-only doesn't
        # count (it's just an unused helper).
        if imports and calls:
            adopters.append(entry.name)
    return {"fns": fns, "adopters": adopters}


def main() -> int:
    result = scan()
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    n_adopters = len(result["adopters"])

    # Floor baseline: adoption can never go below the locked value.
    baseline = n_adopters
    if BASELINE.exists():
        try: baseline = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("adopters", n_adopters))
        except Exception: pass
    else:
        BASELINE.write_text(json.dumps({"adopters": n_adopters}), encoding="utf-8")

    print(f"LLM cache adoption: {n_adopters} fn(s) use cached() (floor {baseline}).")
    print(f"  Adopters: {', '.join(result['adopters']) or '(none)'}")
    if n_adopters < baseline:
        print(f"\033[91mFAIL: adoption dropped {baseline} → {n_adopters} — a fn stopped caching.\033[0m")
        return 1
    if n_adopters > baseline:
        BASELINE.write_text(json.dumps({"adopters": n_adopters}), encoding="utf-8")
        print(f"\033[92mPASS: floor lifted {baseline} → {n_adopters}\033[0m")
        return 0
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
