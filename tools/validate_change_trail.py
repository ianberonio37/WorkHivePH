"""validate_change_trail.py - SL L2 (2026-10-21): a change to shared state leaves WHO, WHAT, WHICH and WHEN, on every path
that makes it, in words a person reads.

Measured on the 21 L2 pages: an API key created or revoked, an integration's endpoint and credentials changed, a project
item reassigned, a report recipient removed, a PM task added, an RCM strategy written, a shift plan published, a service
request moved on, a provider's service areas changed - each left nothing saying who did it; closing a logbook entry was
trailed on one page and not on the other that does it; a member who deactivated simply vanished from the roster; a top-up
recorded WHEN it was decided and not WHO. Migration 20261021000001 writes the trail in the database (one function,
audit_shared_change, attached per table for the events a person decides - never the bookkeeping beside them), and this
gate holds it.

STATIC (the migrations, no database)
  S1 the generic trail is attached exactly where EXPECTED says (events, columns, thing, label) and on NO table in
     FORBIDDEN: a table a page or another trigger already trails (a second row for one change makes the trail say
     everything twice), or rows only two parties may read (a hive trail would show them to supervisors their own policy
     keeps out).
  S2 the function copies no value except a STATE column's (boolean / status / availability / decision), and a save that
     changed nothing writes nothing.
  S3 deactivate_my_account writes its trail BEFORE the statement that erases the person's name.
  S4 the logbook close, top-up decider and feedback triage triggers are created.
LIVE (the local database; one rolled-back transaction; people and rows picked from the data, so a reseed cannot break it)
  L1 the triggers in pg_trigger match EXPECTED, and none sits on a FORBIDDEN table.
  L2 as a real supervisor: an API key turned off, a shift plan published, a project item renamed to a long title, an
     integration's credentials rotated -> one row each with the actor bound to the person, the thing's own name, the
     changed column NAMES and a `to` only for a state column (the credentials row carries no value); a no-op save and
     sync bookkeeping write nothing.
  L3 a logbook entry closed by its author -> close_logbook_entry naming the machine.
  L4 a member deactivating -> one deactivated_account row per active hive, under their real name; erased after.
  L5 a marketplace admin rejecting a top-up -> verified_by + verified_at; triaging feedback -> triaged_by + triaged_at;
     each decision lands ONCE in platform_audit_log, bound to the admin's account and named - and in no hive's trail
     (platform-actions used to write it into the operator's own hive, where an unrelated hive's supervisors read it).
SELF-TEST (--self-test): the parser against synthetic migrations, then every live probe against a MUTANT inside its own
rolled-back transaction - each mutant must turn the probe it targets red, and the clean run must stay green.

    python tools/validate_change_trail.py [--self-test] [--json]
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

# table -> (events, update-of columns or None for every column, thing, label)
EXPECTED = {
    "project_items":       ({"insert", "delete", "update"}, {"title", "status", "owner_name", "notes", "wbs_code"}, "project item", "title"),
    "project_links":       ({"insert"}, None, "project link", "label"),
    "projects":            ({"insert"}, None, "project", "name"),
    "report_contacts":     ({"insert", "update", "delete"}, None, "report recipient", "name"),
    "integration_configs": ({"insert", "delete", "update"}, {"system_type", "label", "endpoint_url", "auth_method", "sync_freq", "auth_token"}, "integration setting", "label"),
    "api_keys":            ({"insert", "delete", "update"}, {"enabled", "label"}, "API key", "label"),
    "rcm_strategies":      ({"insert", "update"}, {"decision", "task_text", "rationale"}, "RCM strategy", "task_text"),
    "rcm_fmea_modes":      ({"insert"}, None, "FMEA failure mode", "failure_mode"),
    "pm_scope_items":      ({"insert", "delete"}, None, "PM task", "item_text"),
    "shift_plans":         ({"update"}, {"status"}, "shift plan", "shift_date+shift_window"),
    "service_requests":    ({"update"}, {"status"}, "service request", "custom_scope"),
    "service_providers":   ({"insert", "update"}, {"availability", "categories", "service_areas", "display_name"}, "service provider profile", "display_name"),
    # the hive's focus only: a rename writes hive_renamed from the page's one rename path, and 'name' here would say it twice
    "hives":               ({"update"}, {"intent"}, "hive setting", "name"),
}
FORBIDDEN = {
    "community_posts": "community.html already writes pin_post / flag_post / make_post_public / soft_delete_post / "
                       "restore_post for every one of these changes - a database row too would say each one twice",
    "marketplace_inquiries": "an inquiry is a conversation only its buyer, its seller and a marketplace admin may read - "
                             "a row in the hive's trail would show it to supervisors its own policy keeps out",
}
AUX_TRIGGERS = ("trg_logbook_close_audit", "trg_stamp_topup_decider", "trg_stamp_feedback_triage",
                "trg_audit_platform_decision", "trg_bind_listing_moderator", "trg_bind_shift_plan_publisher")
# a platform decision is recorded in platform_audit_log on each of these tables (not in any hive's trail)
PLATFORM_TABLES = ("service_credit_topups", "marketplace_listings", "marketplace_sellers", "platform_feedback")
STATE_FILTER = "jsonb_typeof(v_new -> k) = 'boolean' or k in ('status', 'availability', 'decision')"
NOOP_GUARD_RE = re.compile(r"if v_changed is null then\s*return null;[^\n]*\n\s*end if;")


# ── static ────────────────────────────────────────────────────────────────────────────────────────────────────────
CREATE_RE = re.compile(
    r"create\s+trigger\s+trg_audit_shared_change\s+after\s+([\s\S]+?)\s+on\s+(?:public\.)?(\w+)\s+"
    r"for\s+each\s+row\s+execute\s+function\s+(?:public\.)?audit_shared_change\s*\(([^)]*)\)", re.I)
DROP_RE = re.compile(r"drop\s+trigger\s+if\s+exists\s+trg_audit_shared_change\s+on\s+(?:public\.)?(\w+)", re.I)


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def parse_events(clause: str) -> tuple[set, set | None]:
    """'insert or delete or update of a, b' -> ({'insert','delete','update'}, {'a','b'})."""
    ev, cols = set(), None
    for part in re.split(r"\s+or\s+", clause.strip(), flags=re.I):
        p = part.strip().lower()
        m = re.match(r"update\s+of\s+(.+)$", p, re.S)
        if m:
            ev.add("update")
            cols = {c.strip() for c in m.group(1).split(",") if c.strip()}
        elif p in ("insert", "update", "delete", "truncate"):
            ev.add(p)
    return ev, cols


def attachments(texts: list[tuple[str, str]]) -> dict:
    """The FINAL attachment per table after every migration in order: table -> (events, cols, thing, label) or None."""
    state: dict = {}
    for _name, sql in texts:
        sql = _strip_comments(sql)
        events = [(m.start(), "drop", m.group(1).lower(), None) for m in DROP_RE.finditer(sql)]
        events += [(m.start(), "create", m.group(2).lower(), m) for m in CREATE_RE.finditer(sql)]
        for _pos, kind, table, m in sorted(events, key=lambda e: e[0]):
            if kind == "drop":
                state[table] = None
                continue
            ev, cols = parse_events(m.group(1))
            args = [a.strip().strip("'") for a in m.group(3).split(",")]
            state[table] = (ev, cols, args[0] if args else "", args[1] if len(args) > 1 else "")
    return state


def last_function_body(texts: list[tuple[str, str]], name: str) -> str:
    body = ""
    rx = re.compile(r"create\s+or\s+replace\s+function\s+(?:public\.)?%s\s*\(" % re.escape(name), re.I)
    for _n, sql in texts:
        for m in rx.finditer(sql):
            end = re.search(r"\$(?:function|\$)?\$\s*;", sql[m.end():])
            seg = sql[m.start(): m.end() + (end.end() if end else 6000)]
            body = seg
    return body


def check_static(texts: list[tuple[str, str]]) -> list[str]:
    bad = []
    att = attachments(texts)
    for table, (ev, cols, thing, label) in EXPECTED.items():
        got = att.get(table)
        if not got:
            bad.append(f"S1 {table}: no audit_shared_change trigger - its changes leave no trail")
            continue
        gev, gcols, gthing, glabel = got
        if gev != ev:
            bad.append(f"S1 {table}: fires on {sorted(gev)}, expected {sorted(ev)}")
        if (gcols or None) != (cols or None):
            bad.append(f"S1 {table}: update of {sorted(gcols or [])}, expected {sorted(cols or []) or 'every column'} "
                       f"(a bookkeeping column here floods the trail; a decision missing from it goes unrecorded)")
        if gthing != thing or glabel != label:
            bad.append(f"S1 {table}: names the thing '{gthing}' by '{glabel}', expected '{thing}' by '{label}'")
    for table, why in FORBIDDEN.items():
        if att.get(table):
            bad.append(f"S1 {table}: has the generic trail attached - {why}")
    fn = last_function_body(texts, "audit_shared_change")
    if not fn:
        bad.append("S2 audit_shared_change is not defined in any migration")
    else:
        if STATE_FILTER not in fn:
            bad.append("S2 audit_shared_change no longer limits the values it copies to state columns "
                       "(an integration's auth token is one of the columns it sees)")
        if not NOOP_GUARD_RE.search(fn):
            bad.append("S2 audit_shared_change writes a row for a save that changed nothing")
    dz = last_function_body(texts, "deactivate_my_account")
    i_ins = dz.lower().find("insert into public.hive_audit_log")
    i_upd = dz.lower().find("update public.worker_profiles")
    if i_ins < 0 or i_upd < 0 or i_ins > i_upd:
        bad.append("S3 deactivate_my_account does not write its trail before erasing the name "
                   "(the actor binding reads the name it erases)")
    allsql = "\n".join(_strip_comments(s) for _n, s in texts).lower()
    for t in AUX_TRIGGERS:
        if not re.search(r"create\s+trigger\s+%s\b" % t, allsql):
            bad.append(f"S4 {t} is not created in any migration")
    return bad


def migration_texts() -> list[tuple[str, str]]:
    return [(p.name, p.read_text(encoding="utf-8", errors="replace")) for p in sorted(MIGRATIONS.glob("*.sql"))]


# ── live ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def psql(sql: str, timeout: int = 180) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At",
                            "-v", "ON_ERROR_STOP=1", "-f", "-"], input=sql, capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, "", str(e)


PICK_SQL = r"""
with sup as (
  select hm.auth_uid, hm.hive_id, coalesce(wp.display_name, hm.worker_name) as actor
    from public.hive_members hm left join public.worker_profiles wp on wp.auth_uid = hm.auth_uid
   where hm.role = 'supervisor' and hm.status = 'active' and hm.auth_uid is not null
     and exists (select 1 from public.api_keys k where k.hive_id = hm.hive_id and k.enabled)
     and exists (select 1 from public.shift_plans x where x.hive_id = hm.hive_id and x.status = 'draft')
     and exists (select 1 from public.project_items x where x.hive_id = hm.hive_id)
     and exists (select 1 from public.report_contacts x where x.hive_id = hm.hive_id)
     and exists (select 1 from public.integration_configs x where x.hive_id = hm.hive_id)
   order by hm.hive_id, hm.auth_uid limit 1),
lg as (
  select l.id, l.auth_uid, l.machine, coalesce(wp.display_name, hm.worker_name) as actor
    from public.logbook l
    join public.hive_members hm on hm.auth_uid = l.auth_uid and hm.hive_id = l.hive_id and hm.status = 'active'
    left join public.worker_profiles wp on wp.auth_uid = l.auth_uid
   where l.status is distinct from 'Closed' and l.deleted_at is null and l.hive_id is not null
   order by l.id limit 1)
select json_build_object(
  'sup', sup.auth_uid, 'hive', sup.hive_id, 'actor', sup.actor,
  'key', (select json_build_object('id', id, 'label', label) from public.api_keys
           where hive_id = sup.hive_id and enabled order by id limit 1),
  'shift', (select json_build_object('id', id, 'name', shift_date::text || ' ' || shift_window) from public.shift_plans
             where hive_id = sup.hive_id and status = 'draft' order by id limit 1),
  'item', (select id from public.project_items where hive_id = sup.hive_id order by id limit 1),
  'contact', (select id from public.report_contacts where hive_id = sup.hive_id order by id limit 1),
  'integ', (select id from public.integration_configs where hive_id = sup.hive_id order by id limit 1),
  'log', (select json_build_object('id', lg.id, 'uid', lg.auth_uid, 'machine', lg.machine, 'actor', lg.actor) from lg),
  'leaver', (select json_build_object('uid', lg.auth_uid,
               'actors', (select json_agg(coalesce(wp.display_name, hm.worker_name) order by hm.hive_id)
                            from public.hive_members hm left join public.worker_profiles wp on wp.auth_uid = hm.auth_uid
                           where hm.auth_uid = lg.auth_uid and hm.status = 'active')) from lg),
  'admin', (select auth_uid from public.marketplace_platform_admins where auth_uid is not null order by auth_uid limit 1),
  'admin_actor', (select coalesce(wp.display_name, '(unknown)') from public.marketplace_platform_admins pa
                    left join public.worker_profiles wp on wp.auth_uid = pa.auth_uid
                   where pa.auth_uid is not null order by pa.auth_uid limit 1),
  'sup_name', (select wp.display_name from public.worker_profiles wp where wp.auth_uid = sup.auth_uid)
)::text from sup;
"""

LONG_TITLE = "Replace the drive-end bearing on conveyor CV-3, re-align the coupling and log vibration readings for a week"


def _claims(uid: str) -> str:
    return "select set_config('request.jwt.claims', json_build_object('sub', '%s', 'role', 'authenticated')::text, true);" % uid


def probe_sql(p: dict, mutation: str = "") -> str:
    return "\n".join([
        "begin;",
        mutation,
        # the decisions the platform admin makes: seeded fresh, so the probe never depends on what the data holds. The
        # top-up belongs to SOMEONE ELSE - guard_service_topup_status refuses an admin deciding one they are a party to
        "insert into public.service_credit_topups (account_type, account_id, payer_auth_uid, amount, gcash_ref) "
        f"values ('consumer', '{p['sup']}', '{p['sup']}', 100, '900000001') returning id as topup \\gset",
        "insert into public.platform_feedback (kind, subject, body) values ('idea', 'L2 probe', 'L2 probe') returning id as fb \\gset",
        "set local role authenticated;",
        _claims(p["sup"]),
        f"update public.api_keys set enabled = false where id = '{p['key']['id']}';",
        f"update public.shift_plans set status = 'published' where id = '{p['shift']['id']}';",
        f"update public.project_items set title = '{LONG_TITLE}' where id = '{p['item']}';",
        f"update public.report_contacts set name = name where id = '{p['contact']}';",
        f"update public.integration_configs set last_sync_status = 'ok' where id = '{p['integ']}';",
        f"update public.integration_configs set auth_token = 'rotated-' || md5(random()::text) where id = '{p['integ']}';",
        _claims(p["log"]["uid"]),
        f"update public.logbook set status = 'Closed' where id = '{p['log']['id']}';",
        _claims(p["admin"]),
        "update public.service_credit_topups set status = 'rejected' where id = :'topup';",
        "update public.platform_feedback set status = 'triaged' where id = :'fb';",
        _claims(p["leaver"]["uid"]),
        "select public.deactivate_my_account();",
        "reset role;",
        "select set_config('request.jwt.claims', '', true);",
        "select '@@ROWS|' || coalesce(json_agg(json_build_object('a', action, 'actor', actor, 'tid', target_id, "
        "'t', target_name, 'm', meta))::text, '[]') from public.hive_audit_log where created_at = now();",
        "select '@@TOPUP|' || json_build_object('by', verified_by, 'at', verified_at is not null)::text "
        "from public.service_credit_topups where id = :'topup';",
        "select '@@FB|' || json_build_object('by', triaged_by, 'at', triaged_at is not null)::text "
        "from public.platform_feedback where id = :'fb';",
        f"select '@@NAME|' || coalesce((select display_name from public.worker_profiles where auth_uid = '{p['leaver']['uid']}'), '');",
        f"select '@@PUBBY|' || coalesce((select published_by from public.shift_plans where id = '{p['shift']['id']}'), '');",
        "select '@@TRG|' || coalesce(json_agg(json_build_object('t', c.relname, 'def', pg_get_triggerdef(t.oid)))::text, '[]') "
        "from pg_trigger t join pg_class c on c.oid = t.tgrelid join pg_proc f on f.oid = t.tgfoid "
        "where not t.tgisinternal and f.proname = 'audit_shared_change';",
        "select '@@AUX|' || coalesce(json_agg(t.tgname)::text, '[]') from pg_trigger t "
        f"where t.tgname in ({', '.join(repr(x) for x in AUX_TRIGGERS)});",
        "select '@@PLATTRG|' || coalesce(json_agg(c.relname)::text, '[]') from pg_trigger t join pg_class c on c.oid = t.tgrelid "
        "where t.tgname = 'trg_audit_platform_decision';",
        "select '@@IDS|' || json_build_object('topup', :'topup', 'fb', :'fb', 'amount', (select amount::text from public.service_credit_topups where id = :'topup'))::text;",
        "select '@@PLAT|' || coalesce(json_agg(json_build_object('a', action, 'actor', actor, 'tid', target_id, "
        "'t', target_name, 'm', meta))::text, '[]') from public.platform_audit_log where created_at = now();",
        "rollback;",
    ])


def _out(stdout: str) -> dict:
    out = {}
    for line in stdout.splitlines():
        if line.startswith("@@"):
            k, _, v = line[2:].partition("|")
            out[k] = v
    return out


def judge(p: dict, out: dict) -> dict:
    """probe -> list of problems ([] = the probe holds)."""
    res = {k: [] for k in ("L1", "KEY", "SHIFT", "ITEM", "NOOP", "CREDENTIALS", "CLOSE", "LEAVE", "TOPUP", "FEEDBACK", "PLATFORM")}
    if "ROWS" not in out:
        return {k: ["the probe transaction did not complete"] for k in res}
    rows = json.loads(out["ROWS"])
    by = lambda tid: [r for r in rows if r.get("tid") == str(tid)]  # noqa: E731

    trg = {}
    for t in json.loads(out.get("TRG", "[]")):
        m = re.search(r"AFTER (.+?) ON public\.\w+ FOR EACH ROW EXECUTE FUNCTION audit_shared_change\((.*)\)$", t["def"])
        if m:
            ev, cols = parse_events(m.group(1))
            args = [a.strip().strip("'") for a in m.group(2).split(",")]
            trg[t["t"]] = (ev, cols, args[0], args[1] if len(args) > 1 else "")
    for table, want in EXPECTED.items():
        got = trg.get(table)
        if got is None:
            res["L1"].append(f"{table}: no trigger")
        elif (got[0], got[1] or None, got[2], got[3]) != (want[0], want[1] or None, want[2], want[3]):
            res["L1"].append(f"{table}: {got} != {want}")
    for table in FORBIDDEN:
        if table in trg:
            res["L1"].append(f"{table}: carries the generic trail ({FORBIDDEN[table]})")
    aux = set(json.loads(out.get("AUX", "[]")))
    for t in AUX_TRIGGERS:
        if t not in aux:
            res["L1"].append(f"{t} is missing")

    def one(probe, tid, action, actor, target, changed=None, to=None, no_to=False):
        rs = by(tid)
        if len(rs) != 1:
            res[probe].append(f"{len(rs)} trail row(s) for the change, expected 1")
            return
        r = rs[0]
        m = r.get("m") or {}
        if r.get("a") != action:
            res[probe].append(f"action {r.get('a')!r}, expected {action!r}")
        if r.get("actor") != actor:
            res[probe].append(f"actor {r.get('actor')!r}, expected the person's own name {actor!r}")
        if target is not None and r.get("t") != target:
            res[probe].append(f"name {r.get('t')!r}, expected {target!r}")
        if changed is not None and m.get("changed") != changed:
            res[probe].append(f"changed {m.get('changed')!r}, expected {changed!r}")
        if to is not None and m.get("to") != to:
            res[probe].append(f"to {m.get('to')!r}, expected {to!r}")
        if no_to and "to" in m:
            res[probe].append(f"copied a value it must not: {m.get('to')!r}")

    one("KEY", p["key"]["id"], "change_api_key", p["actor"], p["key"]["label"], ["enabled"], {"enabled": False})
    # publishing also stamps published_by / published_at (bound by trg_bind_shift_plan_publisher): the change is the
    # status, and those two columns are its stamps - nothing else may move
    one("SHIFT", p["shift"]["id"], "change_shift_plan", p["actor"], p["shift"]["name"], None, {"status": "published"})
    _sh = by(p["shift"]["id"])
    if len(_sh) == 1 and not ({"status"} <= set((_sh[0].get("m") or {}).get("changed") or []) <= {"status", "published_at", "published_by"}):
        res["SHIFT"].append(f"changed {(_sh[0].get('m') or {}).get('changed')!r}: expected the status and its two stamps only")
    if out.get("PUBBY") != p["actor"]:
        res["SHIFT"].append(f"the plan says it was published by {out.get('PUBBY')!r}, not the account that published it ({p['actor']!r})")
    title = LONG_TITLE if len(LONG_TITLE) <= 80 else LONG_TITLE[:79] + "…"
    one("ITEM", p["item"], "change_project_item", p["actor"], title, ["title"], no_to=True)
    if by(p["contact"]):
        res["NOOP"].append(f"a save that changed nothing wrote {len(by(p['contact']))} trail row(s)")
    one("CREDENTIALS", p["integ"], "change_integration_setting", p["actor"], None, ["auth_token"], no_to=True)
    one("CLOSE", p["log"]["id"], "close_logbook_entry", p["log"]["actor"], p["log"]["machine"])
    leave = [r for r in rows if r.get("a") == "deactivated_account"]
    want = sorted(p["leaver"]["actors"] or [])
    if sorted(r.get("actor") for r in leave) != want:
        res["LEAVE"].append(f"deactivation rows by {sorted(r.get('actor') for r in leave)!r}, expected one per hive by {want!r}")
    if out.get("NAME") != "Deleted user":
        res["LEAVE"].append(f"the name was not erased after the trail ({out.get('NAME')!r})")
    tp = json.loads(out.get("TOPUP") or "{}")
    if tp.get("by") != p["admin"] or not tp.get("at"):
        res["TOPUP"].append(f"the top-up decision recorded {tp!r}, expected verified_by = the admin and a time")
    fb = json.loads(out.get("FB") or "{}")
    if fb.get("by") != p["admin"] or not fb.get("at"):
        res["FEEDBACK"].append(f"the triage recorded {fb!r}, expected triaged_by = the admin and a time")
    # the platform's own trail: each decision once, bound to the admin's account, named, and in NO hive's trail
    plat_tables = set(json.loads(out.get("PLATTRG", "[]")))
    for t in PLATFORM_TABLES:
        if t not in plat_tables:
            res["L1"].append(f"{t}: no trg_audit_platform_decision - a platform decision there is recorded nowhere")
    ids = json.loads(out.get("IDS") or "{}")
    plat = json.loads(out.get("PLAT", "[]"))
    want = [("reject_topup", ids.get("topup"), f"PHP {ids.get('amount')} top-up from {p.get('sup_name') or 'an account'}"),
            ("triage_feedback", ids.get("fb"), "L2 probe")]
    for action, tid, name in want:
        rs = [r for r in plat if r.get("tid") == tid]
        if len(rs) != 1:
            res["PLATFORM"].append(f"{action}: {len(rs)} platform trail row(s), expected 1")
            continue
        r = rs[0]
        if r.get("a") != action:
            res["PLATFORM"].append(f"action {r.get('a')!r}, expected {action!r}")
        if r.get("actor") != p.get("admin_actor"):
            res["PLATFORM"].append(f"{action}: actor {r.get('actor')!r}, expected the admin's own name {p.get('admin_actor')!r}")
        if r.get("t") != name:
            res["PLATFORM"].append(f"{action}: name {r.get('t')!r}, expected {name!r}")
    if any(r.get("tid") in (ids.get("topup"), ids.get("fb")) for r in rows):
        res["PLATFORM"].append("a platform decision was written into a hive's trail - another hive's supervisors would read it")
    return res


def pick() -> tuple[dict | None, str]:
    code, out, err = psql(PICK_SQL)
    line = next((l for l in out.splitlines() if l.startswith("{")), "")
    if code != 0 or not line:
        return None, (err or "no supervisor with api keys, a draft shift plan, project items, report recipients and "
                             "an integration, or no open logbook entry with a member author").strip()[:300]
    p = json.loads(line)
    missing = [k for k in ("key", "shift", "item", "contact", "integ", "log", "leaver", "admin") if not p.get(k)]
    if missing:
        return None, f"the data lacks {missing} - reseed (test-data-seeder) before this gate can run"
    return p, ""


def run_live(p: dict, mutation: str = "") -> tuple[dict, str]:
    code, out, err = psql(probe_sql(p, mutation))
    if code != 0:
        return {}, (err or out).strip()[-600:]
    return judge(p, _out(out)), ""


# ── self-test ─────────────────────────────────────────────────────────────────────────────────────────────────────
def mutants(fn_def: str) -> list[tuple[str, str, str]]:
    """(name, the probe it must turn red, DDL) - each runs inside the probe's own rolled-back transaction."""
    copy_all = fn_def.replace(STATE_FILTER, "true")
    no_guard = NOOP_GUARD_RE.sub("", fn_def, count=1)
    after_rename = """create or replace function public.deactivate_my_account() returns void language plpgsql security definer
set search_path to 'pg_catalog', 'public' as $m$
declare uid uuid := auth.uid();
begin
  update public.worker_profiles set display_name = 'Deleted user', email = null, deactivated_at = now() where auth_uid = uid;
  insert into public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  select hm.hive_id, hm.worker_name, 'deactivated_account', 'worker_profiles', uid::text, hm.worker_name, '{}'::jsonb
    from public.hive_members hm where hm.auth_uid = uid and hm.status = 'active';
  update public.hive_members set status = 'deactivated' where auth_uid = uid;
end $m$;"""
    return [
        ("copy every changed value", "CREDENTIALS", copy_all + ";" if copy_all != fn_def else ""),
        ("no-op guard removed", "NOOP", no_guard + ";" if no_guard != fn_def else ""),
        ("API key trigger dropped", "KEY", "drop trigger trg_audit_shared_change on public.api_keys;"),
        ("trail attached to community posts", "L1",
         "create trigger trg_audit_shared_change after update of pinned on public.community_posts for each row "
         "execute function public.audit_shared_change('post', 'content');"),
        ("deactivation trail written after the rename", "LEAVE", after_rename),
        ("top-up decider stamp dropped", "TOPUP", "drop trigger trg_stamp_topup_decider on public.service_credit_topups;"),
        ("logbook close trail dropped", "CLOSE", "drop trigger trg_logbook_close_audit on public.logbook;"),
        ("feedback triage stamp dropped", "FEEDBACK", "drop trigger trg_stamp_feedback_triage on public.platform_feedback;"),
        ("platform decision trail dropped", "PLATFORM", "drop trigger trg_audit_platform_decision on public.service_credit_topups;"),
        ("shift plan publisher left to the browser", "SHIFT", "drop trigger trg_bind_shift_plan_publisher on public.shift_plans;"),
    ]


def self_test() -> list[str]:
    fails = []
    base = migration_texts()
    clean = check_static(base)
    if clean:
        fails.append(f"static is not clean on the real migrations: {clean[:3]}")
    synthetic = [
        ("community_posts attached",
         "create trigger trg_audit_shared_change after update of pinned on public.community_posts for each row "
         "execute function public.audit_shared_change('post', 'content');", "S1 community_posts"),
        ("api_keys call counter",
         "drop trigger if exists trg_audit_shared_change on public.api_keys;\ncreate trigger trg_audit_shared_change "
         "after insert or delete or update of enabled, label, call_count on public.api_keys for each row execute "
         "function public.audit_shared_change('API key', 'label');", "S1 api_keys"),
        ("api_keys trigger dropped", "drop trigger if exists trg_audit_shared_change on public.api_keys;", "S1 api_keys"),
        ("deactivation reordered",
         "create or replace function public.deactivate_my_account() returns void language plpgsql as $function$ begin "
         "update public.worker_profiles set display_name = 'Deleted user'; insert into public.hive_audit_log (hive_id) "
         "values (null); end $function$;", "S3"),
    ]
    for name, sql, want in synthetic:
        got = check_static(base + [("zzzz_mutant.sql", sql)])
        if not any(g.startswith(want) for g in got):
            fails.append(f"static mutant '{name}' was not caught (got {got[:2]})")
    p, why = pick()
    if not p:
        fails.append(f"live self-test could not pick its people: {why}")
        return fails
    res, err = run_live(p)
    if err or any(res.values()):
        fails.append(f"the clean live run is not green: {err or {k: v for k, v in res.items() if v}}")
    code, fn_def, err = psql("select pg_get_functiondef('public.audit_shared_change()'::regprocedure);")
    for name, probe, ddl in mutants(fn_def.strip() if code == 0 else ""):
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
              ("SELF-TEST PASS (static mutants caught; 10 live mutants each turn their probe red; the clean run is green)"
               if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails)))
        return 1 if fails else 0
    issues = check_static(migration_texts())
    p, why = pick()
    live = {}
    if not p:
        issues.append(f"LIVE could not run: {why}")
    else:
        live, err = run_live(p)
        if err:
            issues.append(f"LIVE probe transaction failed: {err}")
        for probe, probs in live.items():
            issues += [f"{probe}: {x}" for x in probs]
    if as_json:
        print(json.dumps({"validator": "change_trail", "status": "FAIL" if issues else "PASS", "issues": issues}, indent=1))
    else:
        print("Change trail (SL L2): a shared change leaves who, what, which and when - on every path")
        for i in issues:
            print("  [FAIL] " + i)
        print("  PASS - static S1-S4; live L1-L5 as a supervisor, an author, a leaver and a marketplace admin"
              if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
