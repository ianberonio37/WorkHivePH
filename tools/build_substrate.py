#!/usr/bin/env python3
"""
build_substrate.py — Platform Knowledge Substrate generator (PKS Phase 1).
======================================================================
PLATFORM_KNOWLEDGE_SUBSTRATE_ROADMAP.md L1. Chunk the platform ONCE into durable, semantic,
metadata-prefixed .md files that Memento retrieves — so a task pulls the relevant slice instead of a
fan-out re-deriving everything every run. Each chunk carries a `source_sha` freshness anchor that
`validate_substrate_freshness.py` re-checks every gate run (L2 anti-regression).

Chunk types (this phase):
  table-rls   — per tenant table (has hive_id or auth_uid): RLS on/off, every policy (cmd/roles/
                qual/with_check), guard triggers, + a RULE-BASED verdict (the exact structural hunt
                done by hand 2026-07-13: with_check-null INSERT, USING(true) SELECT, auth_uid tables
                with no self-pin, RLS-off). This is the bug-hunt's P5 memory.
  rpc         — per SECURITY DEFINER function taking p_hive_id: membership-guard present? EXECUTE
                grants (service_role-only vs authenticated). The DEFINER cross-hive-leak class memory.

Source of truth is the LIVE local DB (docker psql) — RLS/grants live in the DB, not one file — so the
source_sha hashes the canonical introspected facts; a migration that changes a policy changes the hash
=> the freshness gate flips the chunk STALE. Reseeding data does NOT change policies, so the anchor is
reseed-stable.

Usage:
  python tools/build_substrate.py                # build all chunk types
  python tools/build_substrate.py --type table-rls
  python tools/build_substrate.py --check        # print what WOULD change, write nothing (dry run)
"""
from __future__ import annotations
import argparse, hashlib, io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SUB = ROOT / "substrate"
DB = "supabase_db_workhive"
# The project's auto-memory dir (Memento topic files). Same literal as tools/memory_cache.py MEM_DIR.
MEM_DIR = (Path.home() / ".claude" / "projects" /
           "c--Users-ILBeronio-Desktop-Industry-4-0-AI-Maintenance-Engineer-Self-learning-Road-Map-Build---Sell-with-Claude-Code-Website-simple-1st" / "memory")


def psql(sql: str):
    """Read-only introspection via docker psql. Returns list of pipe-split rows (or None if DB down)."""
    try:
        p = subprocess.run(
            ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-X", "-A", "-t", "-F", "\x1f", "-c", sql],
            capture_output=True, text=True, timeout=60,
        )
        if p.returncode != 0:
            return None
        return [ln.split("\x1f") for ln in p.stdout.splitlines() if ln.strip()]
    except Exception:
        return None


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def frontmatter(name, ctype, source, source_sha, extra=""):
    return (f"---\nname: {name}\ntype: {ctype}\nsource: {source}\nsource_sha: {source_sha}\n"
            f"last_verified: 2026-07-13\nsupersedes: null\n{extra}---\n")


# ─── table-rls chunker ─────────────────────────────────────────────────────────
def build_table_rls(check_only: bool):
    # tenant tables = have a hive_id OR auth_uid column
    cols = psql("SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND column_name IN ('hive_id','auth_uid') ORDER BY table_name;")
    if cols is None:
        print("  SKIP table-rls: docker DB unavailable")
        return 0
    has_hive, has_uid = {}, {}
    for t, c in cols:
        (has_hive if c == "hive_id" else has_uid).setdefault(t, True)

    # relrowsecurity renders as 't'/'f' under psql -A -t (no ::text cast — that yields 'true'/'false').
    # This dict is BASE TABLES ONLY (relkind='r'), so intersecting `tables` with it drops VIEWS
    # (information_schema.columns includes views, which have no RLS and would false-flag as RLS-DISABLED).
    rls = {r[0]: (r[1] == "t") for r in (psql(
        "SELECT c.relname, c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind='r';") or [])}
    tables = sorted((set(has_hive) | set(has_uid)) & set(rls))
    # ALL columns per table (name + NOT-NULL marker) — write-probing needs the schema, and re-querying
    # it live defeats the substrate (gap hit twice 2026-07-13: pm_assets, project_progress_logs).
    allcols = {}
    for r in (psql("SELECT table_name, column_name, is_nullable FROM information_schema.columns "
                   "WHERE table_schema='public' ORDER BY table_name, ordinal_position;") or []):
        if len(r) < 3:
            continue
        allcols.setdefault(r[0], []).append(r[1] + ("" if r[2] == "YES" else "*"))
    pols = {}
    for r in (psql("SELECT tablename, policyname, cmd, array_to_string(roles,','), "
                   "regexp_replace(coalesce(qual,''), '\\s+', ' ', 'g'), "
                   "regexp_replace(coalesce(with_check,''), '\\s+', ' ', 'g') FROM pg_policies WHERE schemaname='public';") or []):
        if len(r) < 6:  # defensive: any row that still under-splits gets padded, never crashes the build
            r = r + [""] * (6 - len(r))
        pols.setdefault(r[0], []).append({"name": r[1], "cmd": r[2], "roles": r[3], "using": r[4].strip(), "check": r[5].strip()})
    trigs = {}
    for r in (psql("SELECT c.relname, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                   "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal "
                   "AND (t.tgname LIKE 'trg_bind%' OR t.tgname LIKE '%guard%' OR t.tgname LIKE '%cap%' OR t.tgname LIKE 'bind%');") or []):
        trigs.setdefault(r[0], []).append(r[1])

    written = 0
    for t in tables:
        facts = {
            "rls_enabled": rls.get(t, False),
            "has_hive_id": t in has_hive, "has_auth_uid": t in has_uid,
            "policies": sorted(pols.get(t, []), key=lambda p: (p["cmd"], p["name"])),
            "guard_triggers": sorted(trigs.get(t, [])),
            "columns": allcols.get(t, []),  # in the sha so a schema change re-chunks
        }
        s = sha(facts)
        # ── rule-based verdicts (the 2026-07-13 structural hunt, encoded) ──
        flags = []
        if not facts["rls_enabled"]:
            flags.append("RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).")
        for p in facts["policies"]:
            if p["cmd"] in ("INSERT",) and not p["check"]:
                flags.append(f"{p['name']} (INSERT) has NO with_check — INSERT has no USING-fallback = WRITE-HOLE.")
            if p["cmd"] in ("SELECT", "ALL") and (p["using"] == "true" or not p["using"]):
                # An open read by the restricted grafana_reader monitoring role (a dedicated DB role
                # granted the read path separately in infra/mcp/grafana/grafana_reader.sql, NEVER to
                # anon/authenticated app users) is intentional platform observability — not an
                # app-user cross-tenant hole. Flag ONLY when an APP-FACING role (anon / authenticated
                # / public) can use the open policy; infra-only roles (grafana_reader, service_role)
                # do not count against D2 multitenant-isolation adoption.
                _roles_s = str(p.get("roles", ""))
                if any(r in _roles_s for r in ("anon", "authenticated", "public")):
                    flags.append(f"{p['name']} ({p['cmd']}) USING is open ('{p['using'] or 'null'}') — potential cross-tenant read/stream.")
        if facts["has_auth_uid"]:
            # Only a CLIENT-WRITABLE policy can be forged. A table with only a SELECT policy (e.g.
            # community_xp) denies all client writes (RLS on + no write policy) and is written solely by
            # a service-role RPC — NOT an attribution suspect. (Exercise 2026-07-13 caught this FP.)
            # A write policy whose governing expr is literally 'false' is a DENY-ALL service-role lock
            # (agent_episodic_memory / mfa_enrollments / gateway_audit_log etc.) — not client-writable.
            def _client_writable(p):
                expr = (p["check"] if p["cmd"] == "INSERT" else (p["check"] or p["using"])).strip().lower()
                return expr != "false"
            write_pols = [p for p in facts["policies"] if p["cmd"] in ("INSERT", "UPDATE", "ALL") and _client_writable(p)]
            pins = any("auth_uid" in (p["using"] + p["check"]) and "auth.uid()" in (p["using"] + p["check"]) for p in write_pols)
            binds = any(g.startswith(("trg_bind", "bind")) for g in facts["guard_triggers"])
            anon_write = any("anon" in p["roles"] for p in write_pols)  # anon-INSERT tables have no auth_uid to pin (by design)
            if write_pols and not pins and not binds and not anon_write:
                flags.append("has auth_uid + a CLIENT-WRITABLE policy that does NOT self-pin auth_uid AND no bind_* trigger — ATTRIBUTION-FORGERY suspect.")
        # VALUE-INTEGRITY (2026-07-13, marketplace listing trust-forge): a client-writable TRUST/
        # REPUTATION/BALANCE column is self-forgeable unless column-guarded OR the display sources from a
        # canonical table. Attribution being correct (SCOPED) does NOT imply value integrity. Triage flag.
        _TRUST = re.compile(r"(verified|kyb|cert|rating|_sales|tier|xp_total|current_level|\blevel\b|exam_score|badge_key|grade|points|balance|reputation)", re.I)
        _cw = any(p["cmd"] in ("INSERT", "UPDATE", "ALL") and
                  (p["check"] if p["cmd"] == "INSERT" else (p["check"] or p["using"])).strip().lower() != "false"
                  for p in facts["policies"])
        _trust_cols = [c.rstrip("*") for c in facts["columns"] if _TRUST.search(c)]
        _guarded = any("guard" in g or "trust" in g for g in facts["guard_triggers"])
        if _cw and _trust_cols and not _guarded:
            flags.append(f"client-writable TRUST/VALUE column(s) {_trust_cols[:4]} + no guard trigger — VALUE-INTEGRITY suspect (self-forgeable unless a BEFORE-trigger guards it or the display sources from a canonical table).")
        verdict = "FLAGS: " + " ".join(flags) if flags else "SCOPED — no structural hole detected by rules (verify live before trusting for a fix)."

        # ── chunk body (metadata-prefixed, opinionated, retrieval-carries-context) ──
        lines = [frontmatter(f"table-rls-{t}", "table-rls", f"db:pg_policies+pg_trigger:{t}", s)]
        lines.append(f"## table-rls · `{t}` — RLS posture (tenant table)\n")
        lines.append(f"RLS enabled: **{facts['rls_enabled']}** · has hive_id: {facts['has_hive_id']} · has auth_uid: {facts['has_auth_uid']}\n")
        _cols = allcols.get(t, [])
        if _cols:
            lines.append(f"Columns (*=NOT NULL): {', '.join(_cols[:50])}\n")
        if facts["policies"]:
            lines.append("Policies:")
            for p in facts["policies"]:
                lines.append(f"- `{p['name']}` [{p['cmd']} · roles={p['roles']}] USING=`{(p['using'] or '∅')[:120]}` CHECK=`{(p['check'] or '∅')[:120]}`")
        else:
            lines.append("Policies: (none)")
        if facts["guard_triggers"]:
            lines.append(f"\nGuard triggers: {', '.join('`'+g+'`' for g in facts['guard_triggers'])}")
        lines.append(f"\n**Verdict:** {verdict}")
        lines.append("\nLinks: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]")
        body = "\n".join(lines) + "\n"

        dest = SUB / "table-rls" / f"{t}.md"
        if check_only:
            old = dest.read_text(encoding="utf-8") if dest.exists() else ""
            old_sha = ""
            for ln in old.splitlines():
                if ln.startswith("source_sha:"):
                    old_sha = ln.split(":", 1)[1].strip()
            if old_sha != s:
                print(f"  WOULD update table-rls/{t}.md (sha {old_sha or '∅'} -> {s})")
        else:
            dest.write_text(body, encoding="utf-8")
            written += 1
    if not check_only:
        print(f"  table-rls: wrote {written} chunks -> substrate/table-rls/")
    return written


# ─── rpc chunker (DEFINER hive functions) ──────────────────────────────────────
def build_rpc(check_only: bool):
    rows = psql(
        "SELECT p.proname, pg_get_function_arguments(p.oid), coalesce(array_to_string(p.proacl,','),'(default:public)'), "
        "CASE WHEN pg_get_functiondef(p.oid) ILIKE '%user_can_access_hive%' OR pg_get_functiondef(p.oid) ILIKE '%user_hive_ids%' "
        "  OR pg_get_functiondef(p.oid) ILIKE '%user_supervisor_hive_ids%' OR pg_get_functiondef(p.oid) ~* 'hive_members[^;]*auth.uid' "
        "  OR pg_get_functiondef(p.oid) ~* 'auth.uid[^;]*=[^;]*worker_id' THEN 'GUARDED' ELSE 'NO-GUARD' END "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.prosecdef AND pg_get_function_arguments(p.oid) ILIKE '%hive%' ORDER BY p.proname;")
    if rows is None:
        print("  SKIP rpc: docker DB unavailable")
        return 0
    written = 0
    for name, args, acl, guard in rows:
        exec_scope = "service_role/postgres-only" if ("authenticated" not in acl and "public" not in acl.lower()) else "authenticated-callable"
        facts = {"args": args, "acl": acl, "guard": guard}
        s = sha(facts)
        flag = ""
        if guard == "NO-GUARD" and exec_scope == "authenticated-callable":
            flag = "\n**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify."
        elif guard == "NO-GUARD":
            flag = "\n**Note:** no in-body membership guard, but EXECUTE is service_role-only — exposure only if an edge fn invokes it with an unchecked hive_id (verify the caller)."
        body = (frontmatter(f"rpc-{name}", "rpc", f"db:pg_proc:{name}", s)
                + f"## rpc · `{name}({args[:100]})` — SECURITY DEFINER, hive-scoped\n\n"
                + f"Membership guard in body: **{guard}** · EXECUTE: **{exec_scope}** (`{acl[:80]}`)\n{flag}\n"
                + "\nLinks: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]\n")
        dest = SUB / "rpc" / f"{name}.md"
        if check_only:
            old = dest.read_text(encoding="utf-8") if dest.exists() else ""
            old_sha = next((ln.split(":",1)[1].strip() for ln in old.splitlines() if ln.startswith("source_sha:")), "")
            if old_sha != s:
                print(f"  WOULD update rpc/{name}.md (sha {old_sha or '∅'} -> {s})")
        else:
            dest.write_text(body, encoding="utf-8")
            written += 1
    if not check_only:
        print(f"  rpc: wrote {written} chunks -> substrate/rpc/")
    return written


import re

def _fhash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]

def _write_chunk(dest: Path, name, ctype, source, src_sha, body_md, check_only):
    """Write a file-anchored chunk (source_sha = file content hash). Returns 1 if written/1 if would-change."""
    content = frontmatter(name, ctype, source, src_sha) + body_md
    if check_only:
        old = dest.read_text(encoding="utf-8") if dest.exists() else ""
        old_sha = next((ln.split(":", 1)[1].strip() for ln in old.splitlines() if ln.startswith("source_sha:")), "")
        if old_sha != src_sha:
            print(f"  WOULD update {dest.parent.name}/{dest.name} (sha {old_sha or '∅'} -> {src_sha})")
            return 1
        return 0
    dest.write_text(content, encoding="utf-8")
    return 1

# ─── page chunker (deterministic parse — the big HTML files NEVER enter the agent's context) ──
_RE_WRITE = re.compile(r"\.from\(['\"](\w+)['\"]\)[\s\S]{0,80}?\.(insert|update|upsert|delete)\b")
_RE_RPC = re.compile(r"\.rpc\(['\"]([\w]+)['\"]")
_RE_INVOKE = re.compile(r"functions\.invoke\(['\"]([\w-]+)['\"]|/functions/v1/([\w-]+)")
_RE_READVIEW = re.compile(r"\.from\(['\"](v_\w+)['\"]\)")
_RE_FUNC = re.compile(r"(?:function\s+(\w+)\s*\(|(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)")
_RE_TITLE = re.compile(r"<title>([^<]{1,80})</title>", re.I)

def _page_list():
    skip = ("backup", "-test", "-v3", "-native", "-hive-test", ".min.")
    return sorted(p for p in ROOT.glob("*.html") if not any(s in p.name.lower() for s in skip))

def build_pages(check_only: bool, subdir="page", globber=None):
    files = globber() if globber else _page_list()
    (SUB / subdir).mkdir(parents=True, exist_ok=True)
    written = 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        writes = sorted({f"{t}.{op}" for t, op in _RE_WRITE.findall(text)})
        rpcs = sorted(set(_RE_RPC.findall(text)))
        invokes = sorted({a or b for a, b in _RE_INVOKE.findall(text)})
        views = sorted(set(_RE_READVIEW.findall(text)))
        funcs = sorted({a or b for a, b in _RE_FUNC.findall(text) if (a or b)})
        title = (_RE_TITLE.search(text) or [None, f.stem])[1]
        src_sha = _fhash(text)
        body = [f"## page · `{f.name}` — {title.strip()}\n",
                f"Size: {len(text)//1024}KB · {len(funcs)} top-level fns. (Retrieve THIS instead of reading the file.)\n"]
        body.append(f"**DB writes** ({len(writes)}): {', '.join('`'+w+'`' for w in writes) or '(none detected)'}")
        body.append(f"**RPC calls**: {', '.join('`'+r+'`' for r in rpcs) or '(none)'}")
        body.append(f"**Edge invokes**: {', '.join('`'+i+'`' for i in invokes) or '(none)'}")
        body.append(f"**Truth views read**: {', '.join('`'+v+'`' for v in views) or '(none)'}")
        body.append(f"\n**Functions**: {', '.join(funcs[:60])}" + (" …" if len(funcs) > 60 else ""))
        body.append("\nLinks: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]\n")
        written += _write_chunk(SUB / subdir / f"{f.stem}.md", f"{subdir}-{f.stem}", subdir,
                                f"file:{f.name}", src_sha, "\n".join(body), check_only)
    if not check_only:
        print(f"  {subdir}: wrote {written} chunks -> substrate/{subdir}/ ({len(files)} files parsed, none loaded into agent context)")
    return written

# ─── edge-function chunker ─────────────────────────────────────────────────────
def build_edge_fns(check_only: bool):
    fns_dir = ROOT / "supabase" / "functions"
    if not fns_dir.exists():
        print("  SKIP edge-fn: supabase/functions absent"); return 0
    (SUB / "edge-fn").mkdir(exist_ok=True)
    written = 0
    files = sorted(fns_dir.glob("*/index.ts"))
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        name = f.parent.name
        # Widened auth-idiom detection (the crude version false-flagged 80% of fns). Still a HEURISTIC:
        # the authoritative gate is config.toml verify_jwt + the caller passing a checked hive_id.
        gated = bool(re.search(r"hive_members|user_can_access|user_hive_ids|user_supervisor|checkSupervisor|"
                               r"getUser|verify_jwt|requireAuth|requireMember|assertMember|auth\.uid|"
                               r"\.eq\(['\"]auth_uid|hive_status|Authorization|Bearer|401|403|Unauthorized|forbidden",
                               text, re.I))
        service_role = bool(re.search(r"SERVICE_ROLE|service_role|scheduled|cron|batch|retrain|orchestrat", text, re.I))
        tables = sorted(set(re.findall(r"\.from\(['\"](\w+)['\"]\)", text)))[:20]
        rpcs = sorted(set(_RE_RPC.findall(text)))
        if gated:
            status = "auth idiom detected in body (verify it gates the hive_id it uses)"
        elif service_role:
            status = "no per-user auth idiom; appears service-role/batch (by design) — confirm the CALLER checks membership"
        else:
            status = "no auth idiom detected in body — the real gate is config.toml verify_jwt + the caller; VERIFY before trusting"
        body = (f"## edge-fn · `{name}` (supabase/functions/{name})\n\n"
                f"Auth gate: **{status}**\n\nTables touched: {', '.join('`'+t+'`' for t in tables) or '(none)'}\n"
                f"RPCs called: {', '.join('`'+r+'`' for r in rpcs) or '(none)'}\n"
                "\nLinks: [[project_platform_knowledge_substrate]]\n")
        written += _write_chunk(SUB / "edge-fn" / f"{name}.md", f"edge-fn-{name}", "edge-fn",
                                f"file:supabase/functions/{name}/index.ts", _fhash(text), body, check_only)
    if not check_only:
        print(f"  edge-fn: wrote {written} chunks -> substrate/edge-fn/ ({len(files)} files)")
    return written

# ─── skill + doc chunkers (TOC + summary; the .md itself stays the deep source) ──
def _toc_chunk(f: Path, ctype: str, source: str, check_only: bool, dest_dir: Path):
    text = f.read_text(encoding="utf-8", errors="replace")
    headings = [ln.strip("# ").strip() for ln in text.splitlines() if re.match(r"#{1,3}\s", ln)][:40]
    desc = ""
    m = re.search(r"^description:\s*(.+)$", text, re.M)
    if m: desc = m.group(1).strip()[:200]
    elif len(text.splitlines()) > 1:
        desc = next((ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith(("#", "-", "```"))), "")[:200]
    name = f.parent.name if f.name in ("SKILL.md", "index.md") else f.stem
    body = (f"## {ctype} · {name}\n\n{desc}\n\n**Sections:** " + " · ".join(headings[:30]) +
            f"\n\n(Deep source: `{source}` — retrieve this TOC to know WHICH section to read.)\n")
    return _write_chunk(dest_dir / f"{name}.md", f"{ctype}-{name}", ctype, source, _fhash(text), body, check_only)

def build_skills(check_only: bool):
    sk = Path.home() / ".claude" / "skills"
    if not sk.exists():
        print("  SKIP skills: ~/.claude/skills absent"); return 0
    (SUB / "skill").mkdir(exist_ok=True)
    files = sorted(sk.glob("*/SKILL.md"))
    w = sum(_toc_chunk(f, "skill", f"skill:{f.parent.name}", check_only, SUB / "skill") for f in files)
    if not check_only: print(f"  skill: wrote {w} chunks -> substrate/skill/ ({len(files)} skills)")
    return w

def build_docs(check_only: bool):
    (SUB / "doc").mkdir(exist_ok=True)
    skip = {"MEMORY.md"}
    # Index DURABLE knowledge docs (roadmaps/guides/strategy), NOT regenerable artifacts — a generated
    # report changes every miner run and would drift the chunk constantly (noise). Skip generated names.
    GEN = re.compile(r"(_report|_baseline|_manifest|_candidates|_map|_provenance|_ladder|_scorecard|"
                     r"_audit_report|canonical_registry|canonical_anchor|display_|column_terminus|"
                     r"_terminus|_registry|_catalog|_results|content_substrate)", re.I)
    files = sorted(p for p in ROOT.glob("*.md")
                   if p.name not in skip and p.stat().st_size > 400 and not GEN.search(p.name))
    w = sum(_toc_chunk(f, "doc", f"file:{f.name}", check_only, SUB / "doc") for f in files)
    if not check_only: print(f"  doc: wrote {w} chunks -> substrate/doc/ ({len(files)} docs)")
    return w

_TRUSTCOL = re.compile(r"(verified|kyb|cert|_sales|rating|tier|xp_total|current_level|\blevel\b|"
                       r"exam_score|badge_key|grade|points|balance|reputation|author_name|worker_name|"
                       r"submitted_by|actor|owner_name)", re.I)

def build_views(check_only: bool):
    """v_* view definitions — what each EXPOSES + from which base tables + security_invoker on/off.
    The trust-forge / display-vs-truth-parity / cross-hive-read-leak brain (migs 001, 009): a view that
    exposes a trust/identity column sourced from a forgeable base column, or runs without security_invoker,
    is the suspect. Def whitespace-collapsed so each view is one deterministic row."""
    (SUB / "view").mkdir(exist_ok=True)
    rows = psql("SELECT c.relname, COALESCE(array_to_string(c.reloptions,','),''), "
                "regexp_replace(pg_get_viewdef(c.oid), '\\s+', ' ', 'g') "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='v' AND c.relname LIKE 'v\\_%' ORDER BY c.relname;")
    if rows is None:
        print("  SKIP view: DB down"); return 0
    written = 0
    for r in rows:
        if len(r) < 3:
            continue
        name, opts, vdef = r[0], r[1], r[2]
        srcs = sorted(set(re.findall(r"(?:FROM|JOIN)\s+(?:public\.)?(\w+)", vdef, re.I)) -
                      {"lateral", "unnest", "generate_series"})
        exposed = sorted(set(re.findall(r"AS\s+(\w+)", vdef, re.I)))
        trust = sorted(set(c for c in exposed if _TRUSTCOL.search(c)))
        si = "on" if "security_invoker=on" in opts.replace(" ", "").lower() or "security_invoker=true" in opts.replace(" ", "").lower() else "OFF ⚠"
        body = (f"## view · `{name}`\n\n"
                f"**security_invoker:** {si}  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)\n"
                f"**Source tables:** {', '.join('`'+s+'`' for s in srcs) or '(none parsed)'}\n"
                f"**Trust/identity cols exposed:** {', '.join('`'+c+'`' for c in trust) or '(none)'}  "
                "(each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)\n"
                f"\n**Definition (collapsed):** {vdef[:600]}" + (" …" if len(vdef) > 600 else "") +
                "\n\nLinks: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]\n")
        written += _write_chunk(SUB / "view" / f"{name}.md", f"view-{name}", "view",
                                f"db:pg_get_viewdef:{name}", _fhash(opts + "|" + vdef), body, check_only)
    if not check_only:
        print(f"  view: wrote {written} chunks -> substrate/view/ ({len(rows)} views introspected)")
    return written

def build_config(check_only: bool):
    """supabase/config.toml per-function verify_jwt + .env.example var names — the EDGE-AUTH truth the
    edge-fn chunks defer to ('the real gate is config.toml verify_jwt'). A public (verify_jwt=false)
    function that also lacks a body auth idiom is the gateway-bypass suspect."""
    (SUB / "config").mkdir(exist_ok=True)
    cfg = ROOT / "supabase" / "config.toml"
    if not cfg.exists():
        print("  SKIP config: supabase/config.toml absent"); return 0
    text = cfg.read_text(encoding="utf-8", errors="replace")
    # [functions.NAME] ... verify_jwt = true/false  (regex — tomllib would need py3.11 + exact structure)
    fns = {}
    cur = None
    for ln in text.splitlines():
        m = re.match(r"\s*\[functions\.([\w-]+)\]", ln)
        if m:
            cur = m.group(1); fns.setdefault(cur, "true (default)")
        elif cur:
            vj = re.match(r"\s*verify_jwt\s*=\s*(true|false)", ln)
            if vj:
                fns[cur] = vj.group(1)
    env_ex = ROOT / ".env.example"
    envs = sorted(set(re.findall(r"^([A-Z][A-Z0-9_]+)=", env_ex.read_text(encoding="utf-8", errors="replace"), re.M))) if env_ex.exists() else []
    public = sorted(k for k, v in fns.items() if v == "false")
    # BOLA surface: a PUBLIC fn that uses hive_id but has NO tenancy idiom is the real cross-hive suspect.
    # The tenancy idiom set is BROAD on purpose (2026-07-14 hunt: a narrow regex false-flagged 15 fns that
    # actually gate via inline membership / JWT self-scope / service-role / webhook — all verified safe).
    _TEN = re.compile(r"resolveTenancy|hive_members|user_can_access|user_hive_ids|user_supervisor|"
                      r"checkSupervisor|requireMember|assertMember|\.rpc\(['\"]user_|hive_status|"
                      r"\.eq\(['\"]auth_uid|resolveIdentity|SERVICE_ROLE|service_role|verifyWebhook|"
                      r"x-webhook|hmac|signature", re.I)
    fns_dir = ROOT / "supabase" / "functions"
    bola = []
    for p in public:
        src = fns_dir / p / "index.ts"
        if not src.exists():
            continue
        t = src.read_text(encoding="utf-8", errors="replace")
        if re.search(r"hive_id", t, re.I) and not _TEN.search(t):
            bola.append(p)
    body = (f"## config · edge-function auth (supabase/config.toml) + env vars\n\n"
            f"**BOLA surface — PUBLIC fns using hive_id with NO tenancy idiom ({len(bola)})** "
            "(the real cross-hive suspects; verified 0 on 2026-07-14): "
            f"{', '.join('`'+b+'`' for b in bola) or '**(none — every public hive_id fn is tenancy-gated)**'}\n\n"
            f"**PUBLIC functions (verify_jwt=false — MUST self-auth in body or via the caller):** "
            f"{', '.join('`'+p+'`' for p in public) or '(none)'}\n\n"
            f"**All functions ({len(fns)}):** " + " · ".join(f"{k}={v}" for k, v in sorted(fns.items())) +
            f"\n\n**Env vars declared in .env.example ({len(envs)}):** {', '.join('`'+e+'`' for e in envs)}\n"
            "\nLinks: [[reference_ai_companion_layer_arc_keystones]] [[project_platform_knowledge_substrate]]\n")
    fp = sha([sorted(fns.items()), envs])
    w = _write_chunk(SUB / "config" / "_edge_auth.md", "config-edge-auth", "config",
                     "file:supabase/config.toml+.env.example", fp, body, check_only)
    if not check_only:
        print(f"  config: wrote {w} chunk -> substrate/config/_edge_auth.md ({len(fns)} fns, {len(public)} public, {len(envs)} envs)")
    return w

def build_migrations(check_only: bool):
    """Migration catalog — per mig, the objects it CHANGED (policies/functions/triggers/tables). The
    'has this been fixed / what did mig N do' brain; append-only history, so one searchable catalog chunk."""
    (SUB / "migration").mkdir(exist_ok=True)
    mig_dir = ROOT / "supabase" / "migrations"
    if not mig_dir.exists():
        print("  SKIP migration: dir absent"); return 0
    migs = sorted(mig_dir.glob("*.sql"))
    lines, fp_parts = [], []
    for m in migs:
        t = m.read_text(encoding="utf-8", errors="replace")
        pol = sorted(set(re.findall(r"(?:CREATE|ALTER|DROP)\s+POLICY\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?\"?([\w]+)", t, re.I)))
        fns = sorted(set(re.findall(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?([\w]+)", t, re.I)))
        trg = sorted(set(re.findall(r"CREATE\s+TRIGGER\s+([\w]+)", t, re.I)))
        tbls = sorted(set(re.findall(r"(?:ALTER|CREATE)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:public\.)?([\w]+)", t, re.I)))
        summ = []
        if pol: summ.append(f"policies:{','.join(pol[:6])}")
        if fns: summ.append(f"fns:{','.join(fns[:6])}")
        if trg: summ.append(f"triggers:{','.join(trg[:6])}")
        if tbls: summ.append(f"tables:{','.join(tbls[:6])}")
        lines.append(f"- `{m.stem}` — " + (" · ".join(summ) or "(misc DDL/DML)"))
        fp_parts.append(m.stem + _fhash(t))
    body = (f"## migration · catalog ({len(migs)} migrations)\n\n"
            "Append-only DDL history. Search here for 'has this table/policy been fixed' before re-diagnosing.\n\n"
            + "\n".join(lines[-200:]) +
            ("\n\n(showing last 200)" if len(lines) > 200 else "") +
            "\n\nLinks: [[project_platform_knowledge_substrate]]\n")
    w = _write_chunk(SUB / "migration" / "_catalog.md", "migration-catalog", "migration",
                     f"dir:supabase/migrations:{len(migs)}", sha(fp_parts), body, check_only)
    if not check_only:
        print(f"  migration: wrote {w} catalog chunk -> substrate/migration/_catalog.md ({len(migs)} migs)")
    return w

def build_ops(check_only: bool):
    """cron.job (pg_cron) + realtime publication membership — the SILENTLY-DEAD classes: a cron that fails
    invisibly (retention 28x dead) and postgres_changes that's dead if the table isn't in the publication."""
    (SUB / "ops").mkdir(exist_ok=True)
    crons = psql("SELECT jobname, schedule, replace(left(command,80),chr(10),' ') FROM cron.job ORDER BY jobname;")
    pubs = psql("SELECT tablename FROM pg_publication_tables WHERE pubname='supabase_realtime' ORDER BY tablename;")
    if crons is None and pubs is None:
        print("  SKIP ops: DB down or cron/publication absent"); return 0
    cron_lines = [f"- `{r[0]}` @ `{r[1] if len(r) > 1 else '?'}` → {r[2] if len(r) > 2 else ''}"
                  for r in (crons or []) if r and len(r) >= 1 and r[0]]
    pub_tbls = sorted(r[0] for r in (pubs or []) if r and len(r) >= 1 and r[0])
    body = (f"## ops · cron jobs + realtime publication\n\n"
            f"**pg_cron jobs ({len(cron_lines)})** — a failing cron is SILENT; audit `cron.job_run_details` for failures:\n"
            + ("\n".join(cron_lines) or "(none)") +
            f"\n\n**Realtime publication `supabase_realtime` ({len(pub_tbls)} tables)** — a table NOT here has "
            f"DEAD postgres_changes subscriptions (no error, just no events):\n{', '.join('`'+t+'`' for t in pub_tbls) or '(none)'}\n"
            "\nLinks: [[reference_cron_silent_failure_retention]] [[reference_realtime_publication_and_singleton]]\n")
    fp = sha([cron_lines, pub_tbls])
    w = _write_chunk(SUB / "ops" / "_cron_realtime.md", "ops-cron-realtime", "ops",
                     "db:cron.job+pg_publication_tables", fp, body, check_only)
    if not check_only:
        print(f"  ops: wrote {w} chunk -> substrate/ops/_cron_realtime.md ({len(cron_lines)} crons, {len(pub_tbls)} realtime tables)")
    return w

def build_fk(check_only: bool):
    """FK / relational-integrity graph — every foreign key: child.col -> parent, ON DELETE action, and
    whether the FK column has a covering INDEX. An UNINDEXED FK = slow joins + slow/table-locking cascade
    deletes (the FK-undercount / embed-entry-FK class). ON DELETE CASCADE on a tenant-root FK is a
    blast-radius risk. Deterministic pg_constraint introspection."""
    (SUB / "fk").mkdir(exist_ok=True)
    rows = psql(
        "SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text, c.confdeltype, "
        "EXISTS(SELECT 1 FROM pg_index i WHERE i.indrelid=c.conrelid AND a.attnum = i.indkey[0]) "
        "FROM pg_constraint c "
        "JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum = c.conkey[1] "
        "WHERE c.contype='f' AND c.connamespace='public'::regnamespace "
        "ORDER BY 1, 2;")
    if rows is None:
        print("  SKIP fk: DB down"); return 0
    DEL = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}
    fks, unindexed, cascades = [], [], []
    for r in rows:
        if len(r) < 5:
            continue
        child, col, parent, deltype, indexed = r[0], r[1], r[2], r[3], r[4].strip() == "t"
        d = DEL.get(deltype, deltype)
        fks.append((child, col, parent, d, indexed))
        if not indexed:
            unindexed.append((child, col, parent))
        if d == "CASCADE":
            cascades.append((child, col, parent))
    body = [f"## fk · relational-integrity graph ({len(fks)} foreign keys)\n",
            f"**UNINDEXED FK columns ({len(unindexed)})** — slow joins + table-locking cascade deletes; "
            "add an index on the child column:\n"
            + ("\n".join(f"- `{c}`.`{col}` -> `{p}`" for c, col, p in unindexed[:60]) or "(none)")
            + (f"\n- … +{len(unindexed)-60} more" if len(unindexed) > 60 else ""),
            f"\n**ON DELETE CASCADE FKs ({len(cascades)})** — deleting the parent row deletes children; "
            "confirm the blast radius is intended (esp. FKs into hives/hive_members):\n"
            + ("\n".join(f"- `{c}`.`{col}` -> `{p}`" for c, col, p in cascades[:40]) or "(none)"),
            "\nLinks: [[reference_pm_knowledge_fk_100pct_broken]] [[reference_logbook_asset_linkage_undercount]]\n"]
    fp = sha([[c, col, p, d, ix] for c, col, p, d, ix in sorted(fks)])
    w = _write_chunk(SUB / "fk" / "_graph.md", "fk-graph", "fk",
                     "db:pg_constraint:foreign-keys", fp, "\n".join(body), check_only)
    if not check_only:
        print(f"  fk: wrote {w} graph chunk -> substrate/fk/_graph.md ({len(fks)} FKs, {len(unindexed)} unindexed, {len(cascades)} cascade)")
    return w

def build_gates(check_only: bool):
    """Catalog the registered gates (run_platform_checks.py VALIDATORS) — the 'WHAT'S ALREADY GATED' brain.
    Grep THIS before building a new gate (this session I nearly rebuilt the XSS suite that already existed
    as innerhtml-eschtml/like-escape/dom-xss). A bug-hunt cell reaches 100% only when a gate here locks it,
    so the catalog is also the scoreboard's source of truth. ast-parsed (no import/exec of the file)."""
    import ast as _ast
    f = ROOT / "run_platform_checks.py"
    if not f.exists():
        print("  SKIP gate: run_platform_checks.py absent"); return 0
    tree = _ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    gates = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign) and any(getattr(t, "id", None) == "VALIDATORS" for t in node.targets) \
           and isinstance(node.value, _ast.List):
            for el in node.value.elts:
                if not isinstance(el, _ast.Dict):
                    continue
                d = {}
                for k, v in zip(el.keys, el.values):
                    if isinstance(k, _ast.Constant) and isinstance(v, _ast.Constant):
                        d[k.value] = v.value
                if d.get("id"):
                    gates.append(d)
    (SUB / "gate").mkdir(exist_ok=True)
    by_group = {}
    for g in gates:
        by_group.setdefault(g.get("group", "?"), []).append(g)
    body = [f"## gate · registered validators ({len(gates)}) — the 'what's already gated' brain\n",
            "GREP THIS before building any new gate. A per-page bug-hunt cell is 100% only when a gate here "
            "LOCKS it, so this is also the scoreboard's source of truth. `⚡` = runs in `--fast`.\n"]
    for grp in sorted(by_group):
        body.append(f"\n### {grp} ({len(by_group[grp])})")
        for g in sorted(by_group[grp], key=lambda x: x.get("id", "")):
            fast = " ⚡" if not g.get("skip_if_fast") else ""
            lab = re.sub(r"\s+", " ", (g.get("label", "") or ""))[:160]
            body.append(f"- `{g['id']}`{fast} [{g.get('severity','fail')}] — {lab}")
    body.append("\nLinks: [[project_platform_knowledge_substrate]] [[reference_per_page_bughunt_roadmap]]\n")
    fp = sha([[g.get("id"), g.get("label"), g.get("group"), g.get("skip_if_fast"), g.get("severity")]
              for g in sorted(gates, key=lambda x: x.get("id", ""))])
    w = _write_chunk(SUB / "gate" / "_catalog.md", "gate-catalog", "gate",
                     "file:run_platform_checks.py:VALIDATORS", fp, "\n".join(body), check_only)
    if not check_only:
        print(f"  gate: wrote {w} catalog chunk -> substrate/gate/_catalog.md ({len(gates)} gates cataloged)")
    return w

def build_memory(check_only: bool):
    """Bring the auto-memory (Memento topic files) under the substrate as a FIRST-CLASS governed source.
    Memory is ALREADY retrievable (Memento indexes every memory/*.md into memory.db — that's what
    `memory_cache.py --retrieve` reads), so we do NOT duplicate 860 bodies into substrate/ (that would
    double-index + bloat). Instead one manifest chunk records the corpus + a per-file source_sha, giving
    memory the SAME no-regress/freshness guarantee tables/pages/skills have: edit any memory file and the
    manifest's combined sha changes, so validate_substrate_freshness flags it until rebuilt. The manifest
    IS the 'substrate knows about memory' record; the deep bodies stay in memory/ where retrieval finds
    them. MEMORY.md (the index) is separately governed by memory_write_quality (M3.1)."""
    if not MEM_DIR.exists():
        print("  SKIP memory: project memory dir absent"); return 0
    (SUB / "memory").mkdir(exist_ok=True)
    # Govern CURATED memory only (reference/feedback/project) — the durable "true memory" that must not
    # regress. EXCLUDE handoffs (transient per-session continuity, auto-created by the Stop hook — they'd
    # churn the manifest every session) and cached_web (external cache). Type read from frontmatter.
    CURATED = {"reference", "feedback", "project"}
    per = []
    for p in sorted(MEM_DIR.glob("*.md")):
        if p.name.startswith("MEMORY.md") or p.name.startswith("handoff"):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        mt = re.search(r"^\s*type:\s*(\w+)", t, re.M)
        ty = mt.group(1) if mt else "?"
        if ty not in CURATED:
            continue
        per.append((p.stem, ty, _fhash(t)))
    files = per
    combined = sha([[n, h] for n, _, h in per])  # combined sha = curated-memory fingerprint
    by_type = {}
    for _, ty, _h in per:
        by_type[ty] = by_type.get(ty, 0) + 1
    body = [f"## memory · curated auto-memory ({len(per)} durable topic files)\n",
            "First-class substrate source. The BODIES live in `memory/*.md` (Memento-indexed for "
            "retrieval via `memory_cache.py --retrieve`); this manifest is the freshness/governance record "
            "for the CURATED corpus (reference/feedback/project) — transient handoffs are excluded.\n",
            f"**By type:** " + " · ".join(f"{k}={v}" for k, v in sorted(by_type.items())),
            f"\n**Corpus fingerprint (source_sha):** editing/adding any curated memory changes it → rebuild "
            "`build_substrate.py --type memory` (part of the flywheel's persist spoke).\n",
            "\nEntries (name · type · sha):"]
    body += [f"- `{n}` · {ty} · {h}" for n, ty, h in per[:500]]
    if len(per) > 500:
        body.append(f"- … +{len(per)-500} more (all included in the fingerprint)")
    body.append("\nLinks: [[project_platform_knowledge_substrate]] [[reference_pm_attribution_pin]]\n")
    w = _write_chunk(SUB / "memory" / "_manifest.md", "memory-corpus", "memory",
                     f"memory-curated:{len(per)}-files", combined, "\n".join(body), check_only)
    if not check_only:
        print(f"  memory: wrote {w} manifest chunk -> substrate/memory/_manifest.md ({len(per)} curated files fingerprinted)")
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["table-rls", "rpc", "page", "edge-fn", "skill", "doc", "memory",
                                       "gate", "view", "config", "migration", "ops", "fk", "all"], default="all")
    ap.add_argument("--check", action="store_true", help="dry run: print what would change, write nothing")
    a = ap.parse_args()
    SUB.mkdir(exist_ok=True)
    print("Platform Knowledge Substrate — build" + (" (CHECK)" if a.check else ""))
    print("=" * 56)
    n = 0
    if a.type in ("table-rls", "all"):
        n += build_table_rls(a.check) or 0
    if a.type in ("rpc", "all"):
        n += build_rpc(a.check) or 0
    if a.type in ("page", "all"):
        n += build_pages(a.check) or 0
    if a.type in ("edge-fn", "all"):
        n += build_edge_fns(a.check) or 0
    if a.type in ("skill", "all"):
        n += build_skills(a.check) or 0
    if a.type in ("doc", "all"):
        n += build_docs(a.check) or 0
    if a.type in ("memory", "all"):
        n += build_memory(a.check) or 0
    if a.type in ("gate", "all"):
        n += build_gates(a.check) or 0
    if a.type in ("view", "all"):
        n += build_views(a.check) or 0
    if a.type in ("config", "all"):
        n += build_config(a.check) or 0
    if a.type in ("migration", "all"):
        n += build_migrations(a.check) or 0
    if a.type in ("ops", "all"):
        n += build_ops(a.check) or 0
    if a.type in ("fk", "all"):
        n += build_fk(a.check) or 0
    print(f"\n  {'would change' if a.check else 'wrote'} {n} chunk(s) across substrate/.")
    # In --check (freshness) mode, drift (a source changed but its chunk wasn't rebuilt) is a FAIL.
    return 1 if (a.check and n > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
