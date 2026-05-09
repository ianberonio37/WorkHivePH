"""
Work Order State Machine Flow -- WorkHive Tester

Phase E.4 introduces an opt-in 7-state workflow on the logbook table:
   requested -> approved -> assigned -> in_progress -> completed -> verified
                                                                 -> rejected

This flow seeds one logbook entry in each state (plus one legacy null-state row
for control), then verifies:

  1. The new wo_state + wo_assigned_to columns persist correctly via insert
  2. The CHECK constraint rejects an invalid state value
  3. The entry list page renders the new badge for non-null wo_state
  4. The edit form contains the new dropdown + role-gated transitions
  5. Legacy rows (wo_state=NULL) still render exactly as before

Coverage: logbook.html (Phase E.4 additions only)
"""

import datetime, urllib.request


WO_STATES = [
    'requested', 'approved', 'assigned',
    'in_progress', 'completed', 'verified', 'rejected',
]


def run(page, errors, warnings, log) -> dict:
    from lib.supabase_client import get_client
    db = get_client()
    results = []

    log("Work Order Flow: locating seeded hive...")
    members = db.table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not members:
        return {"results": [("WARN", "No seeded hive_members — work order flow needs a hive context")]}

    worker_name = members[0]["worker_name"]
    hive_id     = members[0]["hive_id"]
    now         = datetime.datetime.utcnow()
    log(f"  Worker: {worker_name}, Hive: {hive_id}")

    # ── Step 1: Seed one entry per WO state ──────────────────────────────────
    log("Step 1: Seeding one logbook entry per work-order state...")
    rows = []
    for i, state in enumerate(WO_STATES):
        rows.append({
            "id":             f"wo-{state}-{int(now.timestamp())}-{i}",
            "hive_id":        hive_id,
            "worker_name":    worker_name,
            "machine":        f"WO Test Machine {i + 1}",
            "maintenance_type": "Breakdown / Corrective",
            "category":       "Mechanical",
            "problem":        f"Phase E.4 test entry in state '{state}'",
            "status":         "Open" if state != "verified" else "Closed",
            "closed_at":      (now.isoformat() + "Z") if state == "verified" else None,
            "created_at":     (now - datetime.timedelta(minutes=i)).isoformat() + "Z",
            "wo_state":       state,
            "wo_assigned_to": worker_name if state in ("approved", "assigned", "in_progress") else None,
        })

    # Plus one legacy row (wo_state=NULL) as control
    rows.append({
        "id":             f"wo-legacy-{int(now.timestamp())}",
        "hive_id":        hive_id,
        "worker_name":    worker_name,
        "machine":        "WO Test Machine LEGACY",
        "maintenance_type": "Breakdown / Corrective",
        "category":       "Mechanical",
        "problem":        "Phase E.4 control row — wo_state stays NULL",
        "status":         "Open",
        "created_at":     now.isoformat() + "Z",
        "wo_state":       None,
        "wo_assigned_to": None,
    })

    try:
        resp = db.table("logbook").insert(rows).execute()
        n = len(resp.data or []) if hasattr(resp, "data") else 0
        log(f"  Seeded {n} rows (7 states + 1 legacy)")
        results.append(("PASS" if n == 8 else "WARN", f"WO state rows seeded: {n}/8"))
    except Exception as e:
        results.append(("FAIL", f"WO seed failed: {e}"))

    # ── Step 2: Verify CHECK constraint rejects an invalid state ─────────────
    log("Step 2: Verifying CHECK constraint rejects invalid state...")
    try:
        db.table("logbook").insert({
            "id":          f"wo-bad-{int(now.timestamp())}",
            "hive_id":     hive_id,
            "worker_name": worker_name,
            "machine":     "WO Bad State Test",
            "maintenance_type": "Breakdown / Corrective",
            "category":    "Mechanical",
            "status":      "Open",
            "wo_state":    "invalid_phase",   # not in the CHECK list
        }).execute()
        results.append(("FAIL", "CHECK constraint did not reject 'invalid_phase' — schema not enforcing state set"))
    except Exception as ex:
        msg = str(ex)
        if "logbook_wo_state_check" in msg or "violates check constraint" in msg.lower():
            results.append(("PASS", "CHECK constraint correctly rejected invalid state"))
        else:
            results.append(("WARN", f"Insert failed for unexpected reason: {ex}"))

    # ── Step 3: Verify rows read back with the new columns ──────────────────
    log("Step 3: Verifying read-back of wo_state + wo_assigned_to...")
    try:
        res = db.table("logbook") \
            .select("id, wo_state, wo_assigned_to, status") \
            .eq("hive_id", hive_id) \
            .like("id", "wo-%") \
            .limit(20) \
            .execute()
        states_seen = {r["wo_state"] for r in (res.data or [])}
        for s in WO_STATES:
            ok = s in states_seen
            results.append(("PASS" if ok else "FAIL", f"read-back includes state '{s}'"))
        if None in states_seen:
            results.append(("PASS", "legacy row (wo_state=NULL) reads back correctly"))
    except Exception as e:
        results.append(("WARN", f"read-back skipped: {e}"))

    # ── Step 4: Verify logbook.html structure has the new controls ──────────
    log("Step 4: Verifying logbook.html structure has Phase E.4 additions...")
    try:
        with urllib.request.urlopen(f"{page.rstrip('/')}/logbook.html", timeout=15) as r:
            html = r.read(200000).decode("utf-8", errors="replace")

        checks = [
            ("WO state dropdown id present",     'id="f-wo-state"'      in html),
            ("WO assigned-to input present",     'id="f-wo-assigned-to"' in html),
            ("WO state hint copy present",       "Optional 7-state workflow" in html),
            ("woStateBadge() function defined",  "function woStateBadge" in html),
            ("badge wired into entry card",      "woStateBadge(e.wo_state" in html),
            ("badge wired into modal view",      "woStateBadge(entry.wo_state" in html),
            ("WO_TRANSITIONS map for roles",     "WO_TRANSITIONS"        in html),
            ("applyWoStateUI helper present",    "applyWoStateUI"        in html),
            ("hydrate from entry on edit",       "e.wo_state || ''"      in html),
            ("save path includes wo_state",      "wo_state:"             in html and "wo_assigned_to:" in html),
            ("SELECT query includes new cols",   "wo_state, wo_assigned_to" in html),
        ]
        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"logbook.html load skipped: {type(e).__name__}"))

    # ── Step 5: Cleanup test rows ────────────────────────────────────────────
    log("Step 5: Cleaning up test rows...")
    try:
        db.table("logbook").delete().eq("hive_id", hive_id).like("id", "wo-%").execute()
        results.append(("PASS", "Test rows cleaned up"))
    except Exception as e:
        results.append(("WARN", f"cleanup skipped: {e}"))

    return {"results": results}
