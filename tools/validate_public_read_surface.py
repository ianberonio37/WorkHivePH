#!/usr/bin/env python3
"""validate_public_read_surface.py — what a stranger can READ must be a DECISION, not a leftover.

BORN FROM A LIVE DEFECT (2026-08-04). `credit_treasury` holds one row and it is the whole financial
posture of the platform: authorised_credits 10,000,000, issued_credits 1,500. Its grants were
`anon -> SELECT, authenticated -> SELECT` and its policy was:

    credit_treasury_read | cmd=SELECT | roles=public | using=(id = 1)

`using (id = 1)` looks like a filter and is not one. There is exactly one row and its id IS 1, so
the predicate is `true` wearing a filter's clothes: it constrains WHICH row you get, never WHETHER
you may have it. Every provider, every buyer and every anonymous visitor could read how much money
had entered the business.

WHY THE EXISTING GATES ALL PASSED — three lenses, one uncovered middle:
  · validate_rls_coverage classifies by TENANT COLUMN (hive_id / auth_uid). credit_treasury is a
    singleton with neither, so it is outside that gate's lens by construction. It reported 0 gaps,
    correctly, for the question it asks.
  · the `rls_open_policy` flywheel check greps MIGRATION TEXT for `USING (true)`. `USING (id = 1)`
    is not that string, and a policy created by any path other than a migration file is invisible
    to it. It reported 2 findings (both real, both on `assets`) and could never report this one.
  · validate_client_write_grants asks who can WRITE. Nobody wrote here. The leak was a READ.

So the uncovered question is the simplest one: for a table a client can read, is there any rule at
all that consults WHO is asking? This gate asks exactly that, against the LIVE CATALOGUE rather
than migration text, because the catalogue is what actually answers a request.

CLASSIFICATION (deliberately three buckets, not two — the middle one is what keeps this quiet
enough to be read):
  · CALLER_AWARE — a SELECT policy whose predicate references the caller (auth.uid(), auth.jwt(),
    auth.role(), current_user, current_setting, is_platform_admin(), is_marketplace_admin(),
    auth_worker_names(), my_*()). This is a real access rule. Fine.
  · DELEGATED — the predicate has no caller token but scopes through a SUBQUERY over another table
    (`request_id in (select r.id from service_requests r)`). RLS applies to that subquery too, so
    the scoping is real, just inherited. Fine, and NOT flagged: calling these "open" is how a gate
    earns enough false positives to get baselined into silence.
  · OPEN — RLS is disabled outright, or the predicate never consults anybody. This is public data
    whether or not anyone decided it should be.

An OPEN table is not automatically a defect. Reference data (industry standards, terminology,
avatar animations) SHOULD be world-readable. The invariant is that it must be DECLARED, with a
reason, so that "the public can read this" is a sentence someone wrote on purpose. A new OPEN
table that nobody declared fails this gate.

Deterministic, offline apart from the local DB, no browser. Forward-only.

Usage:  python tools/validate_public_read_surface.py [--selftest]
"""
import os
import re
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
DB = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")

# A predicate that mentions any of these is asking WHO is calling.
CALLER_RE = re.compile(
    r"auth\.uid|auth\.jwt|auth\.role|current_user|current_setting|"
    r"is_platform_admin|is_marketplace_admin|auth_worker_names|\bmy_\w+\(",
    re.I)
# A predicate that scopes through another table inherits that table's row security.
DELEGATED_RE = re.compile(r"\bselect\b.+\bfrom\b", re.I | re.S)

# Names that mean money, identity or contact details. Being OPEN is not automatically wrong, but
# these get printed loudly even when declared, because they are the ones worth re-reading.
SENSITIVE_RE = re.compile(
    r"credit|treasur|ledger|payment|payout|receipt|invoice|wallet|balance|"
    r"email|phone|address|contact|token|secret|session", re.I)

# ── DECLARED: this data is public ON PURPOSE. A entry without a reason is a silenced failure. ──
DECLARED = {
    "achievement_definitions":      "the badge catalogue — the same for every hive, shown before sign-in",
    "ai_cache":                     "response cache keyed by prompt hash; holds no identity column and is "
                                    "read through the AI chain, never rendered to another user",
    "ai_global_budget":             "one row of THROTTLING state (minute/day counters, shed and deny counts). "
                                    "Checked 2026-08-04: no money, no identity — operational, not confidential",
    "ai_rate_limits":               "per-window request counters for the shared AI chain; no identity column",
    "avatar_animations":            "static animation manifests for the companion avatar",
    "best_practices":               "the maintenance knowledge base — reference content, the product's whole point",
    "canonical_agent_contracts":    "the canonical registry: published contracts, deliberately inspectable",
    "canonical_capabilities":       "canonical registry — see canonical_agent_contracts",
    "canonical_capture_contracts":  "canonical registry — see canonical_agent_contracts",
    "canonical_formulas":           "canonical registry — the formulas behind every KPI, cited in the UI",
    "canonical_lineage_edges":      "canonical registry — lineage shown by the provenance affordance",
    "canonical_sources":            "canonical registry — the source chips read this to name their origin",
    "canonical_standards":          "canonical registry — SMRP/ISO standard definitions shown as citations",
    "community_xp":                 "the community leaderboard is public by design; XP is not private data",
    "cross_hive_alerts":            "cross-hive BENCHMARK alerts, aggregate by construction. Checked "
                                    "2026-08-04: 0 rows and no hive_id/worker_name column, so nothing "
                                    "tenant-scoped can appear here without changing the schema",
    "embedding_cache":              "vector cache keyed by content hash; no identity column",
    "equipment_reading_templates":  "reading templates per equipment class — reference data",
    "fallback_model_faq":           "the public FAQ shown when the AI chain sheds load",
    "industry_standards":           "reference standards — public citations",
    "industry_standards_chunks":    "the chunked form of the same public standards, for retrieval",
    "marketplace_reviews":          "reviews are public on the listing page; that is what a review is for",
    "multilingual_terms":           "the Filipino/English dictionary the i18n layer reads",
    "network_benchmarks":           "cross-hive aggregate benchmarks — aggregate by construction",
    "ops_artifact_metrics":         "build/ops metrics for the status surface; no identity column",
    "persona_knowledge":            "persona prompt fragments for the AI chain — product content",
    "ph_intelligence_reports":      "published Philippine market reports — editorial content",
    "platform_feedback":            "policy IS caller-aware for private rows (is_public = true for the "
                                    "public branch, is_platform_admin() for the rest); listed here because "
                                    "the public branch is intentional",
    "platform_feedback_votes":      "vote tallies on public feedback; the votes are the public signal",
    "platform_knowledge_graph_facts": "the published knowledge graph — reference content",
    "service_slo_targets":          "the SLO targets the service pages publish as a promise",
    "terminology_gaps":             "terms the dictionary is missing — a content backlog, not user data",
    "tts_cache":                    "speech cache keyed by text hash; no identity column",
    "voice_response_queue":         "transient queue for the voice companion; no identity column",
    "wh_health_status":             "the health banner reads this before sign-in, which is the point",
}


def _query(sql):
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-tA", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
        if p.returncode != 0:
            return None
        return [l.rstrip("\n") for l in p.stdout.splitlines() if l.strip()]
    except Exception:
        return None


def classify(rls_enabled, quals):
    """Pure, so the self-test needs no database.

    quals: list of SELECT/ALL policy predicates (strings) attached to the table.
    """
    if not rls_enabled:
        return "OPEN"                      # no row security at all — policies are irrelevant
    if not quals:
        return "CLOSED"                    # RLS on with no policy denies everyone. Safe, not open.
    for q in quals:
        q = q or ""
        if CALLER_RE.search(q):
            return "CALLER_AWARE"
    for q in quals:
        if DELEGATED_RE.search(q or ""):
            return "DELEGATED"
    return "OPEN"


def selftest():
    print("  selftest: a caller-blind predicate on a readable table must classify OPEN")
    ok = True
    cases = [
        # the actual defect this gate was born from
        (True,  ["(id = 1)"],                                              "OPEN",         "credit_treasury"),
        (True,  ["true"],                                                  "OPEN",         "literal true"),
        (False, ["(auth.uid() = owner)"],                                  "OPEN",         "RLS disabled beats any policy"),
        (True,  [],                                                        "CLOSED",       "RLS on, no policy = deny all"),
        (True,  ["(auth.uid() = owner)"],                                  "CALLER_AWARE", "auth.uid"),
        (True,  ["is_platform_admin()"],                                   "CALLER_AWARE", "admin predicate"),
        (True,  ["(auth.role() = 'service_role'::text)"],                   "CALLER_AWARE", "auth.role"),
        (True,  ["(request_id IN ( SELECT r.id FROM service_requests r))"], "DELEGATED",    "scoped via subquery"),
        (True,  ["(is_public = true)"],                                    "OPEN",         "a column flag is not a caller"),
    ]
    for rls, quals, want, label in cases:
        got = classify(rls, quals)
        if got != want:
            print(f"  {RED}FAIL{RST} — {label}: expected {want}, got {got}")
            ok = False
    if ok:
        print(f"  {GREEN}PASS{RST} — OPEN / CLOSED / CALLER_AWARE / DELEGATED all separate correctly")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Public read surface{RST} — what a stranger can read must be declared, not left over")
    if selftest() != 0:
        return 1

    rows = _query(r"""
      with readable as (
        select distinct c.oid, c.relname, c.relrowsecurity
          from information_schema.role_table_grants g
          join pg_class c on c.relname = g.table_name
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
         where g.privilege_type = 'SELECT'
           and g.grantee in ('anon','authenticated')
           and c.relkind = 'r'
      )
      select r.relname, r.relrowsecurity::text,
             -- Policy predicates are pretty-printed and contain NEWLINES. psql -tA emits one output
             -- line per physical line, so an unflattened qual splits the row and truncates itself
             -- mid-predicate: `(request_id IN ( SELECT r.id` loses its FROM and reads as caller-blind.
             -- Flatten to one line here so the parser sees the whole predicate.
             coalesce((select regexp_replace(string_agg(coalesce(p.qual,'true'), ' @@ '), '\s+', ' ', 'g')
                         from pg_policies p
                        where p.schemaname='public' and p.tablename = r.relname
                          and p.cmd in ('SELECT','ALL')), '')
        from readable r order by r.relname;""")

    if rows is None:
        print(f"  {YEL}SKIP{RST} — local database not reachable (container '{DB}'). "
              f"This gate reads the live catalogue by design; migration text cannot answer it.")
        return 0

    buckets = {"OPEN": [], "CLOSED": [], "CALLER_AWARE": [], "DELEGATED": []}
    for line in rows:
        parts = line.split("|")
        if len(parts) < 3:
            continue
        # `relrowsecurity::text` renders 'true'/'false', NOT psql's bare 't'/'f'. The first version
        # of this line compared against "t", so EVERY table read as RLS-disabled and short-circuited
        # to OPEN: 165 tables, 131 "findings", every one of them false. Accept both spellings.
        name, rls, quals = parts[0], parts[1].strip().lower() in ("t", "true"), parts[2]
        buckets[classify(rls, [q for q in quals.split(" @@ ") if q])].append(name)

    total = sum(len(v) for v in buckets.values())
    print(f"  {DIM}client-readable tables: {total} · "
          f"caller-aware {len(buckets['CALLER_AWARE'])} · delegated {len(buckets['DELEGATED'])} · "
          f"closed {len(buckets['CLOSED'])} · open {len(buckets['OPEN'])}{RST}")

    # INSTRUMENT SELF-CHECK. This platform runs RLS almost everywhere, so "every readable table is
    # wide open" is not a finding, it is a broken parser — which is exactly what shipped the first
    # time this ran (a 't' vs 'true' comparison produced 131 confident false findings). An
    # implausibly BAD reading deserves the same suspicion as an implausibly good one.
    if total >= 20 and not buckets["CALLER_AWARE"]:
        print(f"\n  {RED}FAIL{RST} — instrument check: {total} readable tables and NOT ONE has a "
              f"caller-aware policy. That is not credible on this database; the catalogue parse is "
              f"broken. Fix the gate before believing any finding below.")
        return 1

    undeclared = [t for t in buckets["OPEN"] if t not in DECLARED]
    sensitive_declared = [t for t in buckets["OPEN"] if t in DECLARED and SENSITIVE_RE.search(t)]

    if sensitive_declared:
        print(f"  {YEL}NOTE{RST} — declared public, but the name suggests money or identity. Re-read these:")
        for t in sensitive_declared:
            print(f"    · {BOLD}{t}{RST} — {DIM}{DECLARED[t]}{RST}")

    if undeclared:
        print(f"\n  {RED}FAIL{RST} — {len(undeclared)} table(s) are readable by a client with no rule "
              f"that consults the caller, and nobody declared them public:")
        for t in undeclared:
            flag = f"  {RED}<-- name suggests money or identity{RST}" if SENSITIVE_RE.search(t) else ""
            print(f"    · {BOLD}{t}{RST}{flag}")
        print(f"\n  {DIM}Either give it a policy that asks who is calling, or add it to DECLARED with "
              f"the reason it is public. 'using (id = 1)' is not an access rule: it picks a row, it "
              f"does not check a person.{RST}")
        return 1

    print(f"\n  {GREEN}PASS{RST} — every client-readable table either checks the caller, inherits "
          f"scoping, denies by default, or is declared public with a reason")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
