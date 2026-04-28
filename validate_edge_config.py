"""
Edge Function Config Validator
================================
Checks that every function directory under supabase/functions/ has an
explicit [functions.NAME] entry in supabase/config.toml with:
  - verify_jwt explicitly set (true or false — no silent default)
  - entrypoint file present on disk

Root cause this catches: analytics-orchestrator was deployed without a
config.toml entry, so verify_jwt was inherited from Supabase's default
rather than being explicitly configured. Missing auth headers caused 500.

Usage: python validate_edge_config.py
Output: edge_config_report.json
"""
import os, re, sys, json

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE          = os.path.dirname(os.path.abspath(__file__))
FUNCTIONS_DIR = os.path.join(BASE, "supabase", "functions")
CONFIG_TOML   = os.path.join(BASE, "supabase", "config.toml")

# Functions that are internal Supabase scaffolding — not deployed by us
IGNORED_DIRS = {"_shared", "_utils", "_types"}


def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"


def read_config_toml():
    if not os.path.exists(CONFIG_TOML):
        return None
    with open(CONFIG_TOML, encoding="utf-8") as f:
        return f.read()


def get_function_dirs():
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    return sorted(
        d for d in os.listdir(FUNCTIONS_DIR)
        if os.path.isdir(os.path.join(FUNCTIONS_DIR, d))
        and d not in IGNORED_DIRS
        and not d.startswith(".")
    )


def parse_config_sections(toml_content):
    """Return dict of {function_name: {key: value}} from [functions.NAME] sections."""
    sections = {}
    current = None
    for line in toml_content.splitlines():
        stripped = line.strip()
        m = re.match(r'^\[functions\.(.+)\]$', stripped)
        if m:
            current = m.group(1)
            sections[current] = {}
        elif current and "=" in stripped and not stripped.startswith("#"):
            key, _, val = stripped.partition("=")
            sections[current][key.strip()] = val.strip().strip('"').strip("'")
    return sections


def run_checks():
    issues = []

    if not os.path.exists(CONFIG_TOML):
        issues.append({"check": "config_exists",
                       "reason": "supabase/config.toml not found"})
        return issues

    toml      = read_config_toml()
    sections  = parse_config_sections(toml)
    func_dirs = get_function_dirs()

    if not func_dirs:
        return issues  # no functions to check

    for fn in func_dirs:
        # ── 1. Function must have a config.toml entry ─────────────────────────
        if fn not in sections:
            issues.append({
                "check":    "function_in_config",
                "function": fn,
                "reason":   (
                    f"supabase/functions/{fn}/ exists but [functions.{fn}] "
                    "is missing from config.toml — JWT verification setting "
                    "is undocumented and relies on Supabase deploy-time default"
                ),
            })
            continue

        cfg = sections[fn]

        # ── 2. verify_jwt must be explicit ───────────────────────────────────
        if "verify_jwt" not in cfg:
            issues.append({
                "check":    "verify_jwt_explicit",
                "function": fn,
                "reason":   (
                    f"[functions.{fn}] has no verify_jwt setting — "
                    "defaults to true, requires Authorization header on every call"
                ),
            })

        # ── 3. entrypoint must exist on disk ─────────────────────────────────
        if "entrypoint" in cfg:
            ep_rel  = cfg["entrypoint"].lstrip("./")
            ep_path = os.path.join(BASE, "supabase", ep_rel)
            if not os.path.exists(ep_path):
                issues.append({
                    "check":    "entrypoint_exists",
                    "function": fn,
                    "reason":   (
                        f"[functions.{fn}] entrypoint "
                        f"'{cfg['entrypoint']}' not found on disk"
                    ),
                })
        else:
            default_ep = os.path.join(FUNCTIONS_DIR, fn, "index.ts")
            if not os.path.exists(default_ep):
                issues.append({
                    "check":    "entrypoint_exists",
                    "function": fn,
                    "reason":   (
                        f"[functions.{fn}] no entrypoint key set "
                        "and default index.ts does not exist"
                    ),
                })

    return issues


CHECK_NAMES = [
    "config_exists",
    "function_in_config",
    "verify_jwt_explicit",
    "entrypoint_exists",
]
CHECK_LABELS = {
    "config_exists":       "CFG  config.toml exists",
    "function_in_config":  "CFG  Every function dir has config.toml entry",
    "verify_jwt_explicit": "CFG  verify_jwt explicitly set on every function",
    "entrypoint_exists":   "CFG  entrypoint file exists on disk",
}


def main():
    print(bold("\nEdge Function Config Validator"))
    print("=" * 55)

    issues    = run_checks()
    failed    = {i["check"] for i in issues}
    n_pass    = 0
    n_fail    = 0

    for name in CHECK_NAMES:
        matching = [i for i in issues if i["check"] == name]
        if not matching:
            print(f"  {green('PASS')}  {CHECK_LABELS[name]}")
            n_pass += 1
        else:
            for issue in matching:
                fn_tag = f" [{issue['function']}]" if "function" in issue else ""
                print(f"  {red('FAIL')}  {CHECK_LABELS[name]}{fn_tag}")
                print(f"         {issue['reason'][:90]}")
                n_fail += 1

    if n_fail == 0:
        print(f"{green(chr(10) + '  All checks passed.')}")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_fail} FAIL\033[0m")

    report = {
        "validator": "edge-config",
        "passed":    n_pass,
        "failed":    n_fail,
        "issues":    issues,
    }
    with open("edge_config_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
