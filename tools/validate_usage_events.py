"""validate_usage_events.py - SL L3 (2026-10-21): a page's USE is recorded as events someone can count, under an
identity the database decided.

Measured on the 31 L3 pages: every one logged a page_view and 30 of them recorded nothing else, although the table's own
migration promised "feature pages ALSO emit feature_use" - so the operator could count VISITS per page and never what a
page was used for. And a count by person or by hive was a count of claims: an anonymous insert kept whatever auth_uid it
sent, and for everyone hive_id and worker_name were whatever the device remembered. Migration 20261021000002 binds the
identity and adds founder_feature_use; utils.js whUse(db, action, props) records one use where the use is confirmed;
the operator's usage card on platform-actions read it (the operator console's Growth Pulse, since OPC 2026-10-22).

STATIC (no database)
  U1 utils.js: whUse screens props (keys that can carry a person or their words, long strings, nested values), records
     a feature_use through logEvent and RETURNS its promise; logEvent returns its insert; whUseThen waits for the row
     at most a bounded time (a page that reloads right after a use).
  U2 every L3 page records the uses USES lists for it (a call carrying that action's literal, comments stripped); the
     two retired operator pages record their visit and nothing else.
  U3 no use carries a props key that could hold a person or their words.
  U4 the refused-update fixes this unit made stay made: each write whose refusal returns no rows and no error reads its
     rows back and says so (hive focus, a seller's inquiry reply and close, a project's status / delete / item status,
     a shift plan's archive), and the blocked print window is told.
  U5 every whUse(<client>, ...) call has its client in scope (tools/check_whuse_scope.mjs - out of scope it throws and
     the handler dies with the use).
  U6 the newest migration defining bind_analytics_events_submitter binds a visitor to no account / hive / name, a member
     to their account, an active-membership hive and their own name, and screens props; founder_feature_use counts
     accounts and signed-out sessions apart, as the caller (SECURITY INVOKER); the partial index exists.
  U7 the operator console's Growth Pulse reads founder_feature_use, renders it, and its figure-source names it (it
     carries Platform Actions' usage card, OPC 2026-10-22).
  U8 one page_view per load: one logPageView call site per L3 page (founder-console's two are exclusive branches).
LIVE (the local database; one rolled-back transaction; the people are picked from the data)
  V1 a visitor inserting a forged account, hive and name keeps none of them; an email, a note, an 80-character string and
     a nested object are dropped from props, a count kept.
  V2 a member inserting another account, a hive they are not in and another name gets their own account, no hive and
     their own name; in their own hive the hive is kept.
  V3 founder_feature_use, read as a platform admin, counts the probes by page and action with accounts and signed-out
     sessions apart; read as a member who is not an admin it returns nothing.
  V4 the binder trigger is present and enabled.
SELF-TEST (--self-test): static mutants (synthetic files) and live mutants (each inside the probe's own rolled-back
transaction) must each turn their check red, and the clean run must stay green.

    python tools/validate_usage_events.py [--self-test] [--json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
DB = "supabase_db_workhive"

USES = {
    "achievements.html": ["achievement_opened"],
    "alert-hub.html": ["alert_handled", "alert_snoozed", "alert_seen", "alert_unseen", "alert_put_back",
                       "brief_approved", "brief_rejected"],
    "analytics-report.html": ["report_generated", "report_exported", "print_opened"],
    "analytics.html": ["phase_opened", "period_changed"],
    "asset-hub.html": ["asset_opened", "fmea_mode_added", "rcm_strategy_saved", "fmea_mode_approved", "fmea_mode_deleted",
                       "rcm_strategy_approved", "rcm_strategy_deleted"],
    "assistant.html": ["question_answered", "answer_rated"],
    "community.html": ["post_published", "post_edited", "reply_posted", "reaction_added", "best_answer_marked",
                       "best_answer_removed", "post_pinned", "post_unpinned", "post_flagged", "post_unflagged",
                       "post_deleted", "post_restored", "post_reported"],
    "dayplanner.html": ["item_added", "item_edited", "item_removed"],
    "hive.html": ["hive_joined", "hive_left", "supervisor_handed_off", "hive_renamed", "member_removed",
                  "submission_approved", "submission_rejected", "hive_focus_set", "handover_generated",
                  "handover_copied", "handover_printed", "history_brought_in"],
    "index.html": ["stage_opened", "all_tools_opened", "persona_switched"],
    "integrations.html": ["vehicle_added", "tab_opened", "hive_gate_followed", "import_run", "api_key_created", "api_key_revoked", "sync_config_saved", "sync_run",
                          "import_rolled_back", "conflict_resolved"],
    "inventory.html": ["part_used", "part_restocked", "part_added", "part_edited"],
    "logbook.html": ["entry_logged", "entry_edited", "entry_closed", "team_searched", "entries_exported",
                     "asset_registered", "asset_edited"],
    "marketplace-seller-profile.html": ["section_opened", "seller_contacted"],
    "marketplace-seller.html": ["inquiry_replied", "inquiry_closed", "listing_edited", "listing_deleted",
                                "messenger_saved", "certs_saved", "starter_claimed", "job_accepted", "job_advanced"],
    "marketplace.html": ["listing_opened", "listing_watched", "inquiry_sent", "quotes_requested", "search_saved",
                         "review_posted", "listing_submitted"],
    "ph-intelligence.html": ["report_generated"],
    "plant-connections.html": ["connections_refreshed", "retention_set"],
    "pm-scheduler.html": ["pm_completed", "pm_task_added", "pm_asset_added", "pm_asset_edited", "auto_hail_on",
                          "auto_hail_off"],
    "project-manager.html": ["project_created", "project_edited", "project_deleted", "project_status_set",
                             "item_status_changed", "change_order_submitted", "change_order_approved",
                             "change_order_rejected", "change_order_cancelled", "lessons_saved", "project_linked",
                             "scope_imported", "progress_acknowledged"],
    "project-report.html": ["report_exported", "print_opened", "narrative_generated"],
    "public-feed.html": ["more_loaded"],
    "report-sender.html": ["report_sent", "recipient_added", "recipient_removed"],
    # resume recorded its uses before L3, as resume_* events through logEvent; the rollup counts them by name
    "resume.html": ["resume_saved", "resume_export", "resume_autofill", "resume_upload_import", "resume_polish",
                    "resume_tailor", "resume_summarize", "resume_jd_score", "resume_cover_letter", "resume_print_opened"],
    "shift-brain.html": ["plan_published", "plan_archived", "plan_rerun", "shift_window_opened"],
    "skillmatrix.html": ["lesson_opened", "exam_started", "exam_graded", "targets_saved"],
    "ai-quality.html": ["details_opened"],
    "audit-log.html": ["trail_filtered", "trail_exported"],
    # the operator console's queues (OPC, 2026-10-22): recorded on founder-console.html from operator-actions.js, which
    # tools/build_operator_actions.py cuts from retired platform-actions.html (GENERATED_FROM below)
    "operator-actions.js": ["topup_verified", "topup_rejected", "listing_approved", "listing_rejected",
                            "seller_identity_verified", "seller_certs_verified", "feedback_triaged"],
    "founder-console.html": [],      # its uses are the queues' (operator-actions.js); listed for U8's one page view
}
RETIRED = {"platform-actions.html", "marketplace-admin.html"}      # a retired page's use IS its visit
# a retired page whose script is the SOURCE a live file is generated from: its uses run there, so they are not a retired
# page recording uses - provided every one of them reaches the generated file
GENERATED_FROM = {"platform-actions.html": "operator-actions.js"}
# shared components that record a use on whichever page shows them: the maturity gate IS the page for a hive below its
# stair (ai-quality and ph-intelligence were walked locked), and opening how the stairway works is its one in-page act
SHARED_USES = {"maturity-gate.js": ["stairway_explained", "stairway_opened"]}
PAGEVIEW_SITES = {"founder-console.html": 2}                        # two exclusive branches (retired / live console)
PII_KEY = re.compile(r"^(email|phone|mobile|name|full_?name|display_?name|worker_?name|author|message|content|body|"
                     r"text|notes?|comment|address|password|token|query|q)$", re.I)

# (page, what it guards, pattern that must be present)
REFUSAL_READBACKS = [
    ("hive.html", "the hive focus save reads its row back", r"update\(\{\s*intent:\s*payload\s*\}\)\.eq\('id',\s*HIVE_ID\)\.select\('id'\)"),
    ("hive.html", "a focus save that matched nothing says so", r"if \(!res \|\| !res\.data \|\| !res\.data\.length\)"),
    ("hive.html", "a blocked print window is told", r"if \(!win\) \{ showToast\("),
    ("marketplace-seller.html", "an inquiry reply reads its row back", r"replied_at: now \}\)\s*\.eq\('id', inqId\)\s*\.select\('id'\)"),
    ("marketplace-seller.html", "a reply that matched nothing says so", r"if \(!_replied \|\| !_replied\.length\)"),
    ("marketplace-seller.html", "an inquiry close reads its row back", r"update\(\{ status: 'closed' \}\)\.eq\('id', inqId\)\.select\('id'\)"),
    ("marketplace-seller.html", "a close that matched nothing says so", r"if \(!_closed \|\| !_closed\.length\)"),
    ("project-manager.html", "a project status change reads its row back", r"if \(!_set \|\| !_set\.length\)"),
    ("project-manager.html", "a project delete reads its row back", r"if \(!_hidden \|\| !_hidden\.length\)"),
    ("project-manager.html", "an item status change reads its row back", r"if \(!_moved \|\| !_moved\.length\)"),
    ("shift-brain.html", "a plan archive reads its row back", r"if \(!_arch \|\| !_arch\.length\)"),
]


# ── source helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def strip_js_comments(src: str) -> str:
    """Line and block comments out, strings kept (a URL's // inside a string is not a comment)."""
    out, i, n, q = [], 0, len(src), None
    while i < n:
        c = src[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1]); i += 2; continue
            if c == q:
                q = None
            i += 1; continue
        if c in "'\"`":
            q = c; out.append(c); i += 1; continue
        if src.startswith("//", i):
            j = src.find("\n", i); i = n if j < 0 else j; continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        if src.startswith("<!--", i):
            j = src.find("-->", i + 4); i = n if j < 0 else j + 3; continue
        out.append(c); i += 1
    return "".join(out)


def call_spans(src: str, names: tuple[str, ...]) -> list[str]:
    """The argument text of every call to one of `names` (balanced parentheses, strings respected)."""
    spans = []
    for m in re.finditer(r"\b(" + "|".join(names) + r")\(", src):
        i, depth, q, start = m.end(), 1, None, m.end()
        while i < len(src) and depth:
            c = src[i]
            if q:
                if c == "\\":
                    i += 2; continue
                if c == q:
                    q = None
            elif c in "'\"`":
                q = c
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1
        spans.append(src[start:i - 1])
    return spans


def split_args(span: str) -> list[str]:
    args, depth, q, cur = [], 0, None, []
    i = 0
    while i < len(span):
        c = span[i]
        if q:
            cur.append(c)
            if c == "\\" and i + 1 < len(span):
                cur.append(span[i + 1]); i += 2; continue
            if c == q:
                q = None
        elif c in "'\"`":
            q = c; cur.append(c)
        elif c in "([{":
            depth += 1; cur.append(c)
        elif c in ")]}":
            depth -= 1; cur.append(c)
        elif c == "," and depth == 0:
            args.append("".join(cur).strip()); cur = []
        else:
            cur.append(c)
        i += 1
    if cur:
        args.append("".join(cur).strip())
    return args


def recorded_actions(src: str) -> set[str]:
    acts = set()
    for span in call_spans(src, ("whUse", "whUseThen", "whUseLink")):
        a = split_args(span)
        if len(a) >= 2:
            acts.update(re.findall(r"'([a-z][a-z0-9_]{2,47})'", a[1]))
    for span in call_spans(src, ("logEvent",)):
        a = split_args(span)
        if len(a) >= 2:
            acts.update(re.findall(r"'([a-z][a-z0-9_]{2,47})'", a[1]))
    return acts


def props_keys(src: str) -> list[str]:
    keys = []
    for span in call_spans(src, ("whUse", "whUseThen")):
        a = split_args(span)
        if len(a) >= 3 and a[2].startswith("{"):
            keys += re.findall(r"(?:^|[{,])\s*([A-Za-z_$][\w$]*)\s*:", a[2])
    return keys


def last_function_sql(name: str) -> tuple[str, str]:
    """(file, body) of the NEWEST migration that creates or replaces public.<name>."""
    pat = re.compile(r"create\s+(?:or\s+replace\s+)?function\s+(?:public\.)?" + re.escape(name) + r"\s*\(.*?\$(\w*)\$(.*?)\$\1\$",
                     re.I | re.S)
    found = ("", "")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        for m in pat.finditer(f.read_text(encoding="utf-8", errors="replace")):
            found = (f.name, m.group(0))
    return found


# ── static ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_static(files: dict[str, str] | None = None, migrations_extra: str = "", run_scope: bool = True) -> list[str]:
    """`files` overrides page / utils text (self-test mutants); otherwise read from disk."""
    def text(rel: str) -> str:
        if files and rel in files:
            return files[rel]
        return (ROOT / rel).read_text(encoding="utf-8", errors="replace")

    issues = []
    utils = strip_js_comments(text("utils.js"))
    m = re.search(r"function whUse\(db, action, props\) \{(.*?)\n\}", utils, re.S)
    body = m.group(1) if m else ""
    if not body:
        issues.append("U1 utils.js has no whUse(db, action, props)")
    else:
        for need, why in ((r"WH_USE_PII_KEY\.test\(k\)", "screens props keys"),
                          (r"typeof v === 'string' && v\.length <= 60", "drops long strings"),
                          (r"return logEvent\(db, 'feature_use'", "records a feature_use and returns its promise")):
            if not re.search(need, body):
                issues.append(f"U1 whUse no longer {why}")
        pm = re.search(r"const WH_USE_PII_KEY = /(.*?)/i;", utils)
        for k in ("email", "phone", "message", "content", "notes", "address", "token"):
            if not pm or not re.search(pm.group(1), k, re.I):
                issues.append(f"U1 the props screen lets '{k}' through")
    lm = re.search(r"function logEvent\(db, eventName, props\) \{(.*?)\n\}", utils, re.S)
    if not lm or "return db.auth.getSession()" not in lm.group(1) or "return db.from('analytics_events').insert(payload)" not in lm.group(1):
        issues.append("U1 logEvent no longer returns its insert (a page that reloads after a use cannot wait for it)")
    if not re.search(r"function whUseThen\(.*?Promise\.race\(", utils, re.S):
        issues.append("U1 whUseThen no longer bounds its wait")
    # a remembered tab is restored by CLICKING it and a remembered filter by dispatching 'change': the page's own handler
    # runs, so without the replay guard a load nobody touched records a use (the seller profile did, at 275 ms)
    if not re.search(r"function whUse\(db, action, props\) \{\s*if \(_whReplaying\) return;", utils):
        issues.append("U1 whUse no longer ignores a replayed choice (a restored tab or filter counted as a use)")
    if "whReplay(function () { b.click(); })" not in utils:
        issues.append("U1 whAutoRememberTabs restores a tab outside whReplay - every restore counts as a use")
    if "whReplay(function () { el.dispatchEvent(new Event('change', { bubbles: true })); })" not in utils:
        issues.append("U1 whAutoRememberFilters restores a filter outside whReplay - every restore counts as a use")

    for page, acts in USES.items():
        src = strip_js_comments(text(page))
        got = recorded_actions(src)
        missing = [a for a in acts if a not in got]
        if missing:
            issues.append(f"U2 {page} no longer records {missing}")
        bad = [k for k in props_keys(src) if PII_KEY.match(k)]
        if bad:
            issues.append(f"U3 {page} sends {sorted(set(bad))} in a use's props - a key that can carry a person or their words")
    for shared, acts in SHARED_USES.items():
        missing = [a for a in acts if a not in recorded_actions(strip_js_comments(text(shared)))]
        if missing:
            issues.append(f"U2 {shared} no longer records {missing}")
    for page in RETIRED:
        src = strip_js_comments(text(page))
        if "logPageView(" not in src:
            issues.append(f"U2 {page} (retired) no longer records its visit")
        if page in GENERATED_FROM:
            lost = recorded_actions(src) - recorded_actions(strip_js_comments(text(GENERATED_FROM[page])))
            if lost:
                issues.append(f"U2 {page} is retired and records {sorted(lost)} that {GENERATED_FROM[page]} (cut from "
                              f"its script) does not - those uses cannot happen anywhere")
        elif recorded_actions(src) - {"page_view"} and call_spans(src, ("whUse", "whUseThen")):
            issues.append(f"U2 {page} is retired and records uses - its page's work is skipped, so those cannot happen")

    for page, what, pat in REFUSAL_READBACKS:
        if not re.search(pat, text(page)):
            issues.append(f"U4 {page}: {what} - no longer")

    if run_scope:
        pages = sorted(set(USES) | RETIRED)
        try:
            r = subprocess.run(["node", "tools/check_whuse_scope.mjs", *pages], cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", timeout=240)
            if r.returncode != 0:
                issues += ["U5 " + l.strip() for l in r.stdout.splitlines() if l.strip().startswith(("NOT IN SCOPE", "UNCHECKED"))] \
                          or [f"U5 the scope check failed: {(r.stderr or r.stdout).strip()[-200:]}"]
        except (OSError, subprocess.TimeoutExpired) as e:
            issues.append(f"U5 the scope check could not run: {e}")

    fname, binder = last_function_sql("bind_analytics_events_submitter")
    if migrations_extra:
        mm = re.search(r"create\s+or\s+replace\s+function\s+public\.bind_analytics_events_submitter\(.*?\$\$(.*?)\$\$", migrations_extra, re.I | re.S)
        if mm:
            fname, binder = "zzzz_mutant.sql", mm.group(0)
    low = re.sub(r"\s+", " ", binder.lower())
    for need, why in (("if v_uid is null then new.auth_uid := null; new.hive_id := null; new.worker_name := null;",
                       "a visitor keeps no claimed account, hive or name"),
                      ("new.auth_uid := v_uid;", "a member's events carry their own account"),
                      ("hm.status = 'active'", "a hive is kept only for an ACTIVE membership"),
                      ("from public.worker_profiles wp where wp.auth_uid = v_uid", "the name is the account's own"),
                      ("new.props := coalesce(", "props are screened in the database")):
        if need not in low:
            issues.append(f"U6 {fname or 'no migration'}: the binder no longer ensures {why}")
    if re.search(r"if auth\.uid\(\) is null then return new", low):
        issues.append(f"U6 {fname}: the binder lets a visitor through untouched again (forged accounts kept)")
    _, rollup = last_function_sql("founder_feature_use")
    rl = re.sub(r"\s+", " ", rollup.lower())
    if not rl:
        issues.append("U6 founder_feature_use is not defined in any migration")
    else:
        for need, why in (("security invoker", "runs as the caller (so only an admin's read sees the events)"),
                          ("count(distinct e.auth_uid)", "counts accounts"),
                          ("filter (where e.auth_uid is null)", "counts signed-out sessions apart from accounts"),
                          ("event_name <> 'page_view'", "counts uses, not visits")):
            if need not in rl:
                issues.append(f"U6 founder_feature_use no longer {why}")
    if not any("idx_analytics_events_use_created" in f.read_text(encoding="utf-8", errors="replace")
               for f in MIGRATIONS.glob("*.sql")):
        issues.append("U6 the partial index for use events is gone")

    # the operator console's Growth Pulse carries the usage card Platform Actions had (OPC, 2026-10-22)
    fc = text("founder-console.html")
    if "db.rpc('founder_feature_use'" not in fc or "${usesBlock(uses)}" not in fc:
        issues.append("U7 the operator console no longer reads and renders founder_feature_use")
    if not re.search(r'"sel":"#growth-content"[^}]*"reads":"[^"]*founder_feature_use', fc):
        issues.append("U7 the Growth Pulse's figure-source no longer names founder_feature_use")
    # founder_dau_series returns {day, dau, events}: "People today" read .count / .value and printed "-" for months
    if "byDay[String(r.day).slice(0, 10)] = Number(r.dau) || 0;" not in fc or "byDay[manilaKey(new Date())]" not in fc:
        issues.append("U7 'People today' no longer reads today's row of founder_dau_series by its dau column")

    for page in sorted(p for p in set(USES) | RETIRED if p.endswith(".html")):   # a script is not a load
        n = len(re.findall(r"\blogPageView\(", strip_js_comments(text(page))))
        if n != PAGEVIEW_SITES.get(page, 1):
            issues.append(f"U8 {page} has {n} logPageView call sites (one load must be one page_view)")
    return issues


# ── live ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def psql(sql: str, timeout: int = 180) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At",
                            "-v", "ON_ERROR_STOP=1", "-f", "-"], input=sql, capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, "", str(e)


PICK_SQL = r"""
select json_build_object(
  'member', m.auth_uid, 'hive', m.hive_id,
  'name', coalesce((select wp.display_name from public.worker_profiles wp where wp.auth_uid = m.auth_uid limit 1), m.worker_name),
  'foreign_hive', (select h.id from public.hives h
                    where not exists (select 1 from public.hive_members x where x.hive_id = h.id and x.auth_uid = m.auth_uid and x.status = 'active')
                    order by h.id limit 1),
  'admin', (select pa.auth_uid from public.marketplace_platform_admins pa where pa.auth_uid is not null order by pa.auth_uid limit 1)
)::text
from public.hive_members m
where m.status = 'active' and m.auth_uid is not null
  and not exists (select 1 from public.marketplace_platform_admins pa where pa.auth_uid = m.auth_uid)
  -- a profile name makes the bound name unambiguous in BOTH probes (outside a hive only the profile can name them)
  and exists (select 1 from public.worker_profiles wp where wp.auth_uid = m.auth_uid and wp.display_name is not null)
order by m.hive_id, m.auth_uid limit 1;
"""


def _claims(uid: str | None) -> str:
    if uid is None:
        return "select set_config('request.jwt.claims', '{\"role\":\"anon\"}', true);"
    return "select set_config('request.jwt.claims', json_build_object('sub', '%s', 'role', 'authenticated')::text, true);" % uid


def probe_sql(p: dict, mutation: str = "") -> str:
    m, h, fh, adm = p["member"], p["hive"], p["foreign_hive"], p["admin"]
    return "\n".join([
        "begin;",
        mutation,
        "select 'TRG|' || coalesce((select tgenabled::text from pg_trigger where tgrelid = 'public.analytics_events'::regclass "
        "and tgname = 'trg_bind_analytics_events_submitter'), 'missing');",
        # V1 - a visitor
        "set local role anon;", _claims(None),
        "insert into public.analytics_events (event_name, page, props, auth_uid, hive_id, worker_name, session_id) values "
        f"('feature_use', 'wh-l3-probe', jsonb_build_object('action', 'probe_visitor', 'email', 'a@b.c', 'note', 'my own words', "
        f"'count', 3, 'long', repeat('x', 80), 'nested', jsonb_build_object('a', 1)), '{m}', '{h}', 'Forged Name', 'WH-L3-PROBE-v1');",
        "reset role;",
        # V2 - a member, forging, then in their own hive
        _claims(m), "set local role authenticated;",
        "insert into public.analytics_events (event_name, page, props, auth_uid, hive_id, worker_name, session_id) values "
        f"('feature_use', 'wh-l3-probe', '{{\"action\": \"probe_member\"}}'::jsonb, gen_random_uuid(), '{fh}', 'Someone Else', 'WH-L3-PROBE-v2'), "
        f"('feature_use', 'wh-l3-probe', '{{\"action\": \"probe_member\"}}'::jsonb, null, '{h}', null, 'WH-L3-PROBE-v2b');",
        # V3 - the rollup as this member (not an admin)
        "select 'MEMBER|' || coalesce((select jsonb_agg(to_jsonb(r))::text from public.founder_feature_use(1) r where r.page = 'wh-l3-probe'), '[]');",
        "reset role;",
        _claims(adm), "set local role authenticated;",
        "select 'ADMIN|' || coalesce((select jsonb_agg(to_jsonb(r) order by r.action)::text from public.founder_feature_use(1) r where r.page = 'wh-l3-probe'), '[]');",
        "reset role;",
        "select 'ROW|' || json_build_object('s', session_id, 'uid', auth_uid, 'hive', hive_id, 'name', worker_name, 'props', props)::text "
        "from public.analytics_events where session_id like 'WH-L3-PROBE-%' order by session_id;",
        "rollback;",
    ])


def judge(p: dict, out: str) -> dict:
    res = {"V1": [], "V2": [], "V3": [], "V4": []}
    rows, member_roll, admin_roll, trg = {}, None, None, None
    for line in out.splitlines():
        tag, _, val = line.partition("|")
        if tag == "ROW":
            r = json.loads(val); rows[r["s"]] = r
        elif tag == "MEMBER":
            member_roll = json.loads(val)
        elif tag == "ADMIN":
            admin_roll = json.loads(val)
        elif tag == "TRG":
            trg = val.strip()
    if trg != "O":
        res["V4"].append(f"the binder trigger is {trg or 'not reported'} (O = enabled)")
    v1 = rows.get("WH-L3-PROBE-v1")
    if not v1:
        res["V1"].append("the visitor's event did not land")
    else:
        if v1["uid"] or v1["hive"] or v1["name"]:
            res["V1"].append(f"a visitor's event kept a claimed identity: account={v1['uid']} hive={v1['hive']} name={v1['name']!r}")
        pr = v1["props"] or {}
        kept = [k for k in ("email", "note", "long", "nested") if k in pr]
        if kept:
            res["V1"].append(f"props kept {kept} - a person's details or words in an event")
        if pr.get("count") != 3 or pr.get("action") != "probe_visitor":
            res["V1"].append(f"props lost what may stay: {pr}")
    v2, v2b = rows.get("WH-L3-PROBE-v2"), rows.get("WH-L3-PROBE-v2b")
    if not v2 or not v2b:
        res["V2"].append("the member's events did not land")
    else:
        if v2["uid"] != p["member"]:
            res["V2"].append(f"a member's event carries the account it CLAIMED ({v2['uid']}), not theirs")
        if v2["hive"] is not None:
            res["V2"].append("a member's event kept a hive they are not a member of")
        if v2["name"] != p["name"]:
            res["V2"].append(f"a member's event carries the name {v2['name']!r}, not their own {p['name']!r}")
        if v2b["hive"] != p["hive"] or v2b["uid"] != p["member"]:
            res["V2"].append("a member's event in their own hive lost the hive or the account")
    if member_roll:
        res["V3"].append(f"a member who is not an admin reads usage through founder_feature_use: {member_roll}")
    by = {r["action"]: r for r in (admin_roll or [])}
    pv, pm = by.get("probe_visitor"), by.get("probe_member")
    if not pv or not pm:
        res["V3"].append(f"the admin's rollup does not count the probes: {admin_roll}")
    else:
        if (pv["uses"], pv["accounts"], pv["visitor_sessions"]) != (1, 0, 1):
            res["V3"].append(f"a visitor's use counted as {pv} (want 1 use, 0 accounts, 1 signed-out session)")
        if (pm["uses"], pm["accounts"], pm["visitor_sessions"]) != (2, 1, 0):
            res["V3"].append(f"a member's two uses counted as {pm} (want 2 uses, 1 account, 0 signed-out sessions)")
    return res


def pick() -> tuple[dict | None, str]:
    code, out, err = psql(PICK_SQL)
    line = next((l for l in out.splitlines() if l.startswith("{")), "")
    if code != 0 or not line:
        return None, (err or "no active member who is not a platform admin").strip()[:300]
    p = json.loads(line)
    missing = [k for k in ("foreign_hive", "admin", "name") if not p.get(k)]
    if missing:
        return None, f"the data lacks {missing} - reseed (test-data-seeder) before this gate can run"
    return p, ""


def run_live(p: dict, mutation: str = "") -> tuple[dict, str]:
    code, out, err = psql(probe_sql(p, mutation))
    if code != 0:
        return {}, (err or out).strip()[-600:]
    return judge(p, out), ""


# ── self-test ──────────────────────────────────────────────────────────────────────────────────────────────────────
def live_mutants(binder: str, rollup: str) -> list[tuple[str, str, str]]:
    def sub(src: str, pat: str, rep: str = "") -> str:
        out, n = re.subn(pat, rep, src, count=1, flags=re.S)
        return out + ";" if n else ""
    old_binder = ("create or replace function public.bind_analytics_events_submitter() returns trigger language plpgsql "
                  "security definer set search_path = public as $m$ begin if auth.uid() is null then return new; end if; "
                  "new.auth_uid := auth.uid(); return new; end $m$;")
    return [
        ("the old binder (a visitor passes untouched)", "V1", old_binder),
        ("hive kept as claimed", "V2", sub(binder, r"if new\.hive_id is not null and not exists \(.*?end if;")),
        ("name left to the page", "V2", sub(binder, r"new\.worker_name := coalesce\(.*?limit 1\)\);")),
        ("props not screened", "V1", sub(binder, r"new\.props := coalesce\(\(.*?'\{\}'::jsonb\);")),
        ("binder trigger dropped", "V4", "drop trigger trg_bind_analytics_events_submitter on public.analytics_events;"),
        ("signed-out sessions counted as accounts", "V3",
         sub(rollup, r"count\(distinct e\.auth_uid\)::bigint", "count(distinct coalesce(e.auth_uid::text, e.session_id))::bigint")),
        # pg_get_functiondef omits SECURITY INVOKER (the default), so the mutant ADDS definer after the volatility
        ("rollup runs as its owner (reads past RLS)", "V3", sub(rollup, r"\bSTABLE\b", "STABLE SECURITY DEFINER")),
    ]


def self_test() -> list[str]:
    fails = []
    clean = check_static()
    if clean:
        fails.append(f"static is not clean on the real files: {clean[:3]}")
    utils = (ROOT / "utils.js").read_text(encoding="utf-8")
    hive = (ROOT / "hive.html").read_text(encoding="utf-8")
    logbook = (ROOT / "logbook.html").read_text(encoding="utf-8")
    synthetic = [
        ("whUse stops screening keys", {"utils.js": utils.replace("WH_USE_PII_KEY.test(k)", "false", 1)}, "", "U1"),
        # (the anchor is logEvent's own insert: "return db.auth.getSession()" also opens another utils function)
        ("logEvent stops returning its insert", {"utils.js": utils.replace("return db.from('analytics_events').insert(payload)", "db.from('analytics_events').insert(payload)", 1)}, "", "U1"),
        ("a remembered tab restored by a plain click", {"utils.js": utils.replace("whReplay(function () { b.click(); })", "b.click()", 1)}, "", "U1 whAutoRememberTabs"),
        ("a page's use removed", {"logbook.html": logbook.replace("'team_searched'", "'x_removed'", 1)}, "", "U2 logbook.html"),
        ("a use carries a name", {"logbook.html": logbook.replace("whUse(db, 'entries_exported', { rows:", "whUse(db, 'entries_exported', { name: WORKER_NAME, rows:", 1)}, "", "U3 logbook.html"),
        ("hive focus stops reading its row back", {"hive.html": hive.replace("update({ intent: payload }).eq('id', HIVE_ID).select('id')", "update({ intent: payload }).eq('id', HIVE_ID)", 1)}, "", "U4 hive.html"),
        ("binder back to the anon pass-through", None,
         "create or replace function public.bind_analytics_events_submitter() returns trigger language plpgsql as $$ begin "
         "if auth.uid() is null then return new; end if; new.auth_uid := auth.uid(); return new; end $$;", "U6"),
        ("a second page view site", {"hive.html": hive.replace("logPageView(db", "logPageView(db); logPageView(db", 1)}, "", "U8 hive.html"),
        ("a retired source records a use its generated file lacks", {"operator-actions.js": (ROOT / "operator-actions.js").read_text(encoding="utf-8").replace("'feedback_triaged'", "'x_dropped'")}, "", "U2 platform-actions.html"),
    ]
    for name, files, extra, want in synthetic:
        got = check_static(files, extra, run_scope=False)
        if not any(g.startswith(want) for g in got):
            fails.append(f"static mutant '{name}' was not caught (got {got[:2]})")
    # U5: a use whose client is not in scope, in a scratch page the checker reads
    scratch = ROOT / ".tmp" / "whuse_scope_mutant.html"
    scratch.parent.mkdir(exist_ok=True)
    scratch.write_text("<script>function f(){ whUse(dbx, 'probe'); }</script>", encoding="utf-8")
    r = subprocess.run(["node", "tools/check_whuse_scope.mjs", str(scratch.relative_to(ROOT))], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode == 0 or "NOT IN SCOPE" not in r.stdout:
        fails.append(f"U5 mutant (a client out of scope) was not caught: {r.stdout.strip()[-160:]}")
    scratch.unlink(missing_ok=True)

    p, why = pick()
    if not p:
        fails.append(f"live self-test could not pick its people: {why}")
        return fails
    res, err = run_live(p)
    if err or any(res.values()):
        fails.append(f"the clean live run is not green: {err or {k: v for k, v in res.items() if v}}")
    _, binder, _ = psql("select pg_get_functiondef('public.bind_analytics_events_submitter()'::regprocedure);")
    _, rollup, _ = psql("select pg_get_functiondef('public.founder_feature_use(integer)'::regprocedure);")
    for name, probe, ddl in live_mutants(binder.strip(), rollup.strip()):
        if not ddl:
            fails.append(f"mutant '{name}' did not apply (the function text it edits has drifted)")
            continue
        res, err = run_live(p, ddl)
        if err:
            fails.append(f"mutant '{name}' broke the probe transaction instead of failing a probe: {err[-200:]}")
        elif not res.get(probe):
            fails.append(f"mutant '{name}' left {probe} green - the probe has no teeth")
    return fails


def main() -> int:
    as_json = "--json" in sys.argv
    if "--self-test" in sys.argv:
        fails = self_test()
        print(json.dumps({"self_test": "FAIL" if fails else "PASS", "fails": fails}, indent=1) if as_json else
              ("SELF-TEST PASS (9 static mutants and the scope mutant caught; 7 live mutants each turn their probe red; "
               "the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails)))
        return 1 if fails else 0
    issues = check_static()
    p, why = pick()
    if not p:
        issues.append(f"LIVE could not run: {why}")
    else:
        live, err = run_live(p)
        if err:
            issues.append(f"LIVE probe transaction failed: {err}")
        for probe, probs in live.items():
            issues += [f"{probe}: {x}" for x in probs]
    if as_json:
        print(json.dumps({"validator": "usage_events", "status": "FAIL" if issues else "PASS", "issues": issues}, indent=1))
    else:
        print("Usage events (SL L3): a page's use is recorded as events someone can count, under an identity the database decided")
        for i in issues:
            print("  [FAIL] " + i)
        print(f"  PASS - static U1-U8 over {len(USES) + len(RETIRED)} pages; live V1-V4 as a visitor, a member and an admin"
              if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
