"""
RPC Argument Consistency Validator (L0, ratcheted).
====================================================
Every `db.rpc('fn_name', { p_x: value, ... })` call must:
  1. Reference a real RPC function (in canonical_registry).
  2. Pass only argument names that exist in the function's signature.

Caught class: page calls `db.rpc('compute_hive_readiness', { p_hive: ... })`
but the actual arg is `p_hive_id`. Postgres errors out — page silently
shows stale data because the catch swallows the error.

Output: rpc_argument_consistency_report.json. Exit 1 on regression.
Allow with `// rpc-arg-allow: <reason>` near the call.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "rpc_argument_consistency_report.json"
BASELINE_PATH = ROOT / "rpc_argument_consistency_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

# .rpc('NAME', { p_X: ..., p_Y: ... })
RPC_RE = re.compile(
    r"""\.rpc\(\s*['"`](?P<name>[a-z_][\w]*)['"`]\s*,\s*\{(?P<args>[^}]{0,400})\}""",
    re.DOTALL,
)
ARG_KEY_RE = re.compile(r"""\b(?P<key>[a-z_][\w]*)\s*:""")
ALLOW_RE = re.compile(r"rpc-arg-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _parse_rpc_args(reg_args: str) -> set[str]:
    """Parse 'p_hive_id uuid, p_kind text' → {'p_hive_id', 'p_kind'}."""
    out: set[str] = set()
    if not reg_args:
        return out
    for part in reg_args.split(","):
        part = part.strip()
        if not part:
            continue
        # Take first identifier
        m = re.match(r"^(\w+)\b", part)
        if m:
            out.add(m.group(1).lower())
    return out


# Sentinel binding: name the L2 test `test('rpc_argument_consistency: ...')` for coverage credit.
CHECK_NAMES = ["rpc_argument_consistency"]


def main() -> int:
    reg_path = ROOT / "canonical_registry.json"
    if not reg_path.exists():
        print("FAIL: canonical_registry.json missing")
        return 2
    reg = json.loads(reg_path.read_text(encoding="utf-8"))

    rpc_args: dict[str, set[str]] = {}
    for name, meta in reg.get("rpcs", {}).items():
        rpc_args[name.lower()] = _parse_rpc_args(meta.get("args", "") or "")

    per_page = []
    total_drift = 0
    total_calls = 0
    known_rpcs = set(rpc_args.keys())

    files = [(name, ROOT / name) for name in PAGES]
    for p in sorted(ROOT.glob("*.js")):
        if p.name == "sw.js": continue
        files.append((p.name, p))
    # Edge fns too — they often invoke RPCs
    edge_dir = ROOT / "supabase" / "functions"
    if edge_dir.exists():
        for ts in sorted(edge_dir.rglob("*.ts")):
            files.append((str(ts.relative_to(ROOT)), ts))

    seen: set = set()
    for name, path in files:
        if not path.exists(): continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        issues = []
        for m in RPC_RE.finditer(body):
            rpc_name = m.group("name").lower()
            total_calls += 1
            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win): continue

            if rpc_name not in known_rpcs:
                key = (name, rpc_name, "missing_rpc", "")
                if key in seen: continue
                seen.add(key)
                issues.append({"rpc": rpc_name, "issue": "missing_rpc"})
                continue

            args_text = m.group("args") or ""
            arg_keys = {km.group("key").lower() for km in ARG_KEY_RE.finditer(args_text)}
            expected = rpc_args[rpc_name]
            if not expected:
                # Couldn't parse signature; skip arg check
                continue
            for k in arg_keys:
                if k not in expected:
                    key = (name, rpc_name, "bad_arg", k)
                    if key in seen: continue
                    seen.add(key)
                    issues.append({"rpc": rpc_name, "issue": "bad_arg", "arg": k,
                                   "expected": sorted(expected)})
        per_page.append({"file": name, "issues": issues})
        total_drift += len(issues)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_drift < baseline:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(per_page), "total_calls": total_calls,
                    "total_drift": total_drift, "baseline": baseline,
                    "rpcs_known": len(known_rpcs)},
        "per_file": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nRPC Argument Consistency Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(per_page)}")
    print(f"  rpcs known:       {len(known_rpcs)}")
    print(f"  total calls:      {total_calls}")
    print(f"  drift:            {total_drift}  (baseline: {baseline})")
    if total_drift == 0:
        print("\n  PASS — every db.rpc() name + arg keys exist.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["issues"]: continue
        print(f"  {entry['file']}")
        for i in entry["issues"]:
            if i["issue"] == "missing_rpc":
                print(f"    → rpc('{i['rpc']}')  — no such RPC")
            else:
                print(f"    → rpc('{i['rpc']}', {{ {i['arg']}: ... }})  — expected: {', '.join(i['expected'][:4])}")
            shown += 1
            if shown >= 20:
                print("    ... (more in report)")
                break
        if shown >= 20: break
    return 1 if total_drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
