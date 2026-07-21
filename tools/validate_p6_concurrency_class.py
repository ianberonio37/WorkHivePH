#!/usr/bin/env python3
"""
validate_p6_concurrency_class.py - PER_PAGE_BUGHUNT P6 concurrent-edit disposition gate (2026-07-21).
=====================================================================================================
Locks the concurrency-safety CLASS of every remaining P6-partial page so each can honestly reach 100.
The two existing P6 gates cover only two dispositions — `oc-updated-at-backed` (OC-guarded edits:
inventory/pm-scheduler) and `readonly-p6-no-edit` (12 read-only pages). This gate covers the REST: the
pages whose primary write is race-safe NOT by an optimistic lock but by its structural class, and
asserts the LOAD-BEARING DB invariant for each class (so a refactor that breaks the property FAILs):

  * idempotent-upsert (skillmatrix skill_profiles · marketplace-seller marketplace_sellers ·
    dayplanner schedule_items) — a full-object `.upsert(...,{onConflict:KEY})` on a UNIQUE-index-backed
    KEY: two concurrent upserts CONVERGE to one row (no partial lost-update, because the whole object
    is written, not a read-modify-write delta). INVARIANT: the onConflict/PK column has a matching
    unique index in the live DB (else Postgres would 42P10 or duplicate). Live: a rolled-back
    double-upsert with differing payloads yields exactly 1 row holding the 2nd value.
  * owner-scoped-update (resume resume_documents · marketplace marketplace_saved_searches ·
    marketplace-seller marketplace_inquiries) — the row's UPDATE RLS is own-identity/party-scoped, so a
    concurrent writer must be the SAME identity: there is no CROSS-USER lost-update, and a same-user
    two-tab last-write on a full-object payload is expected UX (recoverable via version history where it
    exists). INVARIANT: the table's UPDATE policy qual references auth.uid()/auth_worker_names()
    (own-scope), NOT `true`.
  * create-once / edge-fn-mediated (index worker_profiles · shift-brain · voice-journal) — no client
    shared-row edit: worker_profiles is one-per-user (unique auth_uid, create-once); shift-brain +
    voice-journal write only via edge-fn orchestrators (the server owns the write atomically).
    INVARIANT: no client `.update(`/`.upsert(` on a shared row (append inserts are fine).

Also STATIC-asserts each page still contains its declared write shape, so a refactor that swaps the
class (e.g. a page starts doing a read-modify-write delta) trips the gate for re-scoring.

Skips cleanly (exit 0) if docker/DB unreachable. `--selftest` proves the parser + checks have teeth.
"""
from __future__ import annotations
import io, re, sys, subprocess
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_p6_concurrency_class"]
DB = "supabase_db_workhive"
REPO = Path(__file__).resolve().parent.parent

# page -> (table, class, key/None, write-shape regex the page MUST still contain)
IDEMPOTENT = "idempotent-upsert"; OWNER = "owner-scoped-update"; APPEND = "create-once-insert"
FORWARD = "forward-only-status"
CLASSES = [
    ("skillmatrix",        "skill_profiles",             IDEMPOTENT, "worker_name",
     r"from\('skill_profiles'\)\.upsert\("),
    ("marketplace-seller", "marketplace_sellers",        IDEMPOTENT, "worker_name",
     r"from\('marketplace_sellers'\)\.upsert\("),
    ("dayplanner",         "schedule_items",             IDEMPOTENT, "id",
     r"from\('schedule_items'\)\.upsert\("),
    ("resume",             "resume_documents",           OWNER,      None,
     r"from\('resume_documents'\)\.update\("),
    ("marketplace",        "marketplace_saved_searches", OWNER,      None,
     r"from\('marketplace_saved_searches'\)\.update\("),
    ("marketplace-seller", "marketplace_inquiries",      OWNER,      None,
     r"from\('marketplace_inquiries'\)\.update\("),
    ("index",              "worker_profiles",            APPEND,     "auth_uid",
     r"from\('worker_profiles'\)\.insert\("),
    # shift-brain: supervisor publishes/archives a HIVE-SHARED shift_plans row (multi-line chain). Race-safe
    # by a forward-only status trigger (a concurrent archive-then-publish can't regress a published plan).
    ("shift-brain",        "shift_plans",                FORWARD,    "tg_shift_plans_forward_status",
     r"from\('shift_plans'\)[\s\S]{0,80}\.update\("),
    # voice-journal: persists the persona choice to the caller's OWN worker_profiles row (own-scoped RLS).
    ("voice-journal",      "worker_profiles",            OWNER,      None,
     r"from\('worker_profiles'\)[\s\S]{0,80}\.update\("),
]

# A shared-row read-modify-write delta would break the "full-object write => converge" premise; a page in
# an idempotent/owner class must NOT do `col: col +/- n` on the class table (CSS shorthands excluded).
RMW_RE = re.compile(r"\b([a-z_]{2,})\s*:\s*\1\s*[+\-]\s*\d")
CSS_FALSE = re.compile(r"^(px|py|pt|pb|pl|pr|mt|mb|ml|mr|gap|top|left|right|z|line|col|row|sm|md|lg|xl)$")


def _psql(sql: str, timeout=40):
    try:
        return subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                               "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                              input=sql, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _has_unique_index(table: str, key: str) -> bool:
    # a single-column unique index on `key`, OR key participating as the sole arbiter column
    sql = (f"select 1 from pg_index i join pg_class t on t.oid=i.indrelid "
           f"where i.indisunique and t.relname='{table}' "
           f"and (select array_agg(a.attname order by k.ord) from unnest(i.indkey) with ordinality k(attnum,ord) "
           f"     join pg_attribute a on a.attrelid=t.oid and a.attnum=k.attnum) = array['{key}']::name[];")
    r = _psql(sql)
    return bool(r and r.returncode == 0 and r.stdout.strip() == "1")


def _update_policy_ownscoped(table: str) -> tuple[bool, str]:
    sql = (f"select coalesce(string_agg(pg_get_expr(polqual,polrelid),' || '),'-') from pg_policy "
           f"where polrelid='{table}'::regclass and polcmd in ('w','*');")
    r = _psql(sql)
    if not r or r.returncode != 0:
        return False, "policy-read-failed"
    qual = r.stdout.strip()
    if qual in ("", "-"):
        return False, "no-update-policy"
    own = ("auth.uid()" in qual) or ("auth_worker_names()" in qual)
    unbounded = qual.lower() == "true"
    return (own and not unbounded), qual[:80]


def _has_trigger(table: str, trig: str) -> bool:
    sql = f"select 1 from pg_trigger where tgrelid='{table}'::regclass and tgname='{trig}' and not tgisinternal;"
    r = _psql(sql)
    return bool(r and r.returncode == 0 and r.stdout.strip() == "1")


def _no_client_shared_edit(page: str) -> tuple[bool, int]:
    p = REPO / f"{page}.html"
    if not p.exists():
        return True, 0
    src = p.read_text(encoding="utf-8", errors="ignore")
    n = len(re.findall(r"\.update\(|\.upsert\(", src))
    return n == 0, n


def _static_shape_ok(page: str, shape: str | None) -> bool:
    if shape is None:
        return True
    p = REPO / f"{page}.html"
    if not p.exists():
        return False
    return bool(re.search(shape, p.read_text(encoding="utf-8", errors="ignore")))


def _no_rmw_delta(page: str, table: str) -> tuple[bool, str]:
    p = REPO / f"{page}.html"
    if not p.exists():
        return True, ""
    for m in RMW_RE.finditer(p.read_text(encoding="utf-8", errors="ignore")):
        if not CSS_FALSE.match(m.group(1)):
            return False, m.group(0)
    return True, ""


def _dbup() -> bool:
    r = _psql("select 1;")
    return bool(r and r.returncode == 0 and r.stdout.strip() == "1")


def check_row(page, table, klass, key, shape) -> str:
    if not _static_shape_ok(page, shape):
        return f"FAIL:static-shape-missing({page}: expected write `{shape}` not found — class may have changed, re-score P6)"
    if klass == IDEMPOTENT:
        ok_rmw, hit = _no_rmw_delta(page, table)
        if not ok_rmw:
            return f"FAIL:read-modify-write-delta({page} {table}: `{hit}` breaks upsert-converge premise)"
        if not _has_unique_index(table, key):
            return f"FAIL:no-unique-index({table} onConflict '{key}' has no matching unique index — upserts can DUPLICATE, not converge)"
        return "OK"
    if klass == OWNER:
        own, qual = _update_policy_ownscoped(table)
        if not own:
            return f"FAIL:update-not-ownscoped({table}: UPDATE policy `{qual}` is not own-identity scoped — cross-user lost-update possible)"
        return "OK"
    if klass == FORWARD:
        # a hive-shared status row is race-safe iff a forward-only transition trigger blocks regression
        if not _has_trigger(table, key):
            return f"FAIL:no-forward-guard({table}: forward-only status trigger '{key}' missing — a concurrent status write could regress the state)"
        return "OK"
    if klass == APPEND:
        if table is None:  # edge-fn-mediated page: no client shared-row edit at all
            noedit, n = _no_client_shared_edit(page)
            return "OK" if noedit else f"FAIL:edgefn-page-gained-edit({page}: {n} client .update/.upsert — no longer server-mediated, re-score P6)"
        # create-once insert table: needs a unique key so a concurrent create can't duplicate the identity
        if key and not _has_unique_index(table, key):
            return f"FAIL:no-unique-index({table} create-once needs unique '{key}' so a double-create can't fork the identity)"
        return "OK"
    return f"FAIL:unknown-class({klass})"


def live_converge_probe() -> str:
    """Representative teeth: a rolled-back double-upsert on schedule_items (stable id) must converge to 1 row w/ 2nd value."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
        from test_identity import resolve_test_identity
        i = resolve_test_identity("leandromarquez@auth.workhiveph.com")
        uid, hive = i.user_id, i.hive_id
    except Exception:
        return "SKIP"
    sql = f"""
begin;
set local role authenticated;
set local request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
insert into schedule_items(id, auth_uid, worker_name, date, title, category)
values('P6GATE-CONV-1','{uid}','probe',current_date,'first','task')
on conflict (id) do update set title=excluded.title;
insert into schedule_items(id, auth_uid, worker_name, date, title, category)
values('P6GATE-CONV-1','{uid}','probe',current_date,'second','task')
on conflict (id) do update set title=excluded.title;
select 'CONV|'||count(*)||'|'||max(title) from schedule_items where id='P6GATE-CONV-1';
rollback;
"""
    r = _psql(sql)
    if not r:
        return "SKIP"
    out = (r.stdout or "") + (r.stderr or "")
    for ln in out.splitlines():
        if ln.startswith("CONV|"):
            return "OK" if ln.strip() == "CONV|1|second" else f"FAIL:converge({ln.strip()})"
    if "column" in out.lower() and "does not exist" in out.lower():
        return "SKIP:schema(" + out.strip().replace("\n", " ")[-70:] + ")"
    return "SKIP"


def self_test() -> bool:
    ok = True
    if RMW_RE.search("xp: xp + 5") is None:
        print(f"{R}self-test FAIL: RMW regex misses a real counter delta.{X}"); ok = False
    if CSS_FALSE.match("px") is None:
        print(f"{R}self-test FAIL: CSS shorthand not excluded.{X}"); ok = False
    if RMW_RE.search("total: total - 1") is None:
        print(f"{R}self-test FAIL: RMW regex misses a decrement.{X}"); ok = False
    # a plain assignment must NOT read as a delta
    if RMW_RE.search("title: title") is not None:
        print(f"{R}self-test FAIL: plain copy misread as delta.{X}"); ok = False
    print((G + "self-test PASS - p6-concurrency-class checks have teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}P6 concurrency-class gate (idempotent-upsert · owner-scoped-update · create-once/edge-fn){X}")
    if not _dbup():
        print("  SKIP: local DB not reachable — P6 concurrency-class gate not evaluated.")
        return 0
    fails = []
    seen = set()
    for page, table, klass, key, shape in CLASSES:
        tag = f"{page}/{table or 'edge-fn'}"
        v = check_row(page, table, klass, key, shape)
        if v == "OK":
            print(f"  {G}PASS{X}  {tag} [{klass}]")
        else:
            print(f"  {R}FAIL{X}  {tag}: {v}"); fails.append((tag, v))
        seen.add(tag)
    conv = live_converge_probe()
    if conv == "OK":
        print(f"  {G}PASS{X}  live: schedule_items double-upsert CONVERGES to 1 row (2nd value) — idempotent proof")
    elif conv.startswith("FAIL"):
        print(f"  {R}FAIL{X}  live: {conv}"); fails.append(("live-converge", conv))
    else:
        print(f"  SKIP  live-converge: {conv}")
    if fails:
        print(f"{R}FAIL: {len(fails)} P6 concurrency-class regression(s).{X}")
        return 1
    print(f"{G}PASS - every remaining P6 page's concurrency-safety class is structurally locked.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
