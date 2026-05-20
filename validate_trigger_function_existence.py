"""
Trigger Function Existence Validator (L0, ratcheted).
======================================================
Every `CREATE TRIGGER ... EXECUTE FUNCTION fn_name(...)` must
reference a function defined in the migrations. Catches schema-rename
drift where a trigger fires but the function was renamed/removed.

Output: trigger_function_existence_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "trigger_function_existence_report.json"
BASELINE_PATH = ROOT / "trigger_function_existence_baseline.json"

CREATE_TRIGGER_RE = re.compile(
    r"""CREATE\s+TRIGGER\s+(?P<name>[\w]+)\s+(?:[\s\S]*?)EXECUTE\s+(?:PROCEDURE|FUNCTION)\s+(?:public\.)?(?P<fn>[a-z_][\w]*)""",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('trigger_function_existence: ...')` for coverage credit.
CHECK_NAMES = ["trigger_function_existence"]


def main() -> int:
    reg = json.loads((ROOT / "canonical_registry.json").read_text(encoding="utf-8"))
    rpcs = {r.lower() for r in reg.get("rpcs", {})}

    issues = []
    total = 0
    seen = set()

    mig_dir = ROOT / "supabase" / "migrations"
    if mig_dir.exists():
        for mig in sorted(mig_dir.glob("*.sql")):
            text = mig.read_text(encoding="utf-8", errors="replace")
            for m in CREATE_TRIGGER_RE.finditer(text):
                total += 1
                fn = m.group("fn").lower()
                trig = m.group("name")
                if fn in rpcs: continue
                key = (trig, fn)
                if key in seen: continue
                seen.add(key)
                issues.append({"trigger": trig, "function": fn, "migration": mig.name})

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("issues", 0)
        except Exception: baseline = 0
    else:
        baseline = len(issues)
        BASELINE_PATH.write_text(json.dumps({"issues": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(issues) < baseline:
        baseline = len(issues)
        BASELINE_PATH.write_text(json.dumps({"issues": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"total_triggers": total, "total_issues": len(issues), "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nTrigger Function Existence Validator (L0)")
    print("=" * 56)
    print(f"  triggers found:   {total}")
    print(f"  drift:            {len(issues)}  (baseline: {baseline})")
    if not issues:
        print("\n  PASS — every CREATE TRIGGER target function exists.")
        return 0
    for i in issues[:20]:
        print(f"  trigger='{i['trigger']}' → function '{i['function']}' missing  ({i['migration']})")
    return 1 if len(issues) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
