"""
Episodic Memory Wiring Validator (L0, ratcheted).
=================================================
Memory-stack flywheel Turn 1 (layer 02 "Episodic"). Asserts the durable
agent_episodic_memory layer (Phase 7) stays wired into the live request path.

Before this flywheel, agent_episodic_memory + its agent-memory-store CRUD fn
existed but NOTHING in the live gateway path read or wrote them — the episodic
layer was dead substrate. This validator is the regression guard that keeps the
wiring in place: a future refactor that drops the recall/persist calls, or
re-duplicates the table logic back into agent-memory-store, fails here at L0.

Checks (each missing one = a violation):
  1. _shared/episodic-memory.ts exists and exports recallEpisodic + persistEpisodic
     + formatEpisodicContext + evictIfOverCap.
  2. ai-gateway imports from _shared/episodic-memory.ts AND calls recallEpisodic
     AND calls persistEpisodic.
  3. ai-gateway defines a non-empty EPISODIC_MEMORY_AGENTS set.
  4. agent-memory-store imports recallEpisodic/persistEpisodic from the shared
     module (single source of truth — must NOT re-declare its own table-level
     recall/store/eviction logic).

Output: episodic_memory_wiring_report.json. Exit 1 on regression vs baseline.
Allow individual checks with `# episodic-wiring-allow: <reason>` is NOT
supported — these are structural invariants, not per-line lint.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FUNCS = ROOT / "supabase" / "functions"
SHARED = FUNCS / "_shared" / "episodic-memory.ts"
GATEWAY = FUNCS / "ai-gateway" / "index.ts"
STORE = FUNCS / "agent-memory-store" / "index.ts"
REPORT_PATH = ROOT / "episodic_memory_wiring_report.json"
BASELINE_PATH = ROOT / "episodic_memory_wiring_baseline.json"


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def main() -> int:
    violations: list[dict] = []

    def need(cond: bool, code: str, detail: str) -> None:
        if not cond:
            violations.append({"check": code, "detail": detail})

    shared = _read(SHARED)
    need(bool(shared), "shared-module-missing",
         "_shared/episodic-memory.ts does not exist")
    for fn in ("recallEpisodic", "persistEpisodic", "formatEpisodicContext", "evictIfOverCap"):
        need(bool(re.search(rf"export\s+(?:async\s+)?function\s+{fn}\b", shared)),
             "shared-export-missing", f"_shared/episodic-memory.ts must export {fn}()")

    gw = _read(GATEWAY)
    need(bool(gw), "gateway-missing", "ai-gateway/index.ts does not exist")
    need('from "../_shared/episodic-memory.ts"' in gw,
         "gateway-import-missing",
         "ai-gateway must import from ../_shared/episodic-memory.ts")
    need(bool(re.search(r"\brecallEpisodic\s*\(", gw)),
         "gateway-recall-missing",
         "ai-gateway must call recallEpisodic() (episodic recall not wired)")
    need(bool(re.search(r"\bpersistEpisodic\s*\(", gw)),
         "gateway-persist-missing",
         "ai-gateway must call persistEpisodic() (episodic store not wired)")
    m = re.search(r"EPISODIC_MEMORY_AGENTS[^=]*=\s*new\s+Set\(\s*\[(?P<body>.*?)\]",
                  gw, re.DOTALL)
    agents = [a for a in re.findall(r'"([^"]+)"', m.group("body"))] if m else []
    need(len(agents) > 0,
         "gateway-agentset-empty",
         "ai-gateway must define a non-empty EPISODIC_MEMORY_AGENTS set")

    store = _read(STORE)
    need(bool(store), "store-missing", "agent-memory-store/index.ts does not exist")
    need('from "../_shared/episodic-memory.ts"' in store,
         "store-import-missing",
         "agent-memory-store must import recall/persist from the shared module")
    # Single-source-of-truth guard: agent-memory-store must NOT re-declare its
    # own table-level helpers (the duplication this flywheel removed).
    need(not re.search(r"\basync\s+function\s+(?:recall|store|evictIfOverCap)\b", store),
         "store-duplicate-logic",
         "agent-memory-store re-declares recall/store/evictIfOverCap — use the shared module")

    total = len(violations)
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("violations", 0)
        except Exception:
            baseline = total
    else:
        baseline = total
        BASELINE_PATH.write_text(json.dumps({"violations": baseline, "established": True}, indent=2), encoding="utf-8")
    if total < baseline:
        baseline = total
        BASELINE_PATH.write_text(json.dumps({"violations": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"violations": total, "baseline": baseline,
                    "episodic_memory_agents": agents},
        "violations": violations,
    }, indent=2), encoding="utf-8")

    print("\nEpisodic Memory Wiring Validator (L0)")
    print("=" * 56)
    print(f"  episodic memory agents:   {', '.join(agents) or '(none)'}")
    print(f"  violations:               {total}  (baseline: {baseline})")
    if total == 0:
        print("\n  PASS — episodic memory layer is wired end-to-end.")
        return 0
    for v in violations:
        print(f"    [{v['check']}] {v['detail']}")
    print(f"\n  {'PASS (at baseline)' if total <= baseline else 'FAIL (regression)'}")
    return 1 if total > baseline else 0


# Sentinel binding: name the L2 test `test('episodic_memory_wiring: ...')`.
CHECK_NAMES = ["episodic_memory_wiring"]

if __name__ == "__main__":
    sys.exit(main())
