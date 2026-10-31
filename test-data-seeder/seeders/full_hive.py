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
import subprocess
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


# the register's discipline per machine type (the tag's middle letter), in the vocabulary asset_nodes already holds
ISO_CLASS = {"P": "Mechanical", "B": "Mechanical", "C": "Mechanical", "E": "Mechanical", "F": "Mechanical",
             "T": "Mechanical", "V": "Mechanical", "M": "Electrical", "K": "Pneumatic"}
# which machines each part fits (PARTS by index) - a seal goes on the pumps, a thermocouple on the heater
PART_FITS = [["BRM-P-101", "BRM-P-102", "BRM-B-801"], ["BRM-P-101", "BRM-P-102", "BRM-M-701"], ["BRM-M-701", "BRM-K-901"],
             ["BRM-E-301", "BRM-V-601"], ["BRM-P-101", "BRM-C-201"], ["BRM-C-201", "BRM-V-601"], ["BRM-F-401"],
             ["BRM-K-901"], ["BRM-M-701", "BRM-K-901"], ["BRM-M-701"]]


# (failure mode, effect, cause) - what a refinery's rotating and static equipment actually fails by
FAILURE_MODES = [
    ("Mechanical seal leak", "Process fluid released at the seal; unit slowed to isolate", "Seal face wear from dry running"),
    ("Bearing overheating", "Trip on high bearing temperature", "Lubricant degraded past its change interval"),
    ("Coupling misalignment", "High vibration, accelerated bearing wear", "Soft foot after a base repair"),
    ("Impeller erosion", "Discharge pressure below duty", "Abrasive fines in the feed"),
    ("Tube fouling", "Heat duty lost, outlet temperature high", "Deposits from the cooling water side"),
    ("Burner flame instability", "Heater trips on flame failure", "Fuel gas pressure swings"),
    ("Corrosion under insulation", "Wall thinning found on inspection", "Wet insulation on a cyclic-temperature line"),
    ("Motor winding insulation breakdown", "Motor trips on earth fault", "Moisture ingress at the terminal box"),
    ("Valve passing", "Loss of isolation for maintenance", "Seat damage from throttling service"),
    ("Instrument air moisture", "Control valves sticking", "Dryer desiccant spent"),
]


# (seller, title, category, condition, price) - the plant's surplus, sold by two members
SURPLUS = [("Joel Cruz", "Spare mechanical seal set, 2.5in", "Pumps", "new", 18500),
           ("Joel Cruz", "Refurbished bearing housing for P-101", "Pumps", "refurb", 9200),
           ("Joel Cruz", "Used V-belts B68 (box of 6)", "Filters", "used", 1500),
           ("Ernesto Villareal", "Instrument air dryer cartridge", "Compressors", "new", 12750),
           ("Ernesto Villareal", "40A contactor, unused spare", "Switchgear", "new", 4300)]

# (decision, title, scope) - three change orders per project: one approved, one waiting, one refused
CHANGE_ORDERS = [
    ("approved", "Add a second blind on the suction line", "Isolation for the seal job needs a second spectacle blind"),
    ("pending", "Replace the corroded nozzle reinforcement", "Inspection found wall loss past the corrosion allowance"),
    ("rejected", "Repaint the whole tank roof", "Cosmetic coating loss on the roof plates"),
]


# a PM program's tasks: (what is done, how often) - the platform's own frequency vocabulary
PM_TASKS = [("Check bearing temperature and vibration", "Weekly"), ("Inspect coupling, guard and anchor bolts", "Monthly"),
            ("Change lubricating oil and clean the breather", "Quarterly")]


def _link_completions_to_tasks(log) -> None:
    """Give each task-less completion one of its machine's tasks (the k-th completion of a machine gets task k mod n),
    as one seed-only statement with triggers off: an UPDATE would re-run the completion's XP and audit triggers for work
    done months ago."""
    sql = ("begin; set local session_replication_role = replica;\n"
           "with c as (select id, asset_id, row_number() over (partition by asset_id order by completed_at, id) - 1 as k "
           f"from public.pm_completions where hive_id = '{FULL_HIVE_ID}' and scope_item_id is null), "
           "t as (select id, asset_id, row_number() over (partition by asset_id order by item_text, id) - 1 as j, "
           f"count(*) over (partition by asset_id) as n from public.pm_scope_items where hive_id = '{FULL_HIVE_ID}') "
           "update public.pm_completions pc set scope_item_id = t.id from c join t on t.asset_id = c.asset_id and t.j = c.k % t.n "
           "where pc.id = c.id;\ncommit;\n")
    try:
        r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                            "-v", "ON_ERROR_STOP=1", "-q"], input=sql, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            log(f"  WARN full hive: completions not linked to tasks: {r.stderr.strip()[:160]}")
    except Exception as e:
        log(f"  WARN full hive: completions not linked to tasks: {e}")


def _date_project_activity(log) -> None:
    """A project was last updated when its team last reported on it - not the day the seed (or its backfill) touched it,
    which made every project read 'updated 34m ago'. Seed-only, triggers off (updated_at is what a touch trigger sets)."""
    sql = ("begin; set local session_replication_role = replica;\n"
           "update public.projects p set updated_at = g.last from (select project_id, max(created_at) as last "
           f"from public.project_progress_logs where hive_id = '{FULL_HIVE_ID}' group by project_id) g "
           "where p.id = g.project_id and p.updated_at is distinct from g.last;\ncommit;\n")
    try:
        r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                            "-v", "ON_ERROR_STOP=1", "-q"], input=sql, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            log(f"  WARN full hive: project activity not dated: {r.stderr.strip()[:160]}")
    except Exception as e:
        log(f"  WARN full hive: project activity not dated: {e}")


# A step's progress is written with its status: project-manager's chip writes done 100, in progress at least 50, pending 0.
# The seed drew a status and left progress at 0, so a project with 4 of 9 steps done reported "0% complete" (2026-10-30).
ITEM_PROGRESS = {"done": 100, "in_progress": 50, "pending": 0}


def _cohere_item_progress(log) -> None:
    """Give a hive seeded before ITEM_PROGRESS the progress its steps' statuses mean. Seed-only, triggers off: an UPDATE
    would write a 'changed a scope item' trail row and stamp every step updated today."""
    sql = ("begin; set local session_replication_role = replica;\n"
           f"update public.project_items set pct_complete = 100 where hive_id = '{FULL_HIVE_ID}' and status = 'done' "
           "and coalesce(pct_complete, 0) < 100;\n"
           f"update public.project_items set pct_complete = 50 where hive_id = '{FULL_HIVE_ID}' and status = 'in_progress' "
           "and coalesce(pct_complete, 0) = 0;\ncommit;\n")
    try:
        r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                            "-v", "ON_ERROR_STOP=1", "-q"], input=sql, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            log(f"  WARN full hive: scope progress not set: {r.stderr.strip()[:160]}")
    except Exception as e:
        log(f"  WARN full hive: scope progress not set: {e}")


def _project_dates(n: int, year_ago: datetime) -> dict:
    """A project runs about four months, the four of them staggered through the year."""
    start = (year_ago + timedelta(days=60 + n * 40)).date()
    return {"start_date": start.isoformat(), "end_date": (start + timedelta(days=120)).isoformat()}


def _item_plan(n: int, k: int, year_ago: datetime) -> dict:
    """Step k of project n: a WBS code and two weeks of the project's four months each."""
    start = (year_ago + timedelta(days=60 + n * 40 + k * 14)).date()
    return {"wbs_code": f"{n + 1}.{k + 1}", "planned_start": start.isoformat(),
            "planned_end": (start + timedelta(days=13)).isoformat()}


def _parts_links(k: int, node_of: dict) -> list:
    return [node_of[t] for t in PART_FITS[k % len(PART_FITS)] if node_of.get(t)]


def _link_existing_to_assets(log) -> None:
    """Link a full hive seeded before its asset register (2026-10-30): each logbook entry to its machine by tag, each part
    to the machines it fits. Run as one seed-only statement with triggers off - an UPDATE would have written an
    "amended a closed entry" audit row for every closed entry, queued 420 re-embeds and stamped each entry edited, none of
    which is true of a link the entry was always meant to carry."""
    fits = ",".join(f"({k}, '{t}')" for k, tags in enumerate(PART_FITS) for t in tags)
    sql = ("begin; set local session_replication_role = replica;\n"
           f"update public.logbook l set asset_node_id = n.id from public.asset_nodes n where l.hive_id = '{FULL_HIVE_ID}' "
           f"and n.hive_id = l.hive_id and n.tag = l.machine and l.asset_node_id is null;\n"
           f"update public.inventory_items i set linked_asset_node_ids = s.ids from (select i2.id, array_agg(n.id) ids "
           f"from public.inventory_items i2 join (values {fits}) f(k, tag) "
           f"on f.k = ((substring(i2.part_number from '[0-9]+$')::int - 1) % {len(PART_FITS)}) "
           f"join public.asset_nodes n on n.hive_id = i2.hive_id and n.tag = f.tag "
           f"where i2.hive_id = '{FULL_HIVE_ID}' group by i2.id) s where i.id = s.id "
           f"and coalesce(cardinality(i.linked_asset_node_ids), 0) = 0;\ncommit;\n")
    try:
        r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                            "-v", "ON_ERROR_STOP=1", "-q"], input=sql, capture_output=True, text=True, timeout=120)
        log("  full hive: existing entries and parts linked to the asset register" if r.returncode == 0
            else f"  WARN full hive: links not made: {r.stderr.strip()[:160]}")
    except Exception as e:
        log(f"  WARN full hive: links not made: {e}")


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

    # the asset register - the plant's ten machines, registered by its supervisors before anyone logged work on them.
    # (2026-10-30, Wave HS: the hive had none, so an asset's history, its linked parts and every page reading asset_nodes
    # had nothing to show for thirty members' work.) Its own random stream: the sections below draw exactly as before.
    node_of = {r["tag"]: r["id"] for r in (client.table("asset_nodes").select("id, tag").eq("hive_id", FULL_HIVE_ID)
                                            .execute().data or [])}
    nodes_made = False
    if not node_of:
        ar = _random.Random(3031)
        nodes = []
        for tag, name in ASSETS:
            by = ar.choice(people[:3])
            nodes.append({"hive_id": FULL_HIVE_ID, "worker_name": by, "auth_uid": uids[by], "submitted_by": by,
                          "level": "equipment", "tag": tag, "name": name, "iso_class": ISO_CLASS.get(tag.split("-")[1], "Other"),
                          "criticality": ar.choice(["high", "high", "medium", "low"]), "status": "approved",
                          "created_at": _ts(year_ago - timedelta(days=ar.randint(5, 30)))})
        node_of = {r["tag"]: r["id"] for r in (client.table("asset_nodes").insert(nodes).execute().data or [])}
        nodes_made = True
        rows += len(node_of)

    # the reliability record - two failure modes per machine, proposed through the year by the supervisors and the senior
    # hands, most approved by a supervisor and a few still waiting (2026-10-30, Wave HS: the hive had none, so asset-hub's
    # FMEA list - and a supervisor's approvals - had nothing to show). Its own random stream, like the register's.
    if node_of and not has("rcm_fmea_modes"):
        fr = _random.Random(3032)
        proposers = people[:3] + [p for p in ("Jerome Navarro", "Kristine Aquino", "Ramil Gutierrez") if p in uids]
        modes = []
        for tag, _name in ASSETS:
            for mode, effect, cause in fr.sample(FAILURE_MODES, 2):
                by, d = fr.choice(proposers), year_ago + timedelta(days=fr.randint(10, 330))
                approved = fr.random() < 0.75
                modes.append({"hive_id": FULL_HIVE_ID, "asset_id": node_of[tag], "function_text": f"Keep {tag} in service at rated duty",
                              "failure_mode": mode, "effect_text": effect, "cause_text": cause,
                              "severity": fr.randint(4, 9), "occurrence": fr.randint(2, 7), "detection": fr.randint(2, 7),
                              "consequence_class": fr.choice(["safety", "production", "cost"]), "source": "manual",
                              "created_by": by, "created_at": _ts(d),
                              "approved_by": fr.choice(people[:3]) if approved else None,
                              "approved_at": _ts(d + timedelta(days=fr.randint(1, 14))) if approved else None})
        client.table("rcm_fmea_modes").insert(modes).execute()
        rows += len(modes)

    # the work log - about one entry a day across the year, by many hands
    logs = []
    for _ in range(0 if has("logbook") else 420):
        who, (tag, _name) = rnd.choice(people), rnd.choice(ASSETS)
        d = when()
        closed = rnd.random() < 0.8
        logs.append({"hive_id": FULL_HIVE_ID, "worker_name": who, "auth_uid": uids[who], "date": _ts(d), "machine": tag,
                     "asset_node_id": node_of.get(tag),
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
    if node_of:   # each registered machine knows its PM program (asset_nodes.pm_asset_id), as asset_brain.py bridges by tag
        for r in client.table("pm_assets").select("id, tag_id").eq("hive_id", FULL_HIVE_ID).execute().data or []:
            if node_of.get(r["tag_id"]):
                client.table("asset_nodes").update({"pm_asset_id": r["id"]}).eq("id", node_of[r["tag_id"]]) \
                    .is_("pm_asset_id", "null").execute()
    # each PM program's tasks - what is done to the machine and how often (2026-10-30, Wave HS: the programs had none, so
    # every card read "0 PM tasks" and every completion "Unknown task")
    tasks_of = {}
    pm_rows = client.table("pm_assets").select("id").eq("hive_id", FULL_HIVE_ID).order("tag_id").execute().data or []
    if pm_rows and not has("pm_scope_items"):
        tasks = [{"asset_id": r["id"], "hive_id": FULL_HIVE_ID, "item_text": text, "frequency": freq,
                  "anchor_date": year_ago.date().isoformat()} for r in pm_rows for text, freq in PM_TASKS]
        client.table("pm_scope_items").insert(tasks).execute()
        rows += len(tasks)
    for t in client.table("pm_scope_items").select("id, asset_id").eq("hive_id", FULL_HIVE_ID).order("item_text").execute().data or []:
        tasks_of.setdefault(t["asset_id"], []).append(t["id"])
    comps = []
    for k in range(220 if pm_ids and not has("pm_completions") else 0):
        who, aid = rnd.choice(people), rnd.choice(pm_ids)
        comps.append({"hive_id": FULL_HIVE_ID, "worker_name": who, "auth_uid": uids[who], "asset_id": aid,
                      "scope_item_id": (tasks_of.get(aid) or [None])[k % max(1, len(tasks_of.get(aid) or [None]))],
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
                              "linked_asset_node_ids": _parts_links(k, node_of),
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

    if nodes_made and not logs:   # the register arrived after the hive's work: link what is already there
        _link_existing_to_assets(log)
    _link_completions_to_tasks(log)   # completions seeded before the programs had tasks get one of their machine's tasks
    _date_project_activity(log)      # a project was last updated by its latest progress report, not by the seed

    # projects and their items
    for n, pname in enumerate([] if has("projects") else ["Turnaround 2026 - crude unit", "Cooling tower rebuild", "Instrument air upgrade", "Tank T-501 inspection"]):
        lead = people[n % 3]
        proj = client.table("projects").insert({"hive_id": FULL_HIVE_ID, "worker_name": lead, "auth_uid": uids[lead],
                                                "project_code": f"BRM-2026-{n + 1:03d}", "name": pname, "owner_name": lead,
                                                **_project_dates(n, year_ago),
                                                "project_type": ["shutdown", "capex", "workorder", "contractor"][n], "status": "active"}).execute().data[0]
        its = [{"project_id": proj["id"], "hive_id": FULL_HIVE_ID, "title": f"{pname}: step {k + 1}",
                "owner_name": rnd.choice(people), "status": (st := rnd.choice(["pending", "in_progress", "done"])),
                "pct_complete": ITEM_PROGRESS[st], **_item_plan(n, k, year_ago)} for k in range(8)]
        client.table("project_items").insert(its).execute()
        rows += 1 + len(its)

    # a project made before the seed gave projects an owner and dates (2026-10-30): every other project carries both, and
    # a card without them read "owner -" with no date
    for n, pj in enumerate(client.table("projects").select("id, worker_name, owner_name").eq("hive_id", FULL_HIVE_ID)
                           .order("project_code").execute().data or []):
        if not pj.get("owner_name"):
            client.table("projects").update({"owner_name": pj["worker_name"], **_project_dates(n, year_ago)}).eq("id", pj["id"]).execute()
        # ...and its scope items a WBS code and a plan, as every other project's items carry
        for k, it in enumerate(client.table("project_items").select("id, planned_end").eq("project_id", pj["id"])
                               .order("created_at").order("id").execute().data or []):
            if not it.get("planned_end"):
                client.table("project_items").update(_item_plan(n, k, year_ago)).eq("id", it["id"]).execute()
    _cohere_item_progress(log)

    # the plant's CMMS (SAP PM) syncs six work orders on six machines; three disagree with the machine's latest member entry
    # (2026-10-30, Wave HS: no hive held a synced work order, so integrations' conflict list had never been exercised)
    if not has("external_sync"):
        ext = []
        for k, (tag, _name) in enumerate(ASSETS[:6]):
            last = (client.table("logbook").select("status").eq("hive_id", FULL_HIVE_ID).eq("machine", tag)
                    .order("date", desc=True).order("id").limit(1).execute().data or [{}])[0].get("status") or "Open"
            disagree = k % 2 == 0
            ext.append({"hive_id": FULL_HIVE_ID, "system_type": "SAP_PM", "external_id": f"WO-4000{k + 1}",
                        "entity_type": "work_order", "workhive_table": "logbook", "sync_status": "success",
                        "status": ("Closed" if last == "Open" else "Open") if disagree else ("Closed" if last == "Closed" else "Open"),
                        "sync_payload": {"machine": tag, "order_type": "PM01"},
                        "last_synced_at": _ts(now - timedelta(hours=k + 1))})
        client.table("external_sync").insert(ext).execute()
        rows += len(ext)

    # two members sell the plant's surplus on the marketplace - Joel Cruz (worker) and Ernesto Villareal (supervisor) - and
    # teammates and outside buyers ask about it, some answered (2026-10-30, Wave HS: no member sold anything, so the
    # seller inbox, the hive's own listings and a member's seller profile had nothing a hive of thirty produces)
    if not (client.table("marketplace_listings").select("id", count="exact", head=True).eq("hive_id", FULL_HIVE_ID).execute().count or 0):
        mr = _random.Random(3035)
        for seller in ("Joel Cruz", "Ernesto Villareal"):
            if seller in uids and not (client.table("marketplace_sellers").select("id").eq("worker_name", seller).execute().data or []):
                client.table("marketplace_sellers").insert({"worker_name": seller, "auth_uid": uids[seller], "hive_id": FULL_HIVE_ID,
                                                            "tier": "bronze"}).execute()
        lst = []
        for k, (seller, title, cat, cond, price) in enumerate(SURPLUS):
            d = year_ago + timedelta(days=200 + k * 20)
            lst.append({"hive_id": FULL_HIVE_ID, "seller_name": seller, "auth_uid": uids.get(seller), "section": "parts",
                        "category": cat, "title": title, "description": f"{title} - surplus from the {FULL_HIVE_NAME} stores.",
                        "price": price, "condition": cond, "location": "Batangas", "status": "published",
                        "created_at": _ts(d), "updated_at": _ts(d)})
        made = client.table("marketplace_listings").insert(lst).execute().data or []
        inq = []
        for L in made:
            for j in range(mr.randint(2, 4)):
                buyer = mr.choice([p for p in people if p != L["seller_name"]] + ["Rogelio Baltazar (outside buyer)", "Teresita Villanueva (outside buyer)"])
                d = datetime.fromisoformat(L["created_at"]) + timedelta(days=mr.randint(1, 20), hours=j)
                replied = mr.random() < 0.5
                inq.append({"listing_id": L["id"], "hive_id": FULL_HIVE_ID, "buyer_name": buyer, "buyer_auth_uid": uids.get(buyer),
                            "seller_name": L["seller_name"], "message": mr.choice(["Is this still available?", "Can you do 10% less if I pick up?",
                                                                                  "Does it fit a Grundfos CR 95?", "Can I see it Thursday?"]),
                            "status": "replied" if replied else "pending", "created_at": _ts(d),
                            "reply_text": "Yes - come by the stores, ask for me." if replied else None,
                            "replied_at": _ts(d + timedelta(hours=5)) if replied else None})
        if inq:
            client.table("marketplace_inquiries").insert(inq).execute()
        rows += len(lst) + len(inq)

    # a member who also takes freelance jobs on the hailing marketplace - Joel Cruz, mechanical fitter (2026-10-30, Wave
    # HS: no member was a provider, so a provider's own card on achievements and marketplace-seller had nothing to show)
    if "Joel Cruz" in uids and not (client.table("service_providers").select("id").eq("auth_uid", uids["Joel Cruz"]).execute().data or []):
        client.table("service_providers").insert({"provider_type": "freelancer", "auth_uid": uids["Joel Cruz"], "worker_name": "Joel Cruz",
                                                  "display_name": "Joel Cruz - pump and seal fitting", "categories": ["Mechanical"],
                                                  "service_areas": ["Batangas City"], "base_location": "SRID=4326;POINT(121.0583 13.7565)",
                                                  "availability": "offline", "created_at": _ts(year_ago + timedelta(days=150))}).execute()
        rows += 1

    # the projects' people, their changes and their progress - a team of five per project (owner + four roles assigned by
    # a supervisor), three change orders raised by the team and decided by the supervisor, six weekly progress reports
    # (2026-10-30, Wave HS: the projects had no team, change or report, so project-manager's lists of thirty members'
    # work had nothing to show). Its own random stream, like the register's.
    projs = client.table("projects").select("id, name, worker_name, project_type").eq("hive_id", FULL_HIVE_ID).order("project_code").execute().data or []
    if projs and not has("project_roles"):
        pr = _random.Random(3033)
        roles, cos, reports = [], [], []
        for n, pj in enumerate(projs):
            start = year_ago + timedelta(days=60 + n * 40)
            sup, lead = people[n % 3], pj["worker_name"]
            team = pr.sample([p for p in people if p != lead], 4)
            roles.append({"project_id": pj["id"], "hive_id": FULL_HIVE_ID, "worker_name": lead, "role": "owner",
                          "assigned_by": sup, "assigned_at": _ts(start)})
            for who, role in zip(team, ["planner", "safety_officer", "cost_engineer", "reviewer"]):
                roles.append({"project_id": pj["id"], "hive_id": FULL_HIVE_ID, "worker_name": who, "role": role,
                              "assigned_by": sup, "assigned_at": _ts(start + timedelta(days=pr.randint(0, 5)))})
            # a change order exists only where project-manager.html offers one: its Change orders tab is hidden on a work
            # order, so a CO seeded there was a decision no supervisor could ever see or make (HS W1 race walk, 2026-10-30)
            for k, (status, title, scope) in enumerate(CHANGE_ORDERS if pj.get("project_type") != "workorder" else []):
                d = start + timedelta(days=20 + 25 * k)
                req = pr.choice(team + [lead])
                cos.append({"project_id": pj["id"], "hive_id": FULL_HIVE_ID, "co_number": f"CO-{k + 1:03d}", "title": title,
                            "scope_change": scope, "reason": "Found during execution", "cost_impact_php": pr.randint(15, 250) * 1000,
                            "schedule_impact_days": pr.randint(0, 10), "status": status, "requested_by": req,
                            "requested_at": _ts(d), "created_at": _ts(d),
                            "approved_by": sup if status != "pending" else None,
                            "approved_at": _ts(d + timedelta(days=2)) if status != "pending" else None,
                            "rejection_reason": "Outside this turnaround's window - raise it for the next one" if status == "rejected" else None})
            for w in range(6):
                d = start + timedelta(days=7 * (w + 1))
                rep = pr.choice(team + [lead])
                reports.append({"project_id": pj["id"], "hive_id": FULL_HIVE_ID, "log_date": d.date().isoformat(), "reported_by": rep,
                                "auth_uid": uids[rep], "pct_complete": min(100, 14 * (w + 1)), "hours_worked": pr.randint(6, 40),
                                "notes": pr.choice(["Scaffolding up, permits signed", "Blinds installed on the suction side",
                                                    "Bearings replaced, alignment checked", "Waiting on the gasket delivery",
                                                    "Hydrotest passed", "Punch list walked with operations"]),
                                "created_at": _ts(d)})
        client.table("project_roles").insert(roles).execute()
        client.table("project_change_orders").insert(cos).execute()
        client.table("project_progress_logs").insert(reports).execute()
        rows += len(roles) + len(cos) + len(reports)

    # engineering calculations by the hive's engineers, through the year
    if not has("engineering_calcs"):
        cr = _random.Random(3034)
        calcs = []
        for k in range(12):
            by, d = cr.choice(people[:3] + people[13:18]), year_ago + timedelta(days=cr.randint(5, 350))
            if k % 2:
                calcs.append({"hive_id": FULL_HIVE_ID, "worker_name": by, "auth_uid": uids[by], "discipline": "Mechanical",
                              "calc_type": "Pump Sizing (TDH)", "project_name": f"{ASSETS[k % 3][1]} rerate",
                              "inputs": {"tdh_m": cr.randint(20, 60), "flow_lps": cr.randint(8, 30)},
                              "results": {"power_kw": round(cr.uniform(8, 40), 1), "efficiency": 0.78}, "created_at": _ts(d)})
            else:
                calcs.append({"hive_id": FULL_HIVE_ID, "worker_name": by, "auth_uid": uids[by], "discipline": "Electrical",
                              "calc_type": "Cable Sizing (Voltage Drop)", "project_name": "M-701 motor feeder",
                              "inputs": {"length_m": cr.randint(40, 180), "current_a": cr.randint(30, 120)},
                              "results": {"size_mm2": cr.choice([16, 25, 35, 50]), "vd_pct": round(cr.uniform(1.2, 3.8), 2)},
                              "created_at": _ts(d)})
        client.table("engineering_calcs").insert(calcs).execute()
        rows += len(calcs)

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
