"""
Edge Error-Capture Adoption Validator (Arc T / T2 keystone, 2026-07-01).
=======================================================================
Locks the T2 keystone: every edge fn must route its handler through the shared
`serveObserved()` wrapper (_shared/observability.ts) so any UNHANDLED throw is
aggregated into wh_traces (via trackError) instead of vanishing as a generic
edge-runtime 500. Proven live by fault-injection (roadmap OBSERVABILITY_SLO §4).

Two layers:
  L1 wrapper integrity  - _shared/observability.ts exists, imports + calls
                          trackError in the catch path, and exports both
                          withObservability + serveObserved. Guards against the
                          wrapper being gutted while keeping its name.
  L2 adoption floor     - count of fns importing + calling serveObserved. The
                          count is a forward-only ratchet (baseline = floor);
                          a fn dropping back to bare serve() fails the gate.

Exit codes:
  0  wrapper intact AND adoption >= floor
  1  wrapper broken OR adoption dropped
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FN_DIR = ROOT / "supabase" / "functions"
WRAPPER = FN_DIR / "_shared" / "observability.ts"
REPORT = ROOT / "edge_error_capture_report.json"
BASELINE = ROOT / "edge_error_capture_baseline.json"

CHECK_NAMES = ["edge_error_capture", "edge-error-capture"]

IMPORT_RE = re.compile(r'from\s+["\']\.\./_shared/observability\.ts["\']')
CALL_RE   = re.compile(r"\bserveObserved\s*\(")


def check_wrapper() -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not WRAPPER.exists():
        return False, ["_shared/observability.ts missing"]
    t = WRAPPER.read_text(encoding="utf-8", errors="replace")
    if not re.search(r'from\s+["\']\./error-tracker\.ts["\']', t):
        issues.append("does not import from error-tracker.ts")
    if "trackError(" not in t:
        issues.append("does not call trackError() (no wh_traces aggregation)")
    if "export function withObservability" not in t:
        issues.append("does not export withObservability")
    if "export function serveObserved" not in t:
        issues.append("does not export serveObserved")
    if "catch" not in t:
        issues.append("no catch block (nothing captures the throw)")
    return (len(issues) == 0), issues


def scan() -> dict:
    if not FN_DIR.exists():
        return {"fns": [], "adopters": [], "non_adopters": [], "error": "no functions dir"}
    fns, adopters, non_adopters, ft_adopters = [], [], [], []
    for entry in sorted(FN_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        index = entry / "index.ts"
        if not index.exists():
            continue
        text = index.read_text(encoding="utf-8", errors="replace")
        imports = bool(IMPORT_RE.search(text))
        calls = bool(CALL_RE.search(text))
        fns.append({"fn": entry.name, "imports": imports, "calls": calls})
        (adopters if (imports and calls) else non_adopters).append(entry.name)
        # T2b: HANDLED-error aggregation — fns whose internal catch calls failTracked
        # (non-leaky 500 helper) OR trackHandled (shape-preserving aggregation).
        if re.search(r"\b(failTracked|trackHandled)\s*\(", text):
            ft_adopters.append(entry.name)
    return {"fns": fns, "adopters": adopters, "non_adopters": non_adopters,
            "failtracked_adopters": ft_adopters}


def main() -> int:
    wrapper_ok, wrapper_issues = check_wrapper()
    result = scan()
    n = len(result["adopters"])
    total = len(result["fns"])
    result.update({"wrapper_ok": wrapper_ok, "wrapper_issues": wrapper_issues,
                   "count": n, "total_fns": total})

    ft = len(result["failtracked_adopters"])           # T2b handled-error adopters
    floor, ft_floor = n, ft
    ft_key_missing = False
    if BASELINE.exists():
        try:
            b = json.loads(BASELINE.read_text(encoding="utf-8"))
            floor = int(b.get("adopters", n))
            ft_key_missing = "failtracked" not in b
            ft_floor = int(b.get("failtracked", ft))
        except Exception:
            pass
        if ft_key_missing:  # first run after T2b landed — lock the handled-error floor
            BASELINE.write_text(json.dumps({"adopters": floor, "failtracked": ft}), encoding="utf-8")
            ft_floor = ft
    else:
        BASELINE.write_text(json.dumps({"adopters": n, "failtracked": ft}), encoding="utf-8")
    result.update(floor=floor, failtracked_count=ft, failtracked_floor=ft_floor)
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Edge error-capture: serveObserved {n}/{total} (floor {floor}); "
          f"failTracked handled-error adopters {ft} (floor {ft_floor}).")
    if result["non_adopters"]:
        print(f"  serveObserved non-adopters: {', '.join(result['non_adopters'])}")

    if not wrapper_ok:
        print(f"\033[91mFAIL: wrapper integrity broken -> {'; '.join(wrapper_issues)}\033[0m")
        return 1
    # ★EVERY-FN assertion (Arc T depth, 2026-07-20 — the "a floor ratchet under-covers" meta-lesson that
    # recurred all session: read-isolation name-filter / DEDUP_PATHS / FIELD_WRITE_PAGES / CRITICAL_TABLES).
    # A pure floor passes when a NEW fn ships un-wrapped (n stays >= floor) — leaving it un-observed: an
    # unhandled throw leaks a stack + never aggregates to wh_traces, so it is INVISIBLE to the SLO alert.
    # Assert EVERY edge fn routes serveObserved (derived denominator), minus a documented exempt allowlist.
    NON_OBSERVED_EXEMPT: set[str] = set()   # none — all fns route serveObserved. Add a fn here ONLY with a
    # proof it cannot throw a runtime error (a reason comment), never to silence a real un-observed surface.
    real_non = [f for f in result["non_adopters"] if f not in NON_OBSERVED_EXEMPT]
    if real_non:
        print(f"\033[91mFAIL: {len(real_non)} edge fn(s) route bare serve() without serveObserved -> an "
              f"unhandled throw leaks + is invisible to the SLO alert (add serveObserved or an EXEMPT reason): "
              f"{', '.join(real_non)}\033[0m")
        return 1
    if n < floor:
        print(f"\033[91mFAIL: serveObserved adoption dropped {floor} -> {n} (fns reverted to bare serve())\033[0m")
        return 1
    if ft < ft_floor:
        print(f"\033[91mFAIL: failTracked (T2b handled-error) adoption dropped {ft_floor} -> {ft}\033[0m")
        return 1
    if n > floor or ft > ft_floor:
        BASELINE.write_text(json.dumps({"adopters": max(n, floor), "failtracked": max(ft, ft_floor)}), encoding="utf-8")
        print(f"\033[92mPASS: floors lifted (serveObserved {floor}->{n}, failTracked {ft_floor}->{ft})\033[0m")
        return 0
    print("\033[92mPASS: wrapper intact + serveObserved + failTracked adoption at floor\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
