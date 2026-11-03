#!/usr/bin/env python3
"""prove_founder_rpc_refusal.py - every RPC a founder page's own code calls refuses a person who is not a platform admin.

WHY (2026-11-03, the CX-FND walk). The founder pages refuse a non-admin on screen ("Founder access only", "Platform Admins
Only"), and the walk measured that refusal. But a screen is the client's answer; the data behind it is served by RPCs
anyone holding a token can call directly. tools/prove_tenant_refusal.mjs proves the TABLES and VIEWS refuse a stranger;
nothing proved the platform RPCs did. Asked directly as a non-admin supervisor, eight founder_* functions raised 42501 and
six answered 200 with 0 or [] - SECURITY INVOKER rollups over analytics_events, which row-level security empties for a
non-admin (an admin's same call: MAU 27, 3,740 visitor sessions). Both are refusals, and only a comparison with the
admin's answer can tell the second kind from "there was nothing to show".

THE READING. For each RPC the founder pages' own source calls (the page and its same-basename script - never the shared
chrome's), asked through PostgREST with a real token minted for each actor, the publishable key only for the visitor:
  admin       a platform admin - the CONTROL: what there is to withhold
  supervisor  a non-admin supervisor (widest hive role)        worker  a non-admin worker        anon  no session
A call is REFUSED when it answers 401/403 (42501), or answers empty while the admin's identical call does not. When the
admin's call is empty too, there was nothing to hide: n/a, never counted as a pass. A non-admin answer EQUAL to the
admin's non-empty one is a LEAK; a different non-empty answer is a SLICE the report names for a person to read. A write
RPC is called only with a request id nobody holds (a random uuid), so even a missing check could change nothing.

    python tools/prove_founder_rpc_refusal.py            # read + write founder_rpc_refusal_report.json
    python tools/prove_founder_rpc_refusal.py --check    # the gate: a leak, a probe that did not answer, or no control fails
    python tools/prove_founder_rpc_refusal.py --bank [--apply]   # the founder pages' S and AU contract rows on this reading
    python tools/prove_founder_rpc_refusal.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
REPORT = ROOT / "founder_rpc_refusal_report.json"
API = "http://127.0.0.1:54321"
DB = "supabase_db_workhive"
PASSWORD = "test1234"          # the seeded local accounts' password (seed_*.py); never a production credential
GATE_ID = "founder-rpc-refusal"
NON_ADMIN = ("supervisor", "worker", "anon")


def psql(sql: str) -> list[str]:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return [ln for ln in (r.stdout or "").strip().splitlines() if ln.strip()]


def publishable_key() -> str:
    m = re.search(r"sb_publishable_[A-Za-z0-9_-]+", (ROOT / "utils.js").read_text(encoding="utf-8", errors="replace"))
    return m.group(0) if m else ""


def founder_rpcs() -> dict:
    """{rpc: [pages]} - what each founder page's OWN source calls."""
    import bank_lx_walk as blw
    import sublayer_inventory as si
    out: dict = {}
    for page in si.FOUNDER_PAGES:
        for t in sorted(blw.page_tables(page)):
            if t.startswith("rpc/"):
                out.setdefault(t[4:], []).append(page)
    return out


def casts() -> dict:
    """{actor: [login local parts]} read from the database, never typed - candidates in order, the first that signs in
    is cast (a service account such as ai-eval-runner holds a membership and no seeded password). Never a platform admin
    unless it is the control."""
    admins = "(select worker_name from marketplace_platform_admins)"
    q = ("select split_part(u.email,'@',1) from hive_members m join auth.users u on u.id = m.auth_uid "
         "where m.status = 'active' and m.role = '{role}' and m.worker_name not in " + admins +
         " and u.email like '%@auth.workhiveph.com' order by m.worker_name limit 8")
    adm = psql("select split_part(u.email,'@',1) from marketplace_platform_admins a join worker_profiles w on "
               "w.display_name = a.worker_name join auth.users u on u.id = w.auth_uid order by 1 limit 8")
    return {"admin": adm, "supervisor": psql(q.format(role="supervisor")), "worker": psql(q.format(role="worker")),
            "anon": [""]}


def token(local: str, key: str) -> str:
    body = json.dumps({"email": f"{local}@auth.workhiveph.com", "password": PASSWORD}).encode()
    req = urllib.request.Request(f"{API}/auth/v1/token?grant_type=password", data=body,
                                 headers={"apikey": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("access_token", "")


def signatures(names: list[str]) -> dict:
    """{rpc: (args-text, security definer)} from pg_proc."""
    lit = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    out = {}
    for ln in psql(f"select proname || '|' || pg_get_function_arguments(oid) || '|' || prosecdef from pg_proc "
                   f"where pronamespace = 'public'::regnamespace and proname in ({lit})"):
        name, rest = ln.split("|", 1)
        args, sd = rest.rsplit("|", 1)
        out[name] = (args, sd == "t")
    return out


def call_args(args: str) -> dict:
    """A body for every parameter WITHOUT a default: a window for a timestamp, 30 for a count, a request id nobody holds."""
    body = {}
    for part in [p.strip() for p in args.split(",") if p.strip()]:
        if " DEFAULT " in part.upper():
            continue
        name, typ = part.split(" ", 1)
        t = typ.lower()
        body[name] = (datetime.now(timezone.utc).replace(microsecond=0).isoformat() if "timestamp" in t
                      else 30 if "int" in t else str(uuid.uuid4()) if "uuid" in t else False if "bool" in t else "")
    return body


def call(rpc: str, body: dict, key: str, bearer: str) -> tuple[int, object]:
    req = urllib.request.Request(f"{API}/rest/v1/rpc/{rpc}", data=json.dumps(body).encode(), method="POST",
                                 headers={"apikey": key, "Authorization": "Bearer " + (bearer or key),
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:200]


def empty(v) -> bool:
    """Nothing handed over: null, 0, an empty list or object, or a list/object of nothing but zeros and nulls."""
    if v in (None, 0, 0.0, "", [], {}):
        return True
    if isinstance(v, list):
        return all(empty(x) for x in v)
    if isinstance(v, dict):
        return all(empty(x) for x in v.values())
    return False


def verdict(status: int, val, admin_status: int, admin_val) -> str:
    """REFUSED | n/a | LEAK | SLICE | ERROR for one non-admin call against the admin's control."""
    code = val.get("code") if isinstance(val, dict) else None
    if status in (401, 403) or code == "42501":
        return "REFUSED"
    if status >= 400:
        return "ERROR"          # the probe asked wrongly (a missing parameter, a name that moved): not an answer
    admin_ok = 200 <= admin_status < 300
    if empty(val):
        return "REFUSED" if admin_ok and not empty(admin_val) else "n/a"
    if admin_ok and json.dumps(val, sort_keys=True) == json.dumps(admin_val, sort_keys=True):
        return "LEAK"
    return "SLICE"


def measure() -> dict:
    key = publishable_key()
    rpcs = founder_rpcs()
    sigs = signatures(sorted(rpcs))
    who, toks = {}, {}
    for actor, cands in casts().items():
        who[actor], toks[actor] = "", ""
        for u in cands:
            if not u:                       # the visitor: no session at all
                break
            try:
                toks[actor] = token(u, key)
            except Exception:
                continue
            if toks[actor]:
                who[actor] = u
                break
    out = {"_doc": __doc__.split("\n\n")[0], "generated": datetime.now().isoformat(timespec="seconds"),
           "actors": {a: (u or "(no session)") for a, u in who.items()}, "rpcs": {}}
    for rpc in sorted(rpcs):
        args, sd = sigs.get(rpc, ("", False))
        body = call_args(args)
        a_st, a_val = call(rpc, body, key, toks["admin"])
        row = {"pages": rpcs[rpc], "security_definer": sd, "body": body,
               "admin": {"status": a_st, "empty": empty(a_val)}, "as": {}}
        for actor in NON_ADMIN:
            st, val = call(rpc, body, key, toks[actor])
            row["as"][actor] = {"status": st, "verdict": verdict(st, val, a_st, a_val),
                                "said": (val.get("message") if isinstance(val, dict) else None)}
        out["rpcs"][rpc] = row
    tally: dict = {}
    for r in out["rpcs"].values():
        for x in r["as"].values():
            tally[x["verdict"]] = tally.get(x["verdict"], 0) + 1
    out["totals"] = tally
    return out


def check(rep: dict) -> int:
    bad = []
    if not all((rep.get("actors") or {}).get(a) for a in ("admin", "supervisor", "worker")):
        bad.append("an actor could not be cast from the database: " + json.dumps(rep.get("actors")))
    for rpc, r in (rep.get("rpcs") or {}).items():
        for actor, x in r["as"].items():
            if x["verdict"] in ("LEAK", "ERROR"):
                bad.append(f"{rpc} as {actor}: {x['verdict']} (HTTP {x['status']})")
    for b in bad:
        print("FAIL founder-rpc-refusal: " + b)
    if bad:
        return 1
    t = rep.get("totals") or {}
    print(f"PASS founder-rpc-refusal - {len(rep.get('rpcs') or {})} founder RPCs x {len(NON_ADMIN)} non-admins: "
          f"{t.get('REFUSED', 0)} refused, {t.get('n/a', 0)} n/a (the admin's call was empty too - nothing to hide), "
          f"{t.get('SLICE', 0)} answered a slice of their own, 0 leaked")
    return 0


def self_test() -> int:
    cases = [((403, {"code": "42501"}, 200, 27), "REFUSED"), ((200, 0, 200, 27), "REFUSED"),
             ((200, [], 200, [{"day": 1, "dau": 14}]), "REFUSED"), ((200, 0, 200, 0), "n/a"),
             ((200, 27, 200, 27), "LEAK"), ((200, [{"a": 1}], 200, [{"a": 1}]), "LEAK"),
             ((200, [{"a": 1}], 200, [{"a": 5}]), "SLICE"), ((404, {"code": "PGRST202"}, 200, 1), "ERROR"),
             ((200, [{"n": 0}], 200, [{"n": 9}]), "REFUSED")]
    fails = [f"{c} -> {verdict(*c)} (want {w})" for c, w in cases if verdict(*c) != w]
    if fails:
        print("FAIL self-test: " + "; ".join(fails))
        return 1
    print(f"self-test OK: {len(cases)} verdicts - 42501 and an empty answer against a full control refuse, an answer equal "
          "to the admin's leaks, an empty control is n/a, and a probe that asked wrongly is an error, never a pass")
    return 0


def newest_walk_reads(page: str) -> tuple[str, list[str]] | None:
    """(batch, the relations the page's own healthy load asked for) from the newest LX walk of it, or None."""
    import glob
    for f in sorted(glob.glob(str(ROOT / ".tmp" / "w4_steps" / "LXB*.records.json")), key=os.path.getmtime, reverse=True):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for c in d.get("cells") or []:
            if c.get("page") != page:
                continue
            v = (c.get("vps") or [{}])[0]
            asked = sorted({x["u"].replace("/rest/v1/", "").replace("/functions/v1/", "fn:") for x in v.get("reads") or []
                            if x.get("mode") == "healthy" and x.get("pg") == page})
            return Path(f).name[:-len(".records.json")], asked
    return None


# what a signed-in page's shared code asks on every load, before the page's own: who the person is, their own hive
# memberships, whether they are a platform admin (each read bounded by the person - bank_lx_walk.RL_BOUNDED_BY_NATURE)
IDENTITY = {"v_worker_truth", "worker_profiles", "hive_members", "v_hives_truth", "marketplace_platform_admins",
            "analytics_events", "rpc/note_device", "client_errors"}


def bank(rep: dict, apply: bool) -> int:
    if check(rep):
        print("refused: a row is never banked on a red reading")
        return 1
    import bank_lx_walk as blw
    import registry_io as rio
    reg = rio.load_doc()
    rows = [t for t in reg["trajectories"] if t.get("wave") == "CX-FND" and t.get("status") in ("specced", "walked")
            and (t.get("cx") or {}).get("layer") in ("S", "AU") and (t.get("cx") or {}).get("pillar") in ("F", "I")]
    banked, left = [], []
    for t in rows:
        cx = t["cx"]
        page, layer = cx["page"], cx["layer"]
        own = sorted(x[4:] for x in blw.page_tables(page) if x.startswith("rpc/"))
        tables = sorted(x for x in blw.page_tables(page) if not x.startswith("rpc/"))
        if tables:
            left.append(f"{t['id']} {page}: its own source reads {', '.join(tables[:3])} - the tenant prover's to answer")
            continue
        if own:
            rs = [rep["rpcs"][r] for r in own if r in rep["rpcs"]]
            if len(rs) != len(own):
                left.append(f"{t['id']} {page}: {len(own) - len(rs)} of its RPCs were not read this run")
                continue
            vs = [x["verdict"] for r in rs for x in r["as"].values()]
            if "SLICE" in vs:
                left.append(f"{t['id']} {page}: an RPC answered a non-admin a slice - read the report before banking")
                continue
            ref = vs.count("REFUSED")
            how = (f"every one of the {len(own)} RPCs its own code calls ({', '.join(own[:6])}{' ...' if len(own) > 6 else ''}) "
                   f"refused a non-admin supervisor, a non-admin worker and a visitor when asked DIRECTLY through PostgREST "
                   f"with their own minted tokens: {ref} refusals (42501, or an empty answer where the admin's identical "
                   f"call was full), {vs.count('n/a')} n/a (the admin's call was empty too), 0 leaks")
            what = ("the page's data is withheld by the SERVER, not only by the screen that says so" if layer == "S" else
                    "the admin gate this page's controls sit behind is enforced by the server (AU4): a role the device "
                    "claims, or a direct call around the page, gets nothing")
        else:
            w = newest_walk_reads(page)
            if not w:
                left.append(f"{t['id']} {page}: no walk of this page recorded what it asked for")
                continue
            batch, asked = w
            extra = [r for r in asked if r not in IDENTITY and not (r.startswith("fn:") and r.endswith("/health"))]
            if extra:
                left.append(f"{t['id']} {page}: its load asked for {', '.join(extra[:3])} - not answered here")
                continue
            how = (f"its own source calls no RPC and reads no relation, and the walk {batch} measured its whole healthy load: "
                   f"{', '.join(asked) or 'nothing'} - the shared code's identity reads (each bounded by the person) and "
                   f"services' /health probes, nothing that belongs to a hive or another person")
            what = ("there is nothing on this page to withhold and no boundary on it to cross" if layer == "S" else
                    "no read on this page depends on a membership or a role the device could hold stale")
        basis = (f"[{date.today().isoformat()}] pct -> 60. WALKED with the registered prover tools/prove_founder_rpc_refusal.py "
                 f"(gate `{GATE_ID}`, {rep['generated']}): {how}. So {what}. The {layer} ask through {cx['pillar']} on "
                 f"{page}, as {cx.get('persona') or cx.get('cast')}.")
        prev = t.get("basis") or ""
        if "prove_founder_rpc_refusal.py" not in prev:
            t["basis"] = basis + (" || " + prev if prev else "")
        t["status"] = "locking"
        t["pct"] = max(int(t.get("pct") or 0), 60)
        gates = t.setdefault("artifacts", {}).setdefault("gates", [])
        if GATE_ID not in gates:
            gates.append(GATE_ID)
        banked.append(f"{t['id']} {page} {layer}/{cx['pillar']}")
    for b in banked:
        print("  bank " + b)
    for l in left:
        print("  left open: " + l)
    if apply and banked:
        # at the main file's own indent (the tenant banker's rule): a cube row lives in its shard, the main file is rewritten
        with io.open(rio.MAIN, encoding="utf-8") as fh:
            fh.readline()
            second = fh.readline()
        rio.save_doc(reg, indent=max(1, len(second) - len(second.lstrip(" "))) if second.strip() else 2)
    print(f"{'banked' if apply else 'would bank'} {len(banked)} row(s); {len(left)} left open")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--bank", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    rep = measure()
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.bank:
        return bank(rep, a.apply)
    return check(rep)


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
