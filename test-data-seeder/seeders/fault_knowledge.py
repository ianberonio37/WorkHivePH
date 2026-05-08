"""Seed fault_knowledge from closed Breakdown logbook entries.

Mirrors the production-side bridge (logbook -> fault_knowledge for retrieval).
Without this, the Machine History panel on logbook.html stays empty in fresh
test environments and tests WARN that fault_knowledge has no rows.
"""
import random


def seed_fault_knowledge(client, log, ctx: dict) -> dict:
    """Pulls closed Breakdown/Corrective logbook entries seeded by seed_logbook
    and inserts a fault_knowledge row per entry. Embedding is left NULL —
    semantic search will degrade gracefully to text retrieval."""
    log("Seeding fault_knowledge from closed Breakdown logbook entries...")

    # Pull breakdown entries with usable text content
    closed_breakdowns = client.table("logbook").select(
        "id, hive_id, machine, category, problem, action, knowledge, root_cause, worker_name"
    ).eq("maintenance_type", "Breakdown / Corrective").eq("status", "Closed").limit(2000).execute().data or []

    if not closed_breakdowns:
        log("  no closed breakdowns to mirror — fault_knowledge skipped")
        return {"fault_knowledge_count": 0}

    # Cap at 6 per machine to avoid blowing up the table on large seeds
    rows_per_machine: dict = {}
    rows = []
    for e in closed_breakdowns:
        machine = e.get("machine") or ""
        key = (e.get("hive_id"), machine)
        if rows_per_machine.get(key, 0) >= 6:
            continue
        rows_per_machine[key] = rows_per_machine.get(key, 0) + 1
        rows.append({
            "hive_id":     e.get("hive_id"),
            "logbook_id":  e.get("id"),
            "machine":     machine,
            "category":    e.get("category") or "Other",
            "problem":     e.get("problem") or "",
            "root_cause":  e.get("root_cause") or "",
            "action":      e.get("action") or "",
            "knowledge":   e.get("knowledge") or "",
            "worker_name": e.get("worker_name") or "",
        })

    if not rows:
        return {"fault_knowledge_count": 0}

    from .utils import batch_insert
    inserted = batch_insert(client, "fault_knowledge", rows, chunk=500)
    log(f"  inserted {inserted} fault_knowledge rows")
    return {"fault_knowledge_count": inserted}
