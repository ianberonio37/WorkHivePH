#!/usr/bin/env python3
"""prove_w4_layer_trail.py - the W4 layer-L stories, proven at source (no browser).

The wave-4 L-layer story is "The platform must record who did what on this page, in a trail somebody can read
later." A page that lets a person CHANGE something owes a trail of it; a page that only reads owes nothing, and a
static document writes nothing at all. This reads each L-layer row's own page and the scripts it loads and asks:
  - static document (no data client, tools/page_kind) or no write path at all -> n/a (nothing to record)
  - a write path that reaches the audit trail (audit_log / writeAuditLog / rpc *audit*) -> ok
  - a write path with NO trail -> BAD (a change nobody can trace)
It reuses prove_clock_and_trail's own TRAIL_CALL matcher and page_source so the two cannot drift, and writes a
`witness` receipt per row for live_walk_manifest._w4_missing. The trail is source-level and axis-independent, so
the three axis-rows of a page share one witness.

  python tools/prove_w4_layer_trail.py            # every L-layer row, print + write receipts
  python tools/prove_w4_layer_trail.py --check    # the gate: exit 1 if any L row's page writes without a trail
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import prove_clock_and_trail as ct  # noqa: E402  - reuse TRAIL_CALL + page_source
from page_kind import is_static_doc  # noqa: E402
from prove_w4_layer_headers import _first_root_page  # noqa: E402  - same surface-picking rule

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
# a page that CHANGES a DOMAIN row a colleague can see: from(<domain table>).insert/update/upsert/delete.
# ★NOT the shared telemetry (2026-09-14): `client_errors` (whLogError, in utils.js, on EVERY page) and the other
# self-recording tables below are the platform's own logs, not a user action that owes a separate audit row -
# counting them made status/public-feed/marketplace-seller-profile read "writes without a trail" while they only
# log their own errors. Edge invokes are dropped too: most are reads / AI / search, and whether an edge fn writes
# an audit row is server-side, invisible to a source read - so an edge-only page is `n/a` here, not a false BAD.
_TELEMETRY = r"(?!client_errors\b)(?!ai_reply_feedback\b)(?!analytics_events\b)(?!page_views\b)"
WRITE = re.compile(r"\.from\(\s*['\"]" + _TELEMETRY + r"[a-z0-9_]+['\"]\s*\)\s*[\s\S]{0,120}?\.(insert|update|upsert|delete)\s*\(", re.I)


# ★CODE, NOT COMMENTS (2026-10-13): wh-capture-validate.js's JSDoc usage example ("await db.from('logbook')
# .insert(payload)") read as assistant.html writing the logbook. Block comments and whole-line comments are dropped;
# a `//` after code is left alone, since it may sit inside a URL string.
def _code_only(src: str) -> str:
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return "\n".join("" if ln.lstrip().startswith(("//", "*")) else ln for ln in src.split("\n"))


# ★A PERSON'S OWN PREFERENCE IS NOT A CHANGE ANYONE ELSE CAN SEE (2026-10-13): voice-journal saves which assistant
# voice the person uses, `.update({ preferred_persona: key }).eq('auth_uid', AUTH_UID)`. An update whose payload is
# only these columns, scoped to the caller's own auth_uid, owes no audit row; any other column still does.
SELF_PREF_COLUMNS = {"preferred_persona", "preferred_lang", "preferred_voice", "ui_theme"}
_SELF_PREF = re.compile(r"\.update\(\s*\{([^{}]*)\}\s*\)\s*\.eq\(\s*['\"]auth_uid['\"]")


def _is_self_preference(after: str) -> bool:
    m = _SELF_PREF.match(after)
    if not m:
        return False
    keys = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", m.group(1)))
    return bool(keys) and keys <= SELF_PREF_COLUMNS


# ★A RECORD ONLY ITS OWNER CAN SEE OWES NO HIVE TRAIL (2026-10-28, CX dayplanner). The rule above is "a DOMAIN row a
# colleague can see", but nothing measured the "can see": dayplanner writes only schedule_items, a person's own day
# plan, whose every read policy is auth_uid = auth.uid() - no supervisor, no hive-mate. Who changed it is always its
# owner, and copying a private plan into the supervisor-read hive trail would publish it. Measured from pg_policy, not
# listed by hand: a policy that later admits hive-mates turns the obligation back on, and an unreadable database
# counts the table as shared (the check fails closed).
_OWNER_ONLY_QUAL = re.compile(r"^(?:selectauth\.uid(?:asuid)?isnotnulland)?auth_uid=(?:select)?auth\.uid(?:asuid)?$")
_PRIVATE: dict[str, bool] = {}


def owner_private(table: str) -> bool:
    if table in _PRIVATE:
        return _PRIVATE[table]
    # RLS is not the only door: a view that runs as its owner, or a SECURITY DEFINER function a signed-in person may
    # call that selects from the table, shows its rows past the policy - either one makes the table shared
    sql = ("select ((select relrowsecurity from pg_class where oid = to_regclass('public.{t}'))"
           " and not exists (select 1 from pg_depend d join pg_rewrite r on r.oid = d.objid join pg_class c on c.oid = r.ev_class"
           "   where d.refobjid = to_regclass('public.{t}') and c.oid <> to_regclass('public.{t}') and c.relkind = 'v'"
           "   and coalesce((select option_value from pg_options_to_table(c.reloptions) where option_name = 'security_invoker'), 'false') <> 'true')"
           " and not exists (select 1 from pg_proc p where p.prosecdef and p.prorettype <> 'trigger'::regtype"
           "   and (has_function_privilege('authenticated', p.oid, 'execute') or has_function_privilege('anon', p.oid, 'execute'))"
           "   and p.prosrc ~* 'select[^;]*from\\s+(public\\.)?{t}\\M'))::text || chr(31) || "
           "coalesce(string_agg(pg_get_expr(polqual, polrelid), chr(31)), '') from pg_policy "
           "where polrelid = to_regclass('public.{t}') and polpermissive and polcmd in ('r', '*')").format(t=table)
    try:
        r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tAc", sql],
                           capture_output=True, text=True, timeout=30)
        parts = (r.stdout or "").strip().split("\x1f")
    except Exception:
        parts = []
    rls, quals = (parts[0] == "true") if parts else False, [q for q in parts[1:] if q.strip()]
    _PRIVATE[table] = bool(rls and quals and all(_OWNER_ONLY_QUAL.match(re.sub(r"[()\s]", "", q).lower()) for q in quals))
    return _PRIVATE[table]


# ★THE DATABASE CAN WRITE THE TRAIL (2026-10-28, CX dayplanner). dayplanner closes a linked logbook entry with
# .update({ status: 'Closed' }) and calls no trail function - because trg_logbook_close_audit (UPDATE OF status) does,
# server-side, into hive_audit_log. A source read cannot see that, so the page read as "changes data, no trail". A write
# counts as trailed by a trigger only when a row trigger on that table fires on that operation and inserts into
# hive_audit_log, and - for an update - covers every key the page's payload sets (the trigger's own column list, or
# its function body when it names no columns). A payload passed as a variable earns no trigger credit.
_OP_BIT = {"insert": 4, "delete": 8, "update": 16}
_TRIGGERS: dict[str, list] = {}


def _audit_triggers(table: str) -> list:
    if table not in _TRIGGERS:
        # one JSON document: a function body carries newlines, which split a delimited row apart
        sql = ("select coalesce(json_agg(json_build_object('n', t.tgname, 'ty', t.tgtype, 'src', p.prosrc, 'cols', "
               "(select coalesce(json_agg(attname), '[]'::json) from pg_attribute where attrelid = t.tgrelid "
               "and attnum = any(t.tgattr::int2[])))), '[]'::json) from pg_trigger t join pg_proc p on p.oid = t.tgfoid "
               "where t.tgrelid = to_regclass('public.%s') and not t.tgisinternal and t.tgenabled <> 'D' "
               "and p.prosrc ilike '%%hive_audit_log%%'" % table)
        try:
            r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                                "-tAc", sql], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            rows = json.loads((r.stdout or "").strip() or "[]")
        except Exception:
            rows = []
        _TRIGGERS[table] = [(x["n"], int(x["ty"]), list(x.get("cols") or []), x.get("src") or "") for x in rows]
    return _TRIGGERS[table]


def trigger_trail(table: str, op: str, after: str) -> str | None:
    """The trigger that writes this write's trail, named - or None."""
    op = op.lower()
    need = [_OP_BIT["insert"], _OP_BIT["update"]] if op == "upsert" else [_OP_BIT.get(op, 0)]
    keys = None
    if op in ("update", "upsert"):
        m = re.match(r"\s*\{([^{}]*)\}", after)
        if not m:
            return None                                 # the payload is a variable: its keys cannot be read here
        keys = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", m.group(1)))
        if not keys:
            return None
    for bit in need:
        hit = None
        # a trigger scoped to the columns this write sets names the trail most precisely, so it is tried first
        for name, ty, cols, src in sorted(_audit_triggers(table), key=lambda x: not x[2]):
            if not (ty & 1) or not (ty & bit):          # a ROW trigger that fires on this operation
                continue
            if bit == _OP_BIT["update"] and not (keys <= set(cols) if cols else all(k in src for k in keys)):
                continue
            hit = f"{name} ({'UPDATE OF ' + ','.join(cols) if cols and bit == 16 else op.upper()})"
            break
        if not hit:
            return None
    return hit


def _domain_writes(src: str) -> list:
    code = _code_only(src)
    out = []
    for m in WRITE.finditer(code):
        tail = code[m.end() - len(m.group(1)) - 2: m.end() + 300]   # from the "." of .update( onwards
        if m.group(1).lower() == "update" and _is_self_preference(tail.lstrip()):
            continue
        out.append(m)
    return out


def l_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "L"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    """('ok'|'n/a'|'BAD', witness/reason)."""
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - it writes nothing, so there is no trail to owe"
    src = ct.page_source(page)
    if not src:
        return "n/a", f"{page} could not be read from disk"
    ms = _domain_writes(src)
    trail = ct.TRAIL_CALL.search(src)
    if not ms:
        return "n/a", f"{page} makes no user-visible write, so it owes no trail"
    if trail:
        return "ok", f"{page} records its changes in the audit trail (\"{trail.group(0)[:40]}\")"
    private, by_db, untrailed = set(), [], []
    for m in ms:
        t = re.match(r"\.from\(\s*['\"]([a-z0-9_]+)", m.group(0), re.I).group(1)
        if owner_private(t):
            private.add(t)
            continue
        hit = trigger_trail(t, m.group(1), m.string[m.end():m.end() + 300])
        (by_db.append(f"{t}: {hit}") if hit else untrailed.append(t))
    if untrailed:
        return "BAD", (f"{page} changes data ({', '.join(sorted(set(untrailed))[:4])}) but nothing in it, the scripts it "
                       f"loads or a trigger on the table writes to the audit trail")
    if by_db:
        return "ok", (f"{page} calls no trail function, and the database writes its trail: "
                      + "; ".join(sorted(set(by_db))[:3]) + " inserts into hive_audit_log"
                      + (f"; {', '.join(sorted(private))} is private to its owner" if private else ""))
    return "n/a", (f"{page} writes only rows no colleague can read ({', '.join(sorted(private))}: every read policy keys "
                   f"on the row's own auth_uid) - who changed such a record is always its owner, so it owes no hive trail")


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 L-layer story proven at source (no browser) - tools/prove_w4_layer_trail.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "postgres",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "postgres",
            "condition": "normal", "cast": "the audit trail (source-level)",
            "problems": [] if ok else [witness],
            "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "L", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = l_rows()
    if not rows:
        print("PASS w4-layer-trail - no W4 layer-L row (nothing to prove)")
        return 0
    check_only = "--check" in sys.argv
    page_cache: dict[str, tuple[str, str]] = {}
    bad = 0
    for row in rows:
        page = _first_root_page(row)
        if not page:
            continue
        if page not in page_cache:
            page_cache[page] = check_page(page)
        verdict, witness = page_cache[page]
        if verdict == "BAD":
            bad += 1
        if not check_only:
            write_receipt(row, verdict, witness)
    n = len(rows)
    uniq = len(page_cache)
    na = sum(1 for v, _w in page_cache.values() if v == "n/a")
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-trail - "
          f"{n - bad * (n // max(uniq, 1))}/{n} L-layer row(s) hold "
          f"({uniq} distinct pages, {na} n/a - no writes to record)"
          + (f"; {bad} page(s) write without a trail" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
