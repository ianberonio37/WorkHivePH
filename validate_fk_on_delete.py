"""
FK ON DELETE Clause Validator (L0, ratcheted).
==================================================
Every `REFERENCES parent_table` foreign-key declaration MUST also
specify ON DELETE behavior (CASCADE / SET NULL / SET DEFAULT /
RESTRICT). Without an explicit clause, Postgres defaults to NO
ACTION which:
  - silently leaves orphan rows when the parent fragments
  - causes "violates foreign key" errors only at COMMIT, not at the
    failing row — debugging hell
  - varies by team convention (some assume CASCADE)

Explicit is safer than implicit. Each FK should declare what happens
when its parent disappears.

Exemption: inline marker `fk-on-delete-allow` on the same line.

Output: fk_on_delete_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "fk_on_delete_report.json"
BASELINE_PATH = ROOT / "fk_on_delete_baseline.json"

# REFERENCES <table>[(col)]  followed (eventually) by either ON DELETE ... or a terminator
REF_RE = re.compile(
    r"\bREFERENCES\s+[\w\"\.]+\s*(?:\([^)]*\))?(?P<tail>[^,;)]*)",
    re.IGNORECASE,
)
# Track constraint names superseded by a later ALTER ADD CONSTRAINT with ON DELETE.
SUPERSEDE_RE = re.compile(
    r"ADD\s+CONSTRAINT\s+(?P<name>[\w\"]+)\s+FOREIGN\s+KEY[\s\S]+?ON\s+DELETE",
    re.IGNORECASE,
)
# Walk every CREATE TABLE / ALTER ADD CONSTRAINT to capture the constraint name
# associated with a `REFERENCES` clause.
ADD_CONSTRAINT_FK_RE = re.compile(
    r"(?:ADD\s+CONSTRAINT\s+(?P<acname>[\w\"]+)\s+)?FOREIGN\s+KEY\s*\([^)]*\)\s+REFERENCES\s+[\w\"\.]+\s*(?:\([^)]*\))?(?P<tail>[^,;)]*)",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('fk_on_delete: ...')` for coverage credit.
CHECK_NAMES = ["fk_on_delete"]


def _strip_sql_strings_keep_lines(src: str) -> str:
    """Replace single-quoted strings and dollar-quoted blocks with whitespace
    so REFERENCES matches inside string literals are excluded but line
    numbers stay accurate."""
    def _rep(m):
        return "\n" * m.group(0).count("\n") + " " * (len(m.group(0)) - m.group(0).count("\n"))
    # Dollar-quoted: $$...$$ or $tag$...$tag$
    out = re.sub(r"\$([\w]*)\$.*?\$\1\$", _rep, src, flags=re.DOTALL)
    # Single-quoted strings (handles embedded ''):
    out = re.sub(r"'(?:''|[^'])*'", _rep, out)
    return out


def _check_file(path: Path, superseded: set) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    # Strip block + line SQL comments, then string literals.
    body_clean = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body_clean = re.sub(r"--[^\n]*", "", body_clean)
    body_clean = _strip_sql_strings_keep_lines(body_clean)
    # Walk REFERENCES matches; if the enclosing ADD CONSTRAINT name was
    # later superseded with ON DELETE, skip.
    for m in REF_RE.finditer(body_clean):
        tail = m.group("tail").lower()
        if "on delete" in tail:
            continue
        # Look backward up to 200 chars for an ADD CONSTRAINT name; if that
        # constraint was superseded elsewhere, accept this one.
        prefix = body_clean[max(0, m.start()-300): m.start()]
        cname_match = re.search(r"ADD\s+CONSTRAINT\s+(\"?[\w]+\"?)", prefix, re.IGNORECASE)
        if cname_match and cname_match.group(1).strip('"').lower() in superseded:
            continue
        # Also: if the ENCLOSING CREATE TABLE has a column whose FK gets
        # superseded by a follow-up ALTER, accept. Heuristic: look at the
        # column-name token just before "REFERENCES"; if any constraint name
        # containing that column was superseded, accept.
        col_match = re.search(r"(\w+)\s+(?:[\w()\[\]]+\s+)*(?:NULL\s+|NOT\s+NULL\s+|DEFAULT\s+\S+\s+)*REFERENCES\s", body_clean[max(0, m.start()-200): m.end()], re.IGNORECASE)
        if col_match:
            colname = col_match.group(1).lower()
            if any(colname in name for name in superseded):
                continue
        if "fk-on-delete-allow" in body[max(0, m.start()-200): m.end()+100]:
            continue
        line_no = body_clean.count("\n", 0, m.start()) + 1
        issues.append({"migration": path.name, "line": line_no,
                       "context": m.group(0)[:120].strip()})
    return issues


def main() -> int:
    mig_dir = ROOT / "supabase" / "migrations"
    if not mig_dir.exists():
        print("PASS — no migrations.")
        return 0
    # Pass 1: gather every constraint name superseded by a later ADD CONSTRAINT
    # FK ... ON DELETE statement.
    superseded = set()
    for path in sorted(mig_dir.glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"--[^\n]*", "", text)
        for m in SUPERSEDE_RE.finditer(text):
            superseded.add(m.group("name").strip('"').lower())
    issues = []
    scanned = 0
    for path in sorted(mig_dir.glob("*.sql")):
        scanned += 1
        issues.extend(_check_file(path, superseded))

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
        "summary": {"migrations_scanned": scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nFK ON DELETE Validator (L0)")
    print("=" * 56)
    print(f"  migrations scanned: {scanned}")
    print(f"  drift:              {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every FK declares explicit ON DELETE behavior.")
        return 0
    for i in issues[:25]:
        print(f"  {i['migration']}:{i['line']}  {i['context']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
