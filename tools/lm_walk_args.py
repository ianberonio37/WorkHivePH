"""lm_walk_args.py - write .tmp/lm_args.json for ONE LLM-layer row (§LM), the parameters tools/lm_walk.js walks with.

The LM rows are walked through the Playwright MCP as the row's PERSONA at both viewports, with every model call
answered by a stub (Ian, 2026-10-06: local stubs first; the live model only for Grounding and Routing). This file
decides, deterministically, the three things the walk must not improvise:

  1. WHO signs in. any / worker / assistive-tech -> an active worker of the row's own hive (journey.vertical);
     supervisor / fleet-supervisor -> an active supervisor there; solo-owner -> Jun Salvador, who has no hive
     (tools/seed_solo_personas.py); adversary -> a worker of ANOTHER hive, whose target is this row's hive.
  2. WHICH hive is foreign, and what its records look like. The foreign hive is one the signed-in person is not an
     active member of; its markers (the hive's name and some asset tags) are what a leak would carry.
  3. WHICH functions may be probed live with the foreign hive. A probe is sent only when the function's own source
     proves MEMBERSHIP before its first model or embedding call AND the function writes nothing - so a refusal is
     free, and even a broken gate could not spend or write. Every other function is settled by the static gates
     (validate_edge_fn_auth_gate, validate_ai_prompt_injection, validate_ai_retrieval_isolation) and the page-level
     capture, and the receipt says so.

  python tools/lm_walk_args.py LM1        -> writes the args, prints the cast and the probe plan
  python tools/lm_walk_args.py --profile  -> the per-function profile for every LM function, nothing written
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB = "supabase_db_workhive"
PASSWORD = "test1234"
SOLO = {"user": "junvanowner", "name": "Jun Salvador"}
# the gateway agent each surface's own front door names (read from the pages: agent: '...')
GATEWAY_AGENT = {"asset-hub.html": "asset-brain", "assistant.html": "assistant", "hive.html": "coach",
                 "companion": "voice-journal", "marketplace.html": "assistant"}
# membership proof (not identity alone: auth.getUser proves WHO, not WHICH HIVE)
# resolveIdentity is NOT here: it proves WHO calls, not WHICH hive (voice-transcribe, 2026-10-07)
MEMBERSHIP = re.compile(r"resolveTenancy\(|assertMember\(|requireHiveMember|user_hive_ids|is_hive_member|"
                        r"requireServiceRole\(|"
                        # the inline form (asset-brain-query, ai-orchestrator): a membership row keyed by the caller
                        r"from\(\s*[\"'](?:v_worker_truth|hive_members)[\"']\s*\)[\s\S]{0,240}?[\"']auth_uid[\"']")
MODEL = re.compile(r"\bcallAI\(|\bcallVision\w*\(|\bgenerateEmbedding\(|\bembedText\w*\(|\btranscribe\w*\(|"
                   r"fetch\(\s*[\"'`]https://(api\.(openai|anthropic|groq|voyageai|jina)|generativelanguage)")
WRITES = re.compile(r"\.(insert|update|upsert|delete)\(|\.rpc\(\s*[\"'](?!match_|semantic_search|get_|resolve_|"
                    r"rerank|v_)[a-z_]+[\"']")


def psql(sql: str) -> list[str]:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    return [ln for ln in (r.stdout or "").strip().splitlines() if ln.strip()]


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)(^|[^:])//.*$", r"\1", src)


# Functions whose EXECUTION order was read by hand, because the positional check above is deliberately crude and errs
# toward not probing. Each entry says what was read; a probe is still refused if that text stops being true.
VERIFIED_ORDER = {
    "ai-gateway": ("read 2026-10-07: the Pillar-I resolveTenancy check (~L898) returns the 403 before loadMemory "
                   "(~L1120), buildKnowledgeContext's embedding, the rate-limit bucket and every write; the probe "
                   "also sets context.debug_echo_memory_block, so even a gate that wrongly passed returns the "
                   "assembled context before callAI", "if (!tenancy.ok) {"),
}


# Functions whose membership check does NOT refuse, so a foreign-hive probe would run on and reach the provider.
NEVER_PROBE = {
    "voice-transcribe": ("an unproven hive only loses its ASR vocabulary (2026-10-07 fix); transcription still runs "
                         "and calls the speech provider, and the request needs real audio"),
}


def profile(fn: str) -> dict:
    p = ROOT / "supabase" / "functions" / fn / "index.ts"
    if fn in NEVER_PROBE:
        return {"fn": fn, "exists": p.exists(), "probe": False, "why": NEVER_PROBE[fn]}
    if fn in VERIFIED_ORDER and p.exists() and VERIFIED_ORDER[fn][1] in p.read_text(encoding="utf-8", errors="replace"):
        return {"fn": fn, "exists": True, "probe": True, "why": "execution order read by hand: " + VERIFIED_ORDER[fn][0],
                "membership": "resolveTenancy(", "first_model": "callAI(", "writes": True}
    if not p.exists():
        return {"fn": fn, "exists": False, "probe": False, "why": "no index.ts"}
    src = _strip_comments(p.read_text(encoding="utf-8", errors="replace"))
    # only the handler matters: the first serve(/Deno.serve( onward (imports and helpers above it do not run first)
    h = re.search(r"\b(Deno\.)?serve\(", src)
    body = src[h.start():] if h else src
    gm, mm, wm = MEMBERSHIP.search(body), MODEL.search(body), WRITES.search(src)
    out = {"fn": fn, "exists": True, "membership_at": gm.start() if gm else None,
           "model_at": mm.start() if mm else None, "writes": bool(wm),
           "membership": gm.group(0) if gm else None, "first_model": mm.group(0) if mm else None}
    if not gm:
        out.update(probe=False, why="no membership proof in the handler - settled statically, not probed")
    elif mm and gm.start() > mm.start():
        out.update(probe=False, why="a model/embedding call precedes the membership proof - a probe could spend")
    elif wm:
        out.update(probe=False, why="the function writes - a walk never calls a writer, even to be refused")
    else:
        out.update(probe=True, why="membership is proven before any model call and nothing is written")
    return out


def _member(hive: str, role: str | None) -> tuple[str, str, str] | None:
    role_sql = ("and m.role='%s'" % role) if role else ""
    rows = psql("select m.worker_name||'|'||split_part(u.email,'@',1)||'|'||h.id from hives h join hive_members m "
                "on m.hive_id=h.id join auth.users u on u.id=m.auth_uid where m.status='active' %s and "
                "h.name='%s' order by m.worker_name limit 1" % (role_sql, hive.replace("'", "''")))
    if not rows:
        return None
    n, u, hid = rows[0].split("|")
    return n, u, hid


def _hive(name: str) -> str:
    rows = psql("select id from hives where name='%s' limit 1" % name.replace("'", "''"))
    return rows[0] if rows else ""


def _markers(hive_id: str) -> list[str]:
    tags = psql("select distinct tag from asset_nodes where hive_id='%s' and tag is not null and length(tag)>=4 "
                "order by tag limit 8" % hive_id)
    return tags


def ground_for(hive_id, name, machine=None):
    """The grounding subject for one hive: its most-logged machine, the FACTS a grounded answer would carry (that
    machine's own recent words and dates - naming the machine is not grounding: LM109's first answer named it and
    said it had no history), its maintenance types, and the newest entry's age (a model once called seven-week-old
    entries "the last week")."""
    if hive_id and machine:
        top = [machine]
    elif hive_id:
        top = psql("select machine from logbook where hive_id='%s' and machine is not null group by 1 order by count(*) "
                   "desc limit 1" % hive_id)
    else:
        top = []
    subject = top[0] if top else "brake pads"
    where = ("hive_id='%s' and machine='%s'" % (hive_id, subject.replace("'", "''"))) if top else \
        ("hive_id is null and worker_name='%s'" % name.replace("'", "''"))
    rows = psql("select coalesce(problem,'')||' '||coalesce(action,'')||' '||coalesce(root_cause,'')||' '||"
                "to_char(created_at,'YYYY-MM-DD')||' '||trim(to_char(created_at,'Month'))||'_'||to_char(created_at,'FMDD') "
                "from logbook where %s order by created_at desc limit 12" % where)
    STOP = {"maintenance", "recently", "checked", "replaced", "inspected", "completed", "routine", "change", "changed"}
    facts = []
    for fr in rows:
        for d in re.findall(r"\d{4}-\d{2}-\d{2}", fr):
            if d not in facts:
                facts.append(d)
        for mon, day in re.findall(r"([A-Za-z]+)_(\d{1,2})", fr):
            for f in (f"{mon.lower()} {day}", f"{mon.lower()[:3]} {day}"):
                if f not in facts:
                    facts.append(f)
        for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{5,}", re.sub(r"[A-Za-z]+_\d{1,2}", " ", fr)):
            lw = w.lower()
            if lw not in STOP and lw not in facts:
                facts.append(lw)
    facts = facts[:40]
    # the entries' AGES - the gateway states them ("20 days ago"), and a summarising answer cites them ("five PMs in the
    # last 55 days", LM149) instead of quoting a date
    for ag in psql("select extract(day from now() - created_at)::int from logbook where %s order by created_at desc limit 12" % where):
        if ag.strip().isdigit():
            for f in (f"{int(ag)} days", f"{int(ag)} day"):
                if f not in facts:
                    facts.append(f)
    for mt in psql("select distinct lower(maintenance_type) from logbook where %s and maintenance_type is not null" % where):
        if mt and mt not in facts:
            facts.append(mt)
    age = psql("select extract(day from now() - max(created_at))::int from logbook where %s" % where)
    newest = int(age[0]) if age and age[0].strip().lstrip('-').isdigit() else None
    # an ASSET's record is also its PM completions - asset-hub's brain grounds on them ("a routine PM on August 1st, a
    # quarterly thermal scan", LM112) - so for a named tag their dates and task words count as the record too
    if hive_id and machine:
        pm_rows = psql("select coalesce(s.item_text,'')||' '||to_char(c.completed_at,'YYYY-MM-DD')||' '||"
                       "trim(to_char(c.completed_at,'Month'))||'_'||to_char(c.completed_at,'FMDD') from pm_completions c "
                       "join pm_assets a on a.id=c.asset_id left join pm_scope_items s on s.id=c.scope_item_id "
                       "where c.hive_id='%s' and a.tag_id='%s' order by c.completed_at desc limit 12"
                       % (hive_id, machine.replace("'", "''")))
        for fr in pm_rows:
            for d in re.findall(r"\d{4}-\d{2}-\d{2}", fr):
                if d not in facts:
                    facts.append(d)
            for mon, day in re.findall(r"([A-Za-z]+)_(\d{1,2})", fr):
                for f in (f"{mon.lower()} {day}", f"{mon.lower()[:3]} {day}"):
                    if f not in facts:
                        facts.append(f)
            for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{5,}", re.sub(r"[A-Za-z]+_\d{1,2}", " ", fr)):
                lw = w.lower()
                if lw not in STOP and lw not in facts:
                    facts.append(lw)
        pm_age = psql("select extract(day from now() - max(c.completed_at))::int from pm_completions c join pm_assets a "
                      "on a.id=c.asset_id where c.hive_id='%s' and a.tag_id='%s'" % (hive_id, machine.replace("'", "''")))
        if pm_age and pm_age[0].strip().lstrip('-').isdigit():
            newest = min(newest, int(pm_age[0])) if newest is not None else int(pm_age[0])
    return {"subject": subject, "facts": facts[:80], "newestAgeDays": newest}


def build(rid: str) -> dict:
    reg = {t["id"]: t for t in json.load(io.open("trajectory_registry.json", encoding="utf-8"))["trajectories"]}
    t = reg[rid]
    lx = t["lx"]
    persona, vertical = lx["persona"], (t.get("journey") or {}).get("vertical")
    hives = [h for h in psql("select name from hives where name in (select distinct h2.name from hives h2 join "
                             "hive_members m on m.hive_id=h2.id where m.status='active') order by name")]
    row_hive = _hive(vertical)
    if persona in ("supervisor", "fleet-supervisor"):
        c = _member(vertical, "supervisor")
    elif persona == "solo-owner":
        c = (SOLO["name"], SOLO["user"], "")
    elif persona == "adversary":
        other = next(h for h in hives if h != vertical)
        c = _member(other, "worker") or _member(other, None)
    else:
        c = _member(vertical, "worker") or _member(vertical, None)
    if not c:
        raise SystemExit(f"NO CAST for {rid}: persona {persona} on {vertical}")
    name, user, own = c
    if persona == "adversary":
        foreign_id, foreign_name = row_hive, vertical
    else:
        # the first other seeded hive this person is not an active member of
        mine = set(psql("select h.name from hives h join hive_members m on m.hive_id=h.id join auth.users u on "
                        "u.id=m.auth_uid where m.status='active' and split_part(u.email,'@',1)='%s'" % user))
        foreign_name = next(h for h in hives if h not in mine and h != vertical)
        foreign_id = _hive(foreign_name)
    fns = list(dict.fromkeys((lx.get("functions") or [])))
    # the companion launcher asks the gateway from almost every page (alert-hub's ask went there, 2026-10-07), so a
    # page that carries it has the gateway on its plan too
    _src = (ROOT / lx["page"]).read_text(encoding="utf-8", errors="replace") if (ROOT / lx["page"]).exists() else ""
    if (lx["surface"] in GATEWAY_AGENT or "companion-launcher.js" in _src) and "ai-gateway" not in fns:
        fns.insert(0, "ai-gateway")
    prof = [profile(f) for f in fns]
    # G (grounding): the person asks about the machine their hive has logged most, and about one that does not exist
    # anywhere. ★PER HIVE, BECAUSE A PERSON CAN BELONG TO SEVERAL (LM111, 2026-10-07): Ben Ocampo works in Dela Cruz
    # AND Tan Delivery Vans; the args picked Tan's TDV 1103 while the page opened Dela Cruz, and the AI rightly said
    # "TDV 1103 is not one of your registered assets". So a subject is computed for EVERY active hive of the cast, and
    # the walker asks about the one belonging to the hive the page actually opened. A solo owner's own record is about
    # brake pads (tools/seed_solo_personas.py OWN_WORK), keyed "none".
    hive_ids = [h for h in psql("select distinct m.hive_id from hive_members m join auth.users u on u.id=m.auth_uid "
                                "where m.status='active' and split_part(u.email,'@',1)='%s'" % user) if h]
    ground_by_hive = {h: ground_for(h, name) for h in hive_ids} if hive_ids else {"none": ground_for(None, name)}
    # asset-hub's AI is scoped to the asset its 360 view OPENS (the gateway forwards the asset id to asset-brain-query),
    # so a question about any other asset is rightly answered "no data" (LM112). The walker asks about the card the
    # ask helper opens; every tag of the person's hives gets its record facts here, and a tag with no entries expects
    # an honest "nothing".
    ground_by_tag = {}
    if lx["surface"] == "asset-hub.html":
        for h in hive_ids:
            for tag in psql("select distinct tag from asset_nodes where hive_id='%s' and tag is not null order by tag "
                            "limit 40" % h):
                if tag and tag not in ground_by_tag:
                    ground_by_tag[tag] = ground_for(h, name, machine=tag)
    first = ground_by_hive.get(own) or next(iter(ground_by_hive.values()))
    ground, facts, newest_age = first["subject"], first["facts"], first["newestAgeDays"]
    # a leak marker must be UNIQUE to the foreign hive: seeded hives share tag conventions (GEN-001 exists in Manila AND
    # Baguio), and LM120's answer listing the person's own GEN-001 read as a leak (2026-10-07)
    _own_names = set(psql("select tag from asset_nodes where hive_id in (select m.hive_id from hive_members m join auth.users u "
                          "on u.id=m.auth_uid where m.status='active' and split_part(u.email,'@',1)='%s') and tag is not null "
                          "union select machine from logbook where hive_id in (select m.hive_id from hive_members m join auth.users u "
                          "on u.id=m.auth_uid where m.status='active' and split_part(u.email,'@',1)='%s') and machine is not null"
                          % (user, user)))
    foreign_machines = [m for m in (psql("select machine from logbook where hive_id='%s' and machine is not null group by 1 "
                                         "order by count(*) desc limit 12" % foreign_id) if foreign_id else [])
                        if m not in _own_names][:5]
    page = lx["page"]
    return {
        "id": rid, "sublayer": lx["sublayer"], "persona": persona, "surface": lx["surface"], "page": page,
        "path": (t.get("journey") or {}).get("pages") or t.get("pages") or [page],
        "user": user, "pass": PASSWORD, "castName": name, "ownHive": own, "rowHive": row_hive, "rowHiveName": vertical,
        "foreignHive": foreign_id, "foreignHiveName": foreign_name, "markers": [foreign_name] + _markers(foreign_id),
        "agent": GATEWAY_AGENT.get(lx["surface"]), "functions": fns, "profile": prof,
        # report-sender: its own boxes sit beside a real Send (Resend email) - the person asks the companion instead
        "launcherOnly": lx["surface"] in ("companion", "report-sender.html"),
        "groundSubject": ground, "absentSubject": "ZQX 9471", "foreignMachines": foreign_machines, "groundFacts": facts, "groundNewestAgeDays": newest_age, "groundByHive": ground_by_hive, "groundByTag": ground_by_tag,
        "viewports": [{"name": "phone-390", "width": 390, "height": 844, "mobile": True},
                      {"name": "desktop-1280", "width": 1280, "height": 800, "mobile": False}],
        "origin": "http://localhost:5000/workhive", "api": "http://127.0.0.1:54321",
    }


if __name__ == "__main__":
    if sys.argv[1] == "--profile":
        reg = json.load(io.open("trajectory_registry.json", encoding="utf-8"))["trajectories"]
        fns = sorted({f for t in reg if (t.get("lx") or {}).get("kind") == "llm" for f in t["lx"]["functions"]} |
                     {"ai-gateway"})
        for f in fns:
            p = profile(f)
            print("%-28s probe=%-5s %s | membership=%s model=%s writes=%s" % (
                f, p["probe"], p["why"], p.get("membership"), p.get("first_model"), p.get("writes")))
        raise SystemExit(0)
    a = build(sys.argv[1])
    io.open(os.path.join(".tmp", "lm_args.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(a, ensure_ascii=False, indent=1))
    live = [p["fn"] for p in a["profile"] if p["probe"]]
    print("%s LM-%s %s as %s (%s) | foreign %s | probe live: %s | static: %s" % (
        a["id"], a["sublayer"], a["surface"], a["persona"], a["castName"], a["foreignHiveName"],
        ", ".join(live) or "none", ", ".join(p["fn"] for p in a["profile"] if not p["probe"]) or "none"))
