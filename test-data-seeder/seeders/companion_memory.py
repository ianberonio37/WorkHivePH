"""Seed a minimal companion-memory footprint so a fresh reset_all leaves the
AI memory layer HEALTHY (companion_memory_health_gate needs >=1 episodic + >=1
agent_memory row). Without this, every reseed strands the gate at 0/0 until a
live companion turn happens — the dead-on-reset class (marketplace-seller lesson):
a cross-surface feature is dead-on-reset unless the seeder populates BOTH sides."""
import uuid
from .utils import to_iso
from datetime import datetime, timezone


def seed_companion_memory(client, log, ctx: dict) -> dict:
    hives = ctx.get("hives") or []
    workers = ctx.get("workers") or []
    if not hives:
        try:
            hives = (client.table("hives").select("id").limit(10).execute().data) or []
        except Exception as e:
            log(f"  warn: companion_memory could not load hives ({e})")
            return {}
    now = datetime.now(timezone.utc)
    epi_rows, mem_rows = [], []
    for hive in hives:
        hid = hive["id"]
        hw = [w for w in workers if w.get("hive_id") == hid]
        wname = hw[0]["worker_name"] if hw else "Pablo Aguilar"
        epi_rows.append({
            "hive_id": hid, "worker_name": wname, "memory_type": "factual",
            "content": "Seeded companion episodic memory: the plant runs a compressor overhaul each shutdown.",
            "importance": 0.5, "created_at": to_iso(now),
        })
        mem_rows.append({
            "hive_id": hid, "worker_name": wname, "agent_id": "assistant", "kind": "summary",
            "summary": "Seeded companion working memory for the hive's maintenance context.",
            "created_at": to_iso(now),
        })
    if epi_rows:
        client.table("agent_episodic_memory").insert(epi_rows).execute()
        log(f"  inserted {len(epi_rows)} agent_episodic_memory")
    if mem_rows:
        client.table("agent_memory").insert(mem_rows).execute()
        log(f"  inserted {len(mem_rows)} agent_memory")
    return {"agent_episodic_memory": epi_rows, "agent_memory": mem_rows}
