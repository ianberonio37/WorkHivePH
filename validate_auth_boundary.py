"""
Auth Boundary Coverage -- WorkHive Platform
=============================================
Catches the auth-skip regression class: a page or edge function that
performs a mutating DB write WITHOUT first checking the worker is
authenticated. After the Supabase Auth migration (project memory
`project_supabase_auth_migration`), every mutating endpoint should
either:

  * Use Supabase Auth-gated identity (`_authUid` / `auth.uid()`)
  * OR explicitly scope by worker_name + hive_id (legacy paths)

Without one of these, the write either lands as anonymous (no
attribution) or relies entirely on RLS for protection -- which fails
silently if a future refactor drops the policy.

Layer 1 -- HTML page mutates without auth identity                       [WARN]
  Any page that calls `db.from(X).insert/update/delete/upsert(...)`
  but has no `_authUid` / `auth.getUser` / `_userId` / `WORKER_NAME &&`
  identity guard anywhere in the file.

Layer 2 -- Edge function mutates without auth check                      [WARN]
  Any edge fn that writes (via createClient + insert/update/delete)
  without calling `auth.getUser()` OR receiving `auth_uid` / `worker_name`
  in the request body AND validating it.

Layer 3 -- Per-page identity-source distribution (informational)         [INFO]
  Per-page count: `_authUid` / `auth.getUser` / `WORKER_NAME` /
  `_userId` references. Shows which pages have adopted the modern
  auth pattern.

Layer 4 -- Tables with anonymous-default writes (informational)          [INFO]
  Tables whose schema declares `auth_uid` column but consumer code
  inserts without setting `auth_uid:` in the payload -- writes land
  as NULL even though the column exists for scoping.

Skills consulted: security (auth boundary, no-anonymous-write rule),
multitenant-engineer (hive isolation requires identity attribution),
data-engineer (DB-confirm-before-localStorage-write pattern depends
on a known identity to scope to).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR = os.path.join("supabase", "functions")
MIGRATIONS_DIR = os.path.join("supabase", "migrations")
EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# Per-path exemptions. Each entry needs a one-line justification.
AUTH_BOUNDARY_OK_PAGES: dict[str, str] = {
    "platform-health.html":  "read-only dashboard; no mutating writes",
    "audit-log.html":         "read-only audit viewer",
    "architecture.html":      "RETIRED 2026-05-13 — archival doc, no public surface",
    "drawing-standards.html": "static doc page",
    # Anonymous lead-capture flow is intentional
    "index.html":             "lead capture + signup land here; auth check happens after signup",
    # Retired page excluded from nav (per memory project_retired_pages)
    "parts-tracker.html":     "RETIRED -- excluded from nav-hub; preserved for historical lookups only",
}
AUTH_BOUNDARY_OK_FNS: dict[str, str] = {
    "_shared":                "shared lib, not an endpoint",
    "marketplace-webhook":    "Stripe server-to-server webhook; auth via Stripe signature, not JWT",
    "cmms-webhook-receiver":  "CMMS webhook; auth via shared secret header",
    "voice-transcribe":       "Whisper proxy; uses anon key + rate limit only",
    "send-report-email":      "scheduled send via service role; no user JWT",
    "trigger-ml-retrain":     "cron-driven; no user JWT",
    "scheduled-agents":       "cron-driven; uses service role",
    "failure-signature-scan": "cron-driven daily",
    "batch-risk-scoring":     "cron-driven; service role",
    "benchmark-compute":      "cron-driven; service role",
    "intelligence-report":    "cron-driven scheduled report",
    "intelligence-api":       "public read API; rate-limited",
    "embed-entry":            "internal embedding pipeline; service role",
    "semantic-search":        "public RAG query; rate-limited read",
    "ai-orchestrator":        "deprecated; superseded by ai-gateway",
}

# Patterns that signal mutating DB writes.
MUTATING_HTML_RE = re.compile(
    r"""\bdb\.from\s*\(\s*['"`]\w+['"`]\s*\)
        (?:\s*\.\s*\w+\s*\([^)]*\))*?
        \s*\.\s*(?P<verb>insert|update|upsert|delete)\s*\(""",
    re.VERBOSE,
)
MUTATING_TS_RE = MUTATING_HTML_RE   # same shape in TS

# Identity-guard signals.
IDENTITY_RES = [
    re.compile(r"\b_authUid\b"),
    re.compile(r"\bauth\.getUser\s*\("),
    re.compile(r"\bauth\.getSession\s*\("),
    re.compile(r"\b_userId\b"),
    re.compile(r"\bWORKER_NAME\b"),
    re.compile(r"\bauth_uid\b"),       # body field with explicit auth_uid
]


def list_pages() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    return out


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _has_identity_signal(src: str) -> bool:
    return any(rx.search(src) for rx in IDENTITY_RES)


def _count_mutating_writes(src: str) -> int:
    return len(MUTATING_HTML_RE.findall(src))


# -- Layer 1: HTML page mutates without identity guard ---------------------

def check_html_pages(pages: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in pages:
        if path in AUTH_BOUNDARY_OK_PAGES:
            continue
        src = _strip_comments(read_file(path) or "")
        n_writes = _count_mutating_writes(src)
        if n_writes == 0:
            continue
        if _has_identity_signal(src):
            continue
        report.append({"path": path, "n_writes": n_writes})
        issues.append({
            "check": "html_no_identity", "skip": True,
            "reason": (
                f"{path}: contains {n_writes} mutating DB write(s) "
                f"(insert/update/delete/upsert) but no identity guard "
                f"(_authUid / auth.getUser / _userId / WORKER_NAME / "
                f"auth_uid). Either wire an identity guard or list the "
                f"path in AUTH_BOUNDARY_OK_PAGES with a justification."
            ),
        })
    return issues, report


# -- Layer 2: Edge fn mutates without auth check ---------------------------

def check_edge_fns(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in AUTH_BOUNDARY_OK_FNS:
            continue
        src = _strip_comments(read_file(path) or "")
        n_writes = _count_mutating_writes(src)
        if n_writes == 0:
            continue
        # Edge fns have two valid auth shapes:
        #   * call auth.getUser() / auth.getSession() to verify JWT
        #   * receive worker_name / hive_id from body and use those to scope
        has_jwt_check = bool(
            re.search(r"auth\.getUser\s*\(|auth\.getSession\s*\(", src),
        )
        has_body_identity = bool(
            re.search(r"\b(?:worker_name|hive_id|auth_uid)\b", src),
        )
        if has_jwt_check or has_body_identity:
            continue
        report.append({"fn": name, "n_writes": n_writes})
        issues.append({
            "check": "edge_no_auth", "skip": True,
            "reason": (
                f"{name}/index.ts: contains {n_writes} mutating DB "
                f"write(s) but neither calls auth.getUser/getSession "
                f"NOR reads worker_name/hive_id/auth_uid from the body. "
                f"Either wire a JWT check or accept identity in the body, "
                f"or list '{name}' in AUTH_BOUNDARY_OK_FNS with a reason."
            ),
        })
    return issues, report


# -- Layer 3: Per-page identity-source distribution (informational) -------

def check_identity_distribution(pages: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in pages:
        src = _strip_comments(read_file(path) or "")
        counts = {
            "authUid":         len(re.findall(r"\b_authUid\b", src)),
            "auth.getUser":    len(re.findall(r"\bauth\.getUser\s*\(", src)),
            "auth.getSession": len(re.findall(r"\bauth\.getSession\s*\(", src)),
            "_userId":         len(re.findall(r"\b_userId\b", src)),
            "WORKER_NAME":     len(re.findall(r"\bWORKER_NAME\b", src)),
        }
        if sum(counts.values()) == 0:
            continue
        rows.append({
            "path": path, "counts": counts,
            "total": sum(counts.values()),
        })
    rows.sort(key=lambda r: -r["total"])
    return [], rows


# -- Layer 4: Anonymous writes to auth_uid-bearing tables ---------------

def check_anonymous_writes(
    pages: list[str],
) -> tuple[list[dict], list[dict]]:
    """Find consumer code that inserts into a table with `auth_uid` column
    but doesn't set `auth_uid:` in the payload — leads to NULL auth_uid
    rows that pose ownership ambiguity later."""
    # Build set of tables with auth_uid column.
    auth_uid_tables: set[str] = set()
    create_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?
            "?(?P<name>\w+)"?\s*\(
            (?P<body>[\s\S]*?)\n\s*\);""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in create_re.finditer(sql):
            body = m.group("body").lower()
            if "auth_uid" in body:
                auth_uid_tables.add(m.group("name").lower())
        for m in re.finditer(
            r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.)?
                "?(?P<name>\w+)"?\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+
                "?auth_uid"?""",
            sql, re.IGNORECASE | re.VERBOSE,
        ):
            auth_uid_tables.add(m.group("name").lower())

    # Scan inserts.
    rows: list[dict] = []
    insert_re = re.compile(
        r"""\bdb\.from\s*\(\s*['"`](?P<table>\w+)['"`]\s*\)
            (?:\s*\.\s*\w+\s*\([^)]*\))*?
            \s*\.\s*(?:insert|upsert)\s*\(\s*(?:\[\s*)?\{(?P<body>[^{}]*)\}""",
        re.DOTALL | re.VERBOSE,
    )
    for path in pages:
        src = _strip_comments(read_file(path) or "")
        for m in insert_re.finditer(src):
            tbl = m.group("table").lower()
            if tbl not in auth_uid_tables:
                continue
            if "auth_uid" in m.group("body"):
                continue
            line = src.count("\n", 0, m.start()) + 1
            rows.append({
                "path":  path,
                "line":  line,
                "table": tbl,
            })
    return [], rows


# -- Runner --------------------------------------------------------------

CHECK_NAMES = [
    "html_no_identity",
    "edge_no_auth",
    "identity_distribution",
    "anonymous_writes",
]
CHECK_LABELS = {
    "html_no_identity":      "L1  Every HTML page with writes has an identity guard         [WARN]",
    "edge_no_auth":          "L2  Every mutating edge fn checks JWT or accepts body identity [WARN]",
    "identity_distribution": "L3  Per-page identity-source distribution (informational)     [INFO]",
    "anonymous_writes":      "L4  Inserts to auth_uid tables set auth_uid (informational)   [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAuth Boundary Coverage (4-layer)"))
    print("=" * 60)

    pages = list_pages()
    fns   = list_edge_fns()
    print(f"  {len(pages)} HTML page(s), {len(fns)} edge fn(s) scanned "
          f"(OK_PAGES={len(AUTH_BOUNDARY_OK_PAGES)}, "
          f"OK_FNS={len(AUTH_BOUNDARY_OK_FNS)}).\n")

    l1_issues, l1_report = check_html_pages(pages)
    l2_issues, l2_report = check_edge_fns(fns)
    l3_issues, l3_report = check_identity_distribution(pages)
    l4_issues, l4_report = check_anonymous_writes(pages)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('TOP IDENTITY-USING PAGES (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            top_kind = max(r["counts"].items(), key=lambda kv: kv[1])
            print(f"  {r['path']:<32}  total={r['total']:<3} top={top_kind[0]}({top_kind[1]})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":             "auth_boundary",
        "total_checks":          total,
        "passed":                n_pass,
        "warned":                n_warn,
        "failed":                n_fail,
        "n_pages":               len(pages),
        "n_fns":                 len(fns),
        "html_no_identity":      l1_report,
        "edge_no_auth":          l2_report,
        "identity_distribution": l3_report,
        "anonymous_writes":      l4_report,
        "issues":                [i for i in all_issues if not i.get("skip")],
        "warnings":              [i for i in all_issues if i.get("skip")],
    }
    with open("auth_boundary_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
