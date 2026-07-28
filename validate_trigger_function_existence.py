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

# `DROP TRIGGER [IF EXISTS] name ON table` — used to tell a superseded trigger from a broken one.
DROP_TRIGGER_RE = re.compile(
    r"""DROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?(?P<name>[\w]+)\s+ON\s""",
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

    # A TRIGGER DROPPED BY A LATER MIGRATION IS NOT DRIFT (2026-07-28).
    #
    # Migrations are immutable, so a rename is necessarily "migration A creates trg_x running
    # guard_y; migration B drops both and creates trg_z running bind_y". Reading A in isolation
    # reports guard_y as a missing function — but nothing is missing: B superseded A on purpose,
    # and the LIVE database has exactly one trigger and one function.
    #
    # That is what happened here: 033 added trg_progress_log_is_mine, and 035 renamed the pair to
    # join the platform's bind_* convention (so the DB-adoption census could recognise the
    # attribution pin), dropping the originals. Failing on it would make every legitimate rename
    # permanently red and push the next person toward editing a committed migration to clear it —
    # the exact thing the immutability gate exists to prevent.
    #
    # So a (trigger, function) pair is only checked if no LATER migration drops that trigger.
    dropped_later: dict[str, str] = {}   # trigger name -> migration that drops it
    if mig_dir.exists():
        for mig in sorted(mig_dir.glob("*.sql")):
            for d in DROP_TRIGGER_RE.finditer(mig.read_text(encoding="utf-8", errors="replace")):
                dropped_later[d.group("name")] = mig.name

    if mig_dir.exists():
        for mig in sorted(mig_dir.glob("*.sql")):
            text = mig.read_text(encoding="utf-8", errors="replace")
            for m in CREATE_TRIGGER_RE.finditer(text):
                total += 1
                fn = m.group("fn").lower()
                trig = m.group("name")
                if fn in rpcs: continue
                # dropped by a migration that sorts after the one that created it
                dropper = dropped_later.get(trig)
                if dropper and dropper > mig.name: continue
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
