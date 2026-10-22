"""validate_told_failures_logged.py - SL L4 (2026-10-21): when a page fails, the sentence it showed the person is logged
beside the code, under an identity the database decided.

Measured on the 32 L4 pages: client_errors held 390 rows and 383 were the uncaught net. A failure a person was TOLD about
- a refused save, a list that could not load, an access check that could not be asked - left no row: pages show the
sentence and log nothing, and the one logger kept the error's technical message, never what the person read. Identity
on a row was the device's claim. Migration 20261021000003 adds `shown` and `code` and binds identity; utils.js whTold
logs a told sentence once per load, from every place a failure is told.

STATIC (no database)
  T1 utils.js whTold records the sentence (capped), its code and technical message, once per sentence per load, holds a
     sentence told before the page has a client, and never throws.
  T2 the four sentence makers log what they return: whWriteError / whReadError are wrappers over their sentence
     functions; whAiError and whFnError are wrapped once (whToldMakers).
  T3 the other shared tellers log: the failure notices (_whShowNotice - session, permission, connection, hive context;
     never the update / live information notices), the inline list error (whListError), the access-check sentence
     (whAdminCheckOfflineText).
  T4 every page's own toast is read: the watcher covers the hosts the L4 pages' showToast functions write into.
  T5 the shipped failure classifier answers a fixed case list right (failures, information, input guidance).
  T6 a row-level-security or grant refusal is Postgres-shaped (_WH_RAW_PG), so it is never shown verbatim.
  T7 the fixes the walk found stay made: inventory queues only a network-shaped failure (a refusal was queued, replayed
     and followed by "submitted for supervisor approval"); resume's cloud save words a refusal through the shared
     sentence; assistant logs its rating and greeting failures; platform-actions logs its access sentence.
  T8 the newest migration for client_errors binds the reporter and admits a visitor's told-* row.
LIVE (the local database; one rolled-back transaction)
  V1 a member's told row with another name and a hive they are not in is KEPT, bound to their own name and no hive
     (before the binder, the membership check refused it and the failure was lost).
  V2 a visitor's told row is admitted with no identity; a visitor's row with any other context is refused.
  V3 the binder trigger is present and enabled.
SELF-TEST (--self-test): static mutants (synthetic files) and live mutants (inside the probe's rolled-back transaction).

    python tools/validate_told_failures_logged.py [--self-test] [--json]
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
WATCHED = ["toast", "dp-toast", "hive-toast", "toast-container", "wh-toast", "wh-auth-toast"]
# hosts that only ever carry information (community's undo toast says only "Post deleted ... Undo")
INFO_HOSTS = {"community.html": {"undo-toast"}}
L4_PAGES = ["achievements.html", "ai-quality.html", "alert-hub.html", "analytics-report.html", "analytics.html",
            "asset-hub.html", "assistant.html", "audit-log.html", "community.html", "dayplanner.html",
            "engineering-design.html", "founder-console.html", "hive.html", "index.html", "integrations.html",
            "inventory.html", "logbook.html", "marketplace-admin.html", "marketplace-seller-profile.html",
            "marketplace-seller.html", "marketplace.html", "ph-intelligence.html", "plant-connections.html",
            "platform-actions.html", "pm-scheduler.html", "project-manager.html", "project-report.html", "public-feed.html",
            "report-sender.html", "resume.html", "shift-brain.html", "skillmatrix.html"]
CASES = [
    ("The stock was NOT deducted. Nothing changed - check the quantity and try again.", True),
    ("Popup blocked. Allow popups for asset-hub.", True),
    ("This connector was changed by someone else, reload and re-edit.", True),
    ("Supervisors only.", True),
    ("That asset was already handled by another supervisor.", True),
    ("You are offline. Accepting a job needs a connection - another provider may already have taken it.", True),
    ("Couldn’t load your skill matrix. Please retry.", True),
    ("Could not load the parts list.", True),
    ("API key revoked. Anything still using it is refused from now on.", False),
    ("Filed. Verification is a manual check by the founder, so it is not instant - your pending top-up stays listed", False),
    ("Removed 3 unavailable listings from your saved list.", False),
    ("Tell us what went wrong, so it can be reviewed.", False),
    ("Asset approved.", False),
    ("Pick a reason - it is what your supervisor triages by.", False),
]
FIXES = [
    ("inventory.html", "a refused part is not queued as a network hiccup",
     r"const _isNet = /fetch\|network\|load failed\|connection\|timeout/i\.test\(insertErr\.message \|\| ''\);\s*if \(_isNet && _ensureInvQueue\(\)\)"),
    ("resume.html", "a refused cloud save is worded by the shared sentence, not the database",
     r"whWriteError\(err, 'Not backed up to your account\.'\)"),
    ("assistant.html", "a rating that did not land is logged", r"whTold\('rating', note\.textContent, _fbLastErr\)"),
    ("assistant.html", "a greeting that could not reach the records is logged", r"whTold\('read', recordsNote, lc && lc\.error\)"),
    ("platform-actions.html", "the access-check sentence is logged", r"whTold\('access', cg\.textContent\)"),
]


def strip_js_comments(src: str) -> str:
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
        out.append(c); i += 1
    return out and "".join(out) or ""


def classify_cases(utils: str) -> list[str]:
    """Run the SHIPPED classifier (the regex text in utils.js) on CASES through node."""
    ci = re.search(r"var _WH_FAIL_CI = (new RegExp\([\s\S]*?'i'\));", utils)
    cs = re.search(r'var _WH_FAIL_CS = (new RegExp\([\s\S]*?"\));', utils)
    if not ci or not cs:
        return ["T5 the failure classifier (_WH_FAIL_CI / _WH_FAIL_CS) is gone from utils.js"]
    js = ("const CI = " + ci.group(1) + "; const CS = " + cs.group(1) + ";\n"
          "const cases = " + json.dumps(CASES) + ";\n"
          "const isF = (t) => !/what went wrong/i.test(t) && (CI.test(t) || CS.test(t));\n"
          "console.log(JSON.stringify(cases.filter(([t, want]) => isF(t) !== want).map(([t]) => t)));")
    try:
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=60)
        wrong = json.loads(r.stdout.strip() or "[]") if r.returncode == 0 else ["(node: " + (r.stderr or "")[-120:] + ")"]
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        wrong = [f"(could not run: {e})"]
    return [f"T5 the classifier answers {len(wrong)} case(s) wrong: {[w[:60] for w in wrong[:3]]}"] if wrong else []


def last_migration_with(pattern: str) -> tuple[str, str]:
    found = ("", "")
    rx = re.compile(pattern, re.I)
    for f in sorted(MIGRATIONS.glob("*.sql")):
        t = f.read_text(encoding="utf-8", errors="replace")
        if rx.search(t):
            found = (f.name, t)
    return found


def check_static(files: dict[str, str] | None = None) -> list[str]:
    def text(rel: str) -> str:
        if files and rel in files:
            return files[rel]
        return (ROOT / rel).read_text(encoding="utf-8", errors="replace")

    issues = []
    raw_utils = text("utils.js")
    u = strip_js_comments(raw_utils)
    m = re.search(r"function whTold\(kind, sentence, err\) \{(.*?)\n\}", u, re.S)
    body = m.group(1) if m else ""
    if not body:
        issues.append("T1 utils.js has no whTold(kind, sentence, err)")
    else:
        for need, why in (("shown: shown.slice(0, 400)", "records the sentence it was given"),
                          ("code: code ? code.slice(0, 60) : null", "records the code beside it"),
                          ("_whToldSeen[shown]", "logs one row per sentence per load"),
                          ("_whToldPending.push(", "holds a sentence told before the page has a client"),
                          ("context: 'told-'", "writes a told-* context the visitor policy admits")):
            if need not in body:
                issues.append(f"T1 whTold no longer {why}")
    if not re.search(r"function whWriteError\(err, fallback\) \{ var s = _whWriteErrorText\(err, fallback\); whTold\('write', s, err\); return s; \}", u):
        issues.append("T2 whWriteError no longer logs the sentence it returns")
    if not re.search(r"function whReadError\(err, what\) \{ var s = _whReadErrorText\(err, what\); whTold\('read', s, err\); return s; \}", u):
        issues.append("T2 whReadError no longer logs the sentence it returns")
    wm = re.search(r"\(function whToldMakers\(\) \{(.*?)\}\)\(\);", u, re.S)
    if not wm or "whTold('ai', s, err)" not in wm.group(1) or "whTold('fn', s, err)" not in wm.group(1):
        issues.append("T2 whAiError / whFnError are no longer wrapped to log what they return")
    sn = re.search(r"function _whShowNotice\(id, msg, bottomPx\) \{(.*?)\n\}", u, re.S)
    if not sn or "id !== 'wh-update-notice' && id !== 'wh-live-notice' && typeof whTold === 'function') whTold('notice', msg)" not in sn.group(1):
        issues.append("T3 the shared failure notices are no longer logged (or the information notices are)")
    le = re.search(r"function whListError\(el, message, onRetry\) \{(.*?)\n\}", u, re.S)
    if not le or "whTold('list'" not in le.group(1):
        issues.append("T3 the inline list error no longer logs the sentence it shows")
    # SL RL2 (2026-10-22) passes the lookup's error in (a limit says its wait), so the signature grew a parameter
    ac = re.search(r"function whAdminCheckOfflineText\(what(?:, err)?\) \{(.*?)\n\}", u, re.S)
    if not ac or "whTold('access', s)" not in ac.group(1):
        issues.append("T3 the access-check sentence no longer logs itself")
    ids = re.search(r"var IDS = \[([^\]]*)\];", u)
    watched = re.findall(r"'([a-z-]+)'", ids.group(1)) if ids else []
    for need in WATCHED:
        if need not in watched:
            issues.append(f"T4 the toast watcher no longer reads #{need}")
    for page in L4_PAGES:
        src = text(page)
        ids = set(re.findall(r"getElementById\('([a-z-]*toast[a-z-]*)'\)", src)) | set(re.findall(r"\.id = '([a-z-]*toast[a-z-]*)'", src))
        if re.search(r"\$\('toast-container'\)", src):
            ids.add("toast-container")
        # a part of a host (#toast-text inside #toast, #undo-toast-btn inside #undo-toast) is read with its host
        hosts = {h for h in ids if not any(h.startswith(o + "-") for o in ids | set(watched) if o != h)}
        unread = sorted(h for h in hosts if h not in watched and h not in INFO_HOSTS.get(page, ()))
        if unread:
            issues.append(f"T4 {page} shows toasts in #{', #'.join(unread)}, which the watcher does not read")
    issues += classify_cases(raw_utils)
    rp = re.search(r"var _WH_RAW_PG = /(.*?)/i;", u)
    if not rp or "violates row-level security" not in rp.group(1) or "permission denied for" not in rp.group(1):
        issues.append("T6 a row-level-security / grant refusal is no longer treated as Postgres-shaped (shown verbatim)")
    for page, what, pat in FIXES:
        if not re.search(pat, text(page)):
            issues.append(f"T7 {page}: {what} - no longer")
    fname, mig = last_migration_with(r"bind_client_errors_reporter")
    low = re.sub(r"\s+", " ", mig.lower())
    for need, why in (("create trigger trg_bind_client_errors_reporter before insert on public.client_errors", "binds the reporter"),
                      ("add column if not exists shown text", "keeps the shown sentence"),
                      ("or context like 'told-%'", "admits a visitor's told row")):
        if need not in low:
            issues.append(f"T8 {fname or 'no migration'}: client_errors no longer {why}")
    return issues


def psql(sql: str, timeout: int = 120) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At",
                            "-v", "ON_ERROR_STOP=1", "-f", "-"], input=sql, capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, "", str(e)


PICK_SQL = r"""
select json_build_object('member', m.auth_uid, 'hive', m.hive_id,
  'name', (select wp.display_name from public.worker_profiles wp where wp.auth_uid = m.auth_uid limit 1),
  'foreign_hive', (select h.id from public.hives h where not exists (select 1 from public.hive_members x
                    where x.hive_id = h.id and x.auth_uid = m.auth_uid and x.status = 'active') order by h.id limit 1))::text
from public.hive_members m
where m.status = 'active' and m.auth_uid is not null
  and exists (select 1 from public.worker_profiles wp where wp.auth_uid = m.auth_uid and wp.display_name is not null)
order by m.hive_id, m.auth_uid limit 1;
"""


def probe_sql(p: dict, mutation: str = "") -> str:
    m, fh = p["member"], p["foreign_hive"]
    return "\n".join([
        "begin;", mutation,
        "select 'TRG|' || coalesce((select tgenabled::text from pg_trigger where tgrelid = 'public.client_errors'::regclass "
        "and tgname = 'trg_bind_client_errors_reporter'), 'missing');",
        # V1 - a member, another name, a hive they are not in. Each insert is its own block, so a refusal is a
        # finding the judge reads, never an error that ends the probe.
        "select set_config('request.jwt.claims', json_build_object('sub', '%s', 'role', 'authenticated')::text, true);" % m,
        "set local role authenticated;",
        "do $$ begin insert into public.client_errors (context, message, shown, code, worker_name, hive_id, page) values "
        f"('told-write', 'probe', 'WH-L4-PROBE member sentence', '42501', 'Someone Else', '{fh}', '/workhive/probe.html'); "
        "exception when others then raise notice 'MEMBER|refused %', sqlerrm; end $$;",
        "reset role;",
        # V2 - a visitor: a told row (admitted, no identity) and any other context (refused)
        "select set_config('request.jwt.claims', '{\"role\":\"anon\"}', true);",
        "set local role anon;",
        "do $$ begin insert into public.client_errors (context, message, shown, worker_name, hive_id, page) values "
        f"('told-read', 'probe', 'WH-L4-PROBE visitor sentence', 'Forged Name', '{p['hive']}', '/workhive/probe.html'); "
        "exception when others then raise notice 'VISITOR|refused %', sqlerrm; end $$;",
        "do $$ begin insert into public.client_errors (context, message, shown, page) values ('whatever', 'probe', "
        "'WH-L4-PROBE visitor other', '/workhive/probe.html'); raise notice 'OTHER|admitted'; exception when others then "
        "raise notice 'OTHER|refused'; end $$;",
        "reset role;",
        "select 'ROW|' || json_build_object('s', shown, 'uid', auth_uid, 'hive', hive_id, 'name', worker_name)::text "
        "from public.client_errors where shown like 'WH-L4-PROBE%' order by shown;",
        "rollback;",
    ])


def judge(p: dict, out: str, err: str) -> dict:
    res = {"V1": [], "V2": [], "V3": []}
    rows, trg = {}, None
    for line in out.splitlines():
        tag, _, val = line.partition("|")
        if tag == "ROW":
            r = json.loads(val); rows[r["s"]] = r
        elif tag == "TRG":
            trg = val.strip()
    other = "admitted" if "OTHER|admitted" in err else ("refused" if "OTHER|refused" in err else None)
    if trg != "O":
        res["V3"].append(f"the reporter binder trigger is {trg or 'not reported'} (O = enabled)")
    mrow = rows.get("WH-L4-PROBE member sentence")
    if not mrow:
        res["V1"].append("a member's told row with a hive they are not in was REFUSED - the failure would be lost")
    else:
        if mrow["uid"] != p["member"]:
            res["V1"].append("a member's told row is not bound to their account")
        if mrow["hive"] is not None:
            res["V1"].append("a member's told row kept a hive they are not a member of")
        if mrow["name"] != p["name"]:
            res["V1"].append(f"a member's told row carries {mrow['name']!r}, not their own name {p['name']!r}")
    vrow = rows.get("WH-L4-PROBE visitor sentence")
    if not vrow:
        res["V2"].append("a visitor's told row was refused")
    elif vrow["uid"] or vrow["hive"] or vrow["name"]:
        res["V2"].append(f"a visitor's told row kept a claimed identity: {vrow}")
    if other != "refused":
        res["V2"].append(f"a visitor's row with any other context was {other or 'not reported'}")
    return res


def pick() -> tuple[dict | None, str]:
    code, out, err = psql(PICK_SQL)
    line = next((l for l in out.splitlines() if l.startswith("{")), "")
    if code != 0 or not line:
        return None, (err or "no active member with a profile name").strip()[:200]
    p = json.loads(line)
    if not p.get("foreign_hive"):
        return None, "the data lacks a hive the member is not in - reseed"
    return p, ""


def run_live(p: dict, mutation: str = "") -> tuple[dict, str]:
    code, out, err = psql(probe_sql(p, mutation))
    if code != 0:
        return {}, (err or out).strip()[-500:]
    return judge(p, out, err), ""


def self_test() -> list[str]:
    fails = []
    clean = check_static()
    if clean:
        fails.append(f"static is not clean on the real files: {clean[:3]}")
    utils = (ROOT / "utils.js").read_text(encoding="utf-8")
    inv = (ROOT / "inventory.html").read_text(encoding="utf-8")
    synthetic = [
        ("whWriteError stops logging", {"utils.js": utils.replace("var s = _whWriteErrorText(err, fallback); whTold('write', s, err); return s;", "return _whWriteErrorText(err, fallback);", 1)}, "T2"),
        ("the notices stop logging", {"utils.js": utils.replace("&& typeof whTold === 'function') whTold('notice', msg);", "&& false) whTold('notice', msg);", 1)}, "T3"),
        ("the watcher stops reading #wh-toast", {"utils.js": utils.replace("'wh-toast', 'wh-auth-toast'", "'wh-auth-toast'", 1)}, "T4"),
        ("the classifier loses 'could not'", {"utils.js": utils.replace("\\\\b(could ?n[o']?t|", "\\\\b(", 1)}, "T5"),
        ("RLS shown verbatim again", {"utils.js": utils.replace("violates row-level security|", "", 1)}, "T6"),
        ("inventory queues a refusal again", {"inventory.html": inv.replace("if (_isNet && _ensureInvQueue())", "if (_ensureInvQueue())", 1)}, "T7"),
    ]
    for name, files, want in synthetic:
        if files and all(files[k] == (ROOT / k).read_text(encoding="utf-8") for k in files):
            fails.append(f"static mutant '{name}' did not apply (its anchor text has drifted)")
            continue
        got = check_static(files)
        if not any(g.startswith(want) for g in got):
            fails.append(f"static mutant '{name}' was not caught (got {got[:2]})")
    p, why = pick()
    if not p:
        fails.append(f"live self-test could not pick its people: {why}")
        return fails
    res, err = run_live(p)
    if err or any(res.values()):
        fails.append(f"the clean live run is not green: {err or {k: v for k, v in res.items() if v}}")
    mutants = [
        ("binder trigger dropped", "V1", "drop trigger trg_bind_client_errors_reporter on public.client_errors;"),
        ("visitor policy back to the uncaught contexts only", "V2",
         "drop policy client_errors_insert_anon on public.client_errors; create policy client_errors_insert_anon on public.client_errors "
         "for insert to anon with check ((select auth.uid()) is null and hive_id is null and worker_name is null and auth_uid is null "
         "and context = any (array['uncaught-error', 'unhandled-rejection']));"),
    ]
    for name, probe, ddl in mutants:
        res, err = run_live(p, ddl)
        if err:
            fails.append(f"mutant '{name}' broke the probe transaction: {err[-200:]}")
        elif not res.get(probe):
            fails.append(f"mutant '{name}' left {probe} green - the probe has no teeth")
    return fails


def main() -> int:
    as_json = "--json" in sys.argv
    if "--self-test" in sys.argv:
        fails = self_test()
        print(json.dumps({"self_test": "FAIL" if fails else "PASS", "fails": fails}, indent=1) if as_json else
              ("SELF-TEST PASS (6 static mutants caught; 2 live mutants each turn their probe red; the clean run is green)"
               if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails)))
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
        print(json.dumps({"validator": "told_failures_logged", "status": "FAIL" if issues else "PASS", "issues": issues}, indent=1))
    else:
        print("Told failures logged (SL L4): the sentence a page showed when something failed is logged beside its code")
        for i in issues:
            print("  [FAIL] " + i)
        print(f"  PASS - static T1-T8 over {len(L4_PAGES)} pages; live V1-V3 as a member and a visitor"
              if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
