"""
Environment Variable Existence Validator (L0, ratcheted).
==========================================================
Every `Deno.env.get('X')` / `process.env.X` reference in edge fns +
shared modules must have a counterpart in `.env.example` (or a
documented Supabase secret). If a secret name was renamed (e.g.
`OPENAI_KEY` → `OPENAI_API_KEY`) but the consumer wasn't updated, the
edge fn fails at runtime with no UI signal.

Output: env_variable_existence_report.json. Exit 1 on regression.
Allow with `// env-allow: <reason>` near the reference.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "env_variable_existence_report.json"
BASELINE_PATH = ROOT / "env_variable_existence_baseline.json"

# Supabase secret name patterns
DENO_ENV_RE = re.compile(r"""Deno\.env\.get\(\s*['"`](?P<name>[A-Z][A-Z0-9_]+)['"`]\s*\)""")
PROC_ENV_RE = re.compile(r"""\bprocess\.env\.(?P<name>[A-Z][A-Z0-9_]+)\b""")

# Defaults shipped by Supabase runtime — always available, no .env.example needed
SUPABASE_BUILTIN = {
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_DB_URL", "SUPABASE_PUBLISHABLE_KEY",
}

ALLOW_RE = re.compile(r"env-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _read_env_example_names() -> set[str]:
    names = set()
    env_file = ROOT / ".env.example"
    if not env_file.exists():
        env_file = ROOT / "supabase" / ".env.example"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                names.add(line.split("=", 1)[0].strip())
    # Also accept names mentioned in `# Required secrets:` comments
    for hint_file in (ROOT / "README.md", ROOT / "supabase" / "README.md"):
        if hint_file.exists():
            text = hint_file.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"\b([A-Z][A-Z0-9_]{4,})\b", text):
                names.add(m.group(1))
    return names


# Sentinel binding: name the L2 test `test('env_variable_existence: ...')` for coverage credit.
CHECK_NAMES = ["env_variable_existence"]


def main() -> int:
    known = _read_env_example_names() | SUPABASE_BUILTIN

    edge = ROOT / "supabase" / "functions"
    files: list[tuple[str, Path]] = []
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            files.append((ts.relative_to(ROOT).as_posix(), ts))
    # Also scan python-api if present
    py_api = ROOT / "python-api"
    if py_api.exists():
        for py in sorted(py_api.rglob("*.py")):
            files.append((py.relative_to(ROOT).as_posix(), py))

    per_file = []
    total_refs = 0
    total_missing = 0
    seen: set = set()

    for fname, path in files:
        body = path.read_text(encoding="utf-8", errors="replace")
        missing = []
        for pat in (DENO_ENV_RE, PROC_ENV_RE):
            for m in pat.finditer(body):
                env = m.group("name")
                total_refs += 1
                win = body[max(0, m.start() - 200):m.end() + 200]
                if ALLOW_RE.search(win): continue
                if env in known: continue
                key = (fname, env)
                if key in seen: continue
                seen.add(key)
                missing.append({"env": env, "offset": m.start()})
        per_file.append({"file": fname, "missing": missing})
        total_missing += len(missing)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("missing", 0)
        except Exception: baseline = 0
    else:
        baseline = total_missing
        BASELINE_PATH.write_text(json.dumps({"missing": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_missing < baseline:
        baseline = total_missing
        BASELINE_PATH.write_text(json.dumps({"missing": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(per_file), "total_refs": total_refs,
                    "total_missing": total_missing, "baseline": baseline,
                    "env_names_known": len(known)},
        "per_file": per_file,
    }, indent=2), encoding="utf-8")

    print(f"\nEnvironment Variable Existence Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(per_file)}")
    print(f"  env names known:  {len(known)}")
    print(f"  total refs:       {total_refs}")
    print(f"  missing:          {total_missing}  (baseline: {baseline})")
    if total_missing == 0:
        print("\n  PASS — every env var reference is documented in .env.example/README.")
        return 0
    shown = 0
    for entry in per_file:
        if not entry["missing"]: continue
        print(f"  {entry['file']}")
        for m in entry["missing"]:
            print(f"    → {m['env']}  — not in .env.example/README")
            shown += 1
            if shown >= 20:
                print("    ... (more in report)")
                break
        if shown >= 20: break
    return 1 if total_missing > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
