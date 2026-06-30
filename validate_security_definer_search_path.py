"""
SECURITY DEFINER search_path Validator (L0, ratcheted).
=========================================================
Every Postgres function declared `SECURITY DEFINER` MUST also set
`SET search_path = ''` (or an explicit schema list like `pg_catalog, public`).
Without it, an attacker who controls a schema earlier on the user's
search_path can inject a function that masquerades as a builtin
(e.g. `array_to_string`) and run with the definer's elevated rights.
Supabase + Postgres docs flag this as a critical hardening item; the
linter `function_search_path_mutable` warns on it.

Output: security_definer_search_path_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "security_definer_search_path_report.json"
BASELINE_PATH = ROOT / "security_definer_search_path_baseline.json"

# Matches CREATE [OR REPLACE] FUNCTION ... AS [body] — body terminator is
# the next LANGUAGE clause or semicolon at depth 0. We just need the
# function header window (CREATE FUNCTION ... LANGUAGE) — search_path
# and SECURITY DEFINER both appear before the body.
FUNC_HEADER_RE = re.compile(
    r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?P<sig>(?:"?[\w]+"?\.)?"?[\w]+"?\s*\([^)]*\))(?P<header>[\s\S]*?)(?:AS\s*\$|AS\s*\')',
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('security_definer_search_path: ...')` for coverage credit.
CHECK_NAMES = ["security_definer_search_path"]


def _fn_base_name(sig: str) -> str:
    """Strip schema + quoting + args. 'public.foo("x" text)' -> 'foo'."""
    s = sig
    s = re.sub(r'\([^)]*\)', '', s)
    s = s.replace('"', '').strip()
    if '.' in s:
        s = s.rsplit('.', 1)[-1]
    return s.lower()


def main() -> int:
    issues = []
    total_definer = 0
    seen = set()

    mig_dir = ROOT / "supabase" / "migrations"
    if not mig_dir.exists():
        print("PASS — no migrations.")
        return 0

    # Pass 1: collect every fn covered by a later `ALTER FUNCTION ... SET search_path`
    altered = set()
    alter_re = re.compile(
        # accept both `SET search_path = …` and `SET search_path TO …` (both are valid PG syntax)
        r'ALTER\s+FUNCTION\s+(?:"?[\w]+"?\.)?"?([\w]+)"?\s*(?:\([^)]*\))?\s+SET\s+search_path\s*(?:=|\s+TO\b)',
        re.IGNORECASE,
    )
    for mig in sorted(mig_dir.glob("*.sql")):
        text = mig.read_text(encoding="utf-8", errors="replace")
        for m in alter_re.finditer(text):
            altered.add(m.group(1).lower())

    for mig in sorted(mig_dir.glob("*.sql")):
        text = mig.read_text(encoding="utf-8", errors="replace")
        for m in FUNC_HEADER_RE.finditer(text):
            sig = re.sub(r"\s+", "", m.group("sig"))
            header = m.group("header")
            if not re.search(r"SECURITY\s+DEFINER", header, re.IGNORECASE):
                continue
            total_definer += 1
            # Inline SET search_path = ... OR ... TO ... in the function header (both valid PG syntax)
            if re.search(r"SET\s+search_path\s*(?:=|\s+TO\b)", header, re.IGNORECASE):
                continue
            # Covered by a later ALTER FUNCTION ... SET search_path
            if _fn_base_name(sig) in altered:
                continue
            # allow marker (look in a wider context window)
            if "security-definer-allow" in text[max(0, m.start()-100): m.end()+200]:
                continue
            key = (mig.name, sig)
            if key in seen: continue
            seen.add(key)
            issues.append({"migration": mig.name, "function": sig})

    drift = len(issues)
    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if drift < baseline:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"total_definer_functions": total_definer, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nSECURITY DEFINER search_path Validator (L0)")
    print("=" * 56)
    print(f"  SECURITY DEFINER fns: {total_definer}")
    print(f"  drift:                {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every SECURITY DEFINER fn sets search_path.")
        return 0
    for i in issues[:30]:
        print(f"  {i['migration']}  → {i['function']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
