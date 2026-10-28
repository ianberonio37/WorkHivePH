"""Probe fixtures - the rows the psql probe suite grounds on, made by the seed instead of by weeks of walking (2026-10-27).

WHY: tools/psql_probes/ proves tenant isolation and write authorisation table by table, and each recipe chooses its
fixture LIVE: "a member of ONE hive, not a platform admin, whose hive holds rows in X, and a foreign hive that also
does". The local database had those rows because walks and one-off tools had written them over weeks. A clean reseed
(which the release gate's own Phase 1 performs) left these tables empty, and 40 probes failed for want of a fixture -
the suite could only pass on a database nobody could reproduce. The seeder is part of the test surface (AHK3).

WHAT: in every hive, a handful of rows per table authored by that hive's own single-hive, non-admin member (the shape the
probes select), with auth_uid AND the name set, so a read policy (hive) and a write policy (auth_uid) both have a row to
judge. Plus the two existing seeders nothing called: ai_reports.run and cmms_config_seeder (integration configs + keys).
Every row is plainly sample data ("Seed:" titles, example.test addresses, keys that open nothing).
"""
import hashlib
import secrets

from .ai_reports import run as seed_ai_reports
from .cmms_config_seeder import seed_integration_config
from .utils import batch_insert


def _authors(client) -> dict:
    """hive_id -> the member the probes would pick: active in exactly one hive, not a platform admin, supervisor first."""
    members = (client.table("hive_members").select("hive_id, auth_uid, worker_name, role, status")
               .eq("status", "active").limit(2000).execute().data or [])
    admins = {a["auth_uid"] for a in (client.table("marketplace_platform_admins").select("auth_uid").execute().data or [])}
    hives_of: dict = {}
    for m in members:
        if m.get("auth_uid"):
            hives_of.setdefault(m["auth_uid"], set()).add(m["hive_id"])
    out: dict = {}
    for m in sorted(members, key=lambda x: x.get("role") != "supervisor"):
        uid = m.get("auth_uid")
        if not uid or uid in admins or len(hives_of.get(uid, ())) != 1 or m["hive_id"] in out:
            continue
        out[m["hive_id"]] = {"auth_uid": uid, "name": m["worker_name"]}
    return out


def seed_probe_fixtures(client, log) -> dict:
    log("Seeding probe fixtures (rows the psql probes ground on, per hive)...")
    counts: dict = {}
    authors = _authors(client)
    if len(authors) < 2:
        log(f"  WARN: only {len(authors)} hive(s) have a single-hive non-admin member - cross-hive probes need two")

    def put(table, rows):
        if not rows:
            return
        try:
            counts[table] = counts.get(table, 0) + batch_insert(client, table, rows)
        except Exception as e:  # say which table, never kill the seed
            log(f"  WARN: probe fixture {table} insert failed: {type(e).__name__}: {str(e)[:160]}")

    for n, (hive_id, a) in enumerate(sorted(authors.items())):
        uid, name = a["auth_uid"], a["name"]
        slug = name.lower().replace(" ", ".")
        posts = (client.table("community_posts").select("id").eq("hive_id", hive_id).limit(2).execute().data or [])
        put("community_replies", [{"post_id": p["id"], "hive_id": hive_id, "author_name": name, "auth_uid": uid,
                                   "content": "Seed: we saw the same on our line - check the coupling alignment first."}
                                  for p in posts])
        put("community_reactions", [{"post_id": p["id"], "hive_id": hive_id, "worker_name": name, "auth_uid": uid,
                                     "emoji": "wrench"} for p in posts])
        put("resume_documents", [{"auth_uid": uid, "worker_name": name, "hive_id": hive_id, "title": f"Seed: {name} - CV",
                                  "doc": {"basics": {"name": name, "label": "Maintenance Technician"},
                                          "work": [{"name": "Seed Plant", "position": "Technician",
                                                    "startDate": "2021-03-01"}],
                                          "skills": [{"name": "Preventive maintenance", "level": "Advanced"}]}}])
        put("report_contacts", [{"hive_id": hive_id, "name": f"Seed contact {n + 1}",
                                 "email": f"seed.contact{n + 1}@example.test", "label": "Plant manager"}])
        # ★A DISMISSAL KEYED TO AN ALERT THAT EXISTS (2026-10-28). The fixture used "seed:pm-overdue:N", a key no alert ever
        # carries, so no hive's feed ever had a hidden or a seen alert, and "who hid it" was on no page for a walk to read.
        # alert-hub keys a PM alert 'pm:' + pm_asset_id for an OVERDUE asset (v_pm_scope_items_truth.is_overdue): one is
        # marked handled (hidden for the hive, under the author's name) and one seen (kept, dimmed, under the name). A fleet
        # hive has no overdue PM, so its keys come from the newest failure-signature alerts the feed lists
        # ('pattern:' + machine + ':' + rule_id-or-title, the 20 newest of v_alert_truth).
        od = (client.table("v_pm_scope_items_truth").select("pm_asset_id").eq("hive_id", hive_id).eq("is_overdue", True)
              .order("pm_asset_id").limit(200).execute().data or [])
        sig = (client.table("v_alert_truth").select("machine, rule_id, title").eq("hive_id", hive_id)
               .eq("alert_kind", "signature").order("detected_at", desc=True).order("alert_id").limit(20).execute().data or [])
        alert_keys = list(dict.fromkeys(["pm:" + k for k in sorted({r["pm_asset_id"] for r in od if r.get("pm_asset_id")})]
                                        + [f"pattern:{s.get('machine') or ''}:{s.get('rule_id') or s.get('title') or ''}"
                                           for s in sig]))[:2]
        put("alert_dismissals", [{"hive_id": hive_id, "alert_key": k, "action": act, "actor": name}
                                 for k, act in zip(alert_keys, ("handled", "acknowledged"))])
        put("analytics_snapshots", [{"hive_id": hive_id, "phase": "descriptive", "period_days": 30,
                                     "payload": {"seed": True, "mtbf_hours": None, "note": "sample snapshot"},
                                     "computed_by": name}])
        put("ai_reply_feedback", [{"hive_id": hive_id, "auth_uid": uid, "worker_name": name, "agent": "assistant",
                                   "source": "assistant", "page": "assistant.html",
                                   "question": "Seed: what is due this week?", "answer": "Seed answer.", "rating": 1}])
        put("agentic_rag_traces", [{"hive_id": hive_id, "worker_name": name, "question": "Seed: last breakdown on the line?",
                                    "route": "semantic", "citation_count": 1, "latency_ms": 900}])
        # integration configs + an API key (the sample key opens nothing: its hash is of a random value)
        try:
            seed_integration_config(client, hive_id, "generic", replace=False, log=lambda m: None)
            counts["integration_configs"] = counts.get("integration_configs", 0) + 1
        except Exception as e:
            log(f"  WARN: integration config for {hive_id} failed: {str(e)[:160]}")
        # one sync batch recorded by the integration (what a CMMS import writes): the audit trail a member reads and
        # may not rewrite
        put("cmms_audit_log", [{"hive_id": hive_id, "batch_id": f"seed-batch-{n + 1}", "operation": "import",
                                "entity_type": "work_orders", "system_type": "generic", "rows_attempted": 12,
                                "rows_written": 12, "rows_failed": 0, "quality_score": 1.0, "triggered_by": name}])
        raw = secrets.token_hex(16)
        put("api_keys", [{"hive_id": hive_id, "key_prefix": "wh_seed_", "label": "Seed key",
                          "key_hash": hashlib.sha256(raw.encode()).hexdigest(), "enabled": False}])
        # a project linked to the machine it works on: the seed linked logs, parts and calcs but never an ASSET, so the
        # links-stay-in-their-hive probe had no asset link to test
        proj = client.table("projects").select("id").eq("hive_id", hive_id).limit(1).execute().data or []
        asset = (client.table("asset_nodes").select("id, name").eq("hive_id", hive_id).eq("status", "approved")
                 .is_("parent_id", "null").order("tag").limit(1).execute().data or [])
        if proj and asset:
            put("project_links", [{"project_id": proj[0]["id"], "hive_id": hive_id, "link_type": "asset",
                                   "link_id": asset[0]["id"], "label": asset[0]["name"]}])
        # a deal INSIDE this hive: the author asks about, and orders, a hive-mate's listing. Every other hive's author is no
        # party to it, so the write-authz probes have a foreign row that is genuinely foreign (an inquiry lives in its
        # listing's hive; the seed's six left some members with only their own deals abroad)
        listing = (client.table("marketplace_listings").select("id, auth_uid, price").eq("hive_id", hive_id)
                   .eq("status", "published").neq("auth_uid", uid).limit(1).execute().data or [])
        if listing and listing[0].get("auth_uid"):
            sp = client.table("worker_profiles").select("display_name").eq("auth_uid", listing[0]["auth_uid"]).limit(1).execute().data
            seller = sp[0]["display_name"] if sp else None
            put("marketplace_inquiries", [{"listing_id": listing[0]["id"], "hive_id": hive_id, "buyer_name": name,
                                           "buyer_auth_uid": uid, "buyer_contact": "seed@example.test",
                                           "message": "Seed: is this still available?", "status": "pending",
                                           "seller_name": seller}])
            if seller:
                put("marketplace_orders", [{"listing_id": listing[0]["id"], "hive_id": hive_id, "buyer_name": name,
                                            "buyer_auth_uid": uid, "seller_name": seller,
                                            "price": listing[0].get("price") or 1000, "currency": "PHP"}])
        # private feedback (is_public false): what the founder console must keep from every member
        put("platform_feedback", [{"auth_uid": uid, "worker_name": name, "hive_id": hive_id, "kind": "idea",
                                   "subject": "Seed: filter the logbook by shift", "body": "Sample feedback from the seed.",
                                   "status": "new", "is_public": False}])
        # an asset HIERARCHY: the seed's nodes are flat equipment, so the acyclic / delete-orphans probes had no parent and
        # child to test. One component under one machine per hive, as a person adds a bearing under its pump.
        parent = (client.table("asset_nodes").select("id, tag").eq("hive_id", hive_id).is_("parent_id", "null")
                  .eq("status", "approved").order("tag").limit(1).execute().data or [])
        if parent:
            put("asset_nodes", [{"hive_id": hive_id, "parent_id": parent[0]["id"], "level": "component",
                                 "tag": f"{parent[0]['tag']}-BRG-DE", "name": "Seed: drive-end bearing",
                                 "criticality": "medium", "status": "approved", "auth_uid": uid, "worker_name": name}])
        # one served AI call's trace, with the model chain it walked (what ai-gateway writes for a person's question)
        put("wh_traces", [{"trace_id": secrets.token_hex(8), "route": "ai-gateway", "hive_id": hive_id, "user_id": uid,
                           "status": 200, "latency_ms": 1200, "model_chain": ["groq:llama-3.3-70b-versatile"]}])
        # the gateway's audit trail for this member, so the observability probes have an own-hive row to read
        put("gateway_audit_log", [{"hive_id": hive_id, "auth_uid": uid, "worker_name": name, "route": "ai-gateway",
                                   "method": "POST", "status_code": 200, "latency_ms": 900}])
    # a buyer's private marketplace state (marketplace__the_rest_belongs_to_accounts reads Isidro Suarez's): a watched
    # listing and a saved search, owned by the account, so "a namesake reads none of it" has something to protect
    try:
        prof = client.table("worker_profiles").select("auth_uid").eq("display_name", "Isidro Suarez").limit(1).execute().data
        listing = client.table("marketplace_listings").select("id").eq("status", "published").limit(1).execute().data
        if prof and listing:
            put("marketplace_watchlist", [{"worker_name": "Isidro Suarez", "auth_uid": prof[0]["auth_uid"],
                                           "listing_id": listing[0]["id"]}])
            put("marketplace_saved_searches", [{"worker_name": "Isidro Suarez", "auth_uid": prof[0]["auth_uid"],
                                                "search_name": "Seed: bearings under 5k", "section": "parts",
                                                "query_text": "bearing", "price_max": 5000, "active": True}])
    except Exception as e:
        log(f"  WARN: buyer watchlist fixture failed: {str(e)[:160]}")
    try:
        r = seed_ai_reports(client, log=lambda m: None)
        counts["ai_reports"] = (r or {}).get("seeded", 0)
    except Exception as e:
        log(f"  WARN: ai_reports seed failed: {str(e)[:160]}")
    log("  probe fixtures: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return counts
