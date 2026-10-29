"""Full hive - one hive at the platform's ceiling: thirty members, two roles, a year of their work (Wave HS, 2026-10-29).

WHY: Ian, 2026-10-29 - "multiple tenants ... Role Based, with up to 30 hive members, how they behave when they have a
post, or lists of, concurrency". The seed's hives hold 3 to 9 members each, so no walk had ever read a list the way a
full hive's member reads it: production's community had cluttered his workmates' posts while every gate was green.
Wave HS (tools/hive_scale_census.py, 486 rows) is walked against THIS hive.

WHAT, deterministically (its own Random(30), never the orchestrator's stream - drawing from that would rename every
seeded person the probes rely on):
  - Batangas Refinery Maintenance, pinned id, 30 members: 3 supervisors, 27 workers. The names carry what L6 asks:
    long ones, alike ones (a "Jr.", a one-letter difference, a shared first name) - one hive cannot hold two members
    with ONE display name (UNIQUE hive_id, worker_name), so alike is the honest test.
  - one member who also holds a seat in Baguio Textile Mills (L7, a member of two hives), and one who has left
    (status 'deactivated', L5) whose work stays on the lists.
  - a year of attributed work on the lists the census found: community posts with replies and reactions from many
    members, logbook entries, parts with their stock movements, PM assets with completions, projects with items.
Idempotent: an existing account, membership or the hive's own rows are left alone (a second run adds nothing).
"""
import random as _random
from datetime import datetime, timedelta, timezone

from .hives_workers import AUTH_DOMAIN, TEST_PASSWORD, PINNED_HIVE_IDS

FULL_HIVE_NAME = "Batangas Refinery Maintenance"
FULL_HIVE_ID = "30303030-3030-4030-8030-303030303030"
SECOND_HIVE = "Baguio Textile Mills"

# (display name, username, role) - thirty, fixed
MEMBERS = [
    ("Ernesto Villareal", "ernestovillareal", "supervisor"),
    ("Corazon Bautista", "corazonbautista", "supervisor"),
    ("Danilo Pascual", "danilopascual", "supervisor"),
    ("Mark Anthony Santos", "markanthonysantos", "worker"),
    ("Mark Anthony Santos Jr.", "markanthonysantosjr", "worker"),
    ("Ana Reyes", "anareyes", "worker"),
    ("Anna Reyes", "annareyes", "worker"),
    ("Maria Concepcion Villanueva-Dela Paz", "mariaconcepcionvdp", "worker"),
    ("Jose Emmanuel Bartolome Macaraeg", "joseemmanuelbm", "worker"),
    ("Joel Cruz", "joelcruz", "worker"),
    ("Joey Cruz", "joeycruz", "worker"),
    ("Liza Mercado", "lizamercado", "worker"),          # also holds a seat in Baguio Textile Mills (L7)
    ("Rodel Ignacio", "rodelignacio", "worker"),        # has left the hive (L5)
    ("Rowena Tolentino", "rowenatolentino", "worker"),
    ("Arnel Domingo", "arneldomingo", "worker"),
    ("Jerome Navarro", "jeromenavarro", "worker"),
    ("Kristine Aquino", "kristineaquino", "worker"),
    ("Ramil Gutierrez", "ramilgutierrez", "worker"),
    ("Precious Manalo", "preciousmanalo", "worker"),
    ("Edgardo Salazar", "edgardosalazar", "worker"),
    ("Nestor Valdez", "nestorvaldez", "worker"),
    ("Jocelyn Fernandez", "jocelynfernandez", "worker"),
    ("Benjie Castro", "benjiecastro", "worker"),
    ("Alma Soriano", "almasoriano", "worker"),
    ("Ronaldo Padilla", "ronaldopadilla", "worker"),
    ("Michelle Ramos", "michelleramos", "worker"),
    ("Teodoro Agustin", "teodoroagustin", "worker"),
    ("Gina Lacson", "ginalacson", "worker"),
    ("Wilson Ocampo", "wilsonocampo", "worker"),
    ("Hazel Torres", "hazeltorres", "worker"),
]
TWO_HIVES = "Liza Mercado"
LEFT = "Rodel Ignacio"
ASSETS = [("BRM-P-101", "Crude charge pump P-101"), ("BRM-P-102", "Crude charge pump P-102"),
          ("BRM-C-201", "Recycle gas compressor C-201"), ("BRM-E-301", "Feed/effluent exchanger E-301"),
          ("BRM-F-401", "Process heater F-401"), ("BRM-T-501", "Storage tank T-501"),
          ("BRM-V-601", "Separator V-601"), ("BRM-M-701", "Cooling water fan motor M-701"),
          ("BRM-B-801", "Boiler feed pump B-801"), ("BRM-K-901", "Instrument air compressor K-901")]
CATEGORIES = ["Mechanical", "Electrical", "Instrumentation"]
MAINT = ["Breakdown / Corrective", "Preventive Maintenance", "Inspection", "Project Work"]
POST_CATS = ["general", "safety", "technical", "announcement"]
EMOJI = ["thumbs_up", "wrench", "fire", "eyes"]
PARTS = ["Mechanical seal 2.5in", "Bearing 6316 C3", "V-belt B68", "Gasket 6in 300#", "Coupling insert L-110",
         "Pressure transmitter 0-40 bar", "Thermocouple type K", "Solenoid valve 24VDC", "Contactor 40A", "Fuse 63A gG"]


def _ts(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat()


def _ensure_member(client, hive_id: str, display: str, username: str, role: str, status: str, log) -> str | None:
    email = f"{username}{AUTH_DOMAIN}"
    try:
        uid = client.auth.admin.create_user({"email": email, "password": TEST_PASSWORD, "email_confirm": True}).user.id
    except Exception as e:
        if not any(w in str(e).lower() for w in ("already", "exists", "registered")):
            raise
        uid = next((u.id for u in client.auth.admin.list_users() if getattr(u, "email", None) == email), None)
    if not uid:
        log(f"  WARN full hive {display}: no account")
        return None
    if not (client.table("worker_profiles").select("auth_uid").eq("auth_uid", uid).execute().data or []):
        client.table("worker_profiles").insert({"auth_uid": uid, "username": username, "display_name": display}).execute()
    if not (client.table("hive_members").select("id").eq("hive_id", hive_id).eq("worker_name", display).execute().data or []):
        client.table("hive_members").insert({"hive_id": hive_id, "auth_uid": uid, "worker_name": display,
                                             "role": role, "status": status}).execute()
    return uid


def seed_full_hive(client, log) -> dict:
    rnd = _random.Random(30)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    year_ago = now - timedelta(days=365)
    if not (client.table("hives").select("id").eq("id", FULL_HIVE_ID).execute().data or []):
        client.table("hives").insert({"id": FULL_HIVE_ID, "name": FULL_HIVE_NAME, "invite_code": "FULL30",
                                      "created_by": "Seed Admin", "intent": "maintenance"}).execute()
    uids = {}
    for display, username, role in MEMBERS:
        uid = _ensure_member(client, FULL_HIVE_ID, display, username, role, "active", log)
        if uid:
            uids[display] = uid
    second = PINNED_HIVE_IDS.get(SECOND_HIVE)
    if second and TWO_HIVES in uids:
        _ensure_member(client, second, TWO_HIVES, "lizamercado", "worker", "active", log)
    # each list is filled once: a section whose table already holds this hive's rows is left as it is (a run that stopped
    # partway resumes with the sections it never reached)
    def has(table):
        return (client.table(table).select("id", count="exact", head=True).eq("hive_id", FULL_HIVE_ID).execute().count or 0) > 0
    people = [m[0] for m in MEMBERS if m[0] in uids]
    when = lambda: year_ago + timedelta(seconds=rnd.randint(0, 365 * 86400 - 3600))
    rows = 0

    # the work log - about one entry a day across the year, by many hands
    logs = []
    for _ in range(0 if has("logbook") else 420):
        who, (tag, _name) = rnd.choice(people), rnd.choice(ASSETS)
        d = when()
        closed = rnd.random() < 0.8
        logs.append({"hive_id": FULL_HIVE_ID, "worker_name": who, "auth_uid": uids[who], "date": _ts(d), "machine": tag,
                     "category": rnd.choice(CATEGORIES), "maintenance_type": rnd.choice(MAINT),
                     "problem": f"{rnd.choice(['Vibration high', 'Seal leak', 'Trip on overload', 'Low discharge pressure', 'Noisy bearing', 'Temperature alarm'])} on {tag}",
                     "action": rnd.choice(["Replaced seal", "Re-aligned coupling", "Cleaned strainer", "Reset and monitored", "Tightened terminals"]),
                     "status": "Closed" if closed else "Open", "closed_at": _ts(d + timedelta(hours=rnd.randint(1, 30))) if closed else None,
                     "created_at": _ts(d)})
    for i in range(0, len(logs), 200):
        client.table("logbook").insert(logs[i:i + 200]).execute()
    rows += len(logs)

    # PM assets and a year of completions
    pm = []
    for tag, name in ([] if has("pm_assets") else ASSETS):
        who = rnd.choice(people[:3])
        pm.append({"hive_id": FULL_HIVE_ID, "worker_name": who, "auth_uid": uids[who], "asset_name": name, "tag_id": tag,
                   "category": rnd.choice(CATEGORIES)})
    pm_ids = [r["id"] for r in (client.table("pm_assets").insert(pm).execute().data or [])] if pm else []
    comps = []
    for _ in range(220 if pm_ids and not has("pm_completions") else 0):
        who = rnd.choice(people)
        comps.append({"hive_id": FULL_HIVE_ID, "worker_name": who, "auth_uid": uids[who], "asset_id": rnd.choice(pm_ids),
                      "completed_at": _ts(when())})
    for i in range(0, len(comps), 200):
        client.table("pm_completions").insert(comps[i:i + 200]).execute()
    rows += len(pm) + len(comps)

    # parts on the hive's shelf and their movements - each ledger built by inventory.py's _gen_ledger, so every
    # movement chains (qty_after = previous + change, a use is negative) and the shelf's balance IS the newest
    # qty_after: the stock-conserved and parts-decrement probes hold here as they do everywhere else. _gen_ledger draws
    # from the global random, so it runs inside a saved state and leaves the orchestrator's stream untouched.
    items, moves = [], []
    if not has("inventory_items"):
        import random as _g
        from .inventory import _gen_ledger
        from .utils import text_id
        saved = _g.getstate()
        _g.seed(3030)
        try:
            for k, part in enumerate(PARTS * 4):
                who = rnd.choice(people)
                final, txns = _gen_ledger(rnd.randint(0, 20), False)
                iid = text_id("inv")
                items.append({"id": iid, "hive_id": FULL_HIVE_ID, "worker_name": who, "auth_uid": uids[who],
                              "submitted_by": who, "part_name": f"{part} #{k + 1}", "part_number": f"BRM-{k + 1:04d}",
                              "qty_on_hand": final, "min_qty": rnd.randint(1, 5), "unit": "pcs", "status": "approved",
                              "created_at": _ts(year_ago + timedelta(days=rnd.randint(0, 200)))})
                for t in txns:
                    mover = rnd.choice(people)
                    moves.append({"id": text_id("tx"), "hive_id": FULL_HIVE_ID, "worker_name": mover, "auth_uid": uids[mover],
                                  "item_id": iid, "type": t["type"], "qty_change": t["qty_change"], "qty_after": t["qty_after"],
                                  "created_at": _ts(t["ts"]) if hasattr(t["ts"], "isoformat") else t["ts"]})
        finally:
            _g.setstate(saved)
        client.table("inventory_items").insert(items).execute()
        for i in range(0, len(moves), 200):
            client.table("inventory_transactions").insert(moves[i:i + 200]).execute()
    rows += len(items) + len(moves)

    # projects and their items
    for n, pname in enumerate([] if has("projects") else ["Turnaround 2026 - crude unit", "Cooling tower rebuild", "Instrument air upgrade", "Tank T-501 inspection"]):
        lead = people[n % 3]
        proj = client.table("projects").insert({"hive_id": FULL_HIVE_ID, "worker_name": lead, "auth_uid": uids[lead],
                                                "project_code": f"BRM-2026-{n + 1:03d}", "name": pname,
                                                "project_type": ["shutdown", "capex", "workorder", "contractor"][n], "status": "active"}).execute().data[0]
        its = [{"project_id": proj["id"], "hive_id": FULL_HIVE_ID, "title": f"{pname}: step {k + 1}",
                "owner_name": rnd.choice(people), "status": rnd.choice(["pending", "in_progress", "done"])} for k in range(8)]
        client.table("project_items").insert(its).execute()
        rows += 1 + len(its)

    # the discussion board: posts from many members, replies, and reactions from up to half the hive
    posts = []
    for _ in range(0 if has("community_posts") else 70):
        who, d = rnd.choice(people), when()
        cat = rnd.choice(POST_CATS)
        posts.append({"hive_id": FULL_HIVE_ID, "author_name": who, "auth_uid": uids[who], "category": cat,
                      # a supervisor shares the hive's safety notes with every WorkHive team (the Global feed, L7)
                      "public": who in people[:3] and cat == "safety",
                      "content": rnd.choice(["Anyone seen P-101 run hot after the seal change?", "Reminder: LOTO on C-201 before the bearing job.",
                                             "Spare 6316 bearings are in bay 3, logged in inventory.", "Turnaround permits are due Friday.",
                                             "Shared the vibration trend for M-701 in the logbook - looks like misalignment.",
                                             "Safety walk tomorrow 7am, meet at the control room."]),
                      "created_at": _ts(d)})
    made = (client.table("community_posts").insert(posts).execute().data or []) if posts else []
    if not made and not has("community_replies"):   # a run that stopped after the posts: answer the posts already there
        made = client.table("community_posts").select("id, created_at").eq("hive_id", FULL_HIVE_ID).execute().data or []
    replies, reacts = [], []
    for p in made:
        for _ in range(rnd.randint(0, 5)):
            who = rnd.choice(people)
            # dated after its post, as the base seeder does: the reply rate limit counts an author's last 15 seconds
            at = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) + timedelta(minutes=rnd.randint(5, 4000))
            replies.append({"post_id": p["id"], "hive_id": FULL_HIVE_ID, "author_name": who, "auth_uid": uids[who],
                            "content": rnd.choice(["Seen it too.", "Will check on night shift.", "Thanks, noted.", "Logged the reading."]),
                            "created_at": _ts(min(at, now))})
        for who in rnd.sample(people, rnd.randint(0, 15)):
            at = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) + timedelta(minutes=rnd.randint(1, 2000))
            reacts.append({"post_id": p["id"], "hive_id": FULL_HIVE_ID, "worker_name": who, "auth_uid": uids[who],
                           "emoji": rnd.choice(EMOJI), "created_at": _ts(min(at, now))})
    for i in range(0, len(replies), 200):
        client.table("community_replies").insert(replies[i:i + 200]).execute()
    for i in range(0, len(reacts), 200):
        client.table("community_reactions").insert(reacts[i:i + 200]).execute()
    rows += len(made) + len(replies) + len(reacts)

    # the member who has left: his work stays, his seat goes (L5)
    client.table("hive_members").update({"status": "deactivated"}).eq("hive_id", FULL_HIVE_ID).eq("worker_name", LEFT).execute()
    log(f"  full hive: {FULL_HIVE_NAME} - {len(uids)} members, {rows} attributed rows over a year "
        f"({TWO_HIVES} also in {SECOND_HIVE}; {LEFT} has left)")
    return {"full_hive_members": len(uids), "full_hive_rows": rows}
