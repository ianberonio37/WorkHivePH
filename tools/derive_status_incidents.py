#!/usr/bin/env python3
"""derive_status_incidents.py — T71 status-page incident PRODUCER (the approved default).

The default for T71's status page: derive incidents from the health signals that ALREADY exist —
`platform_health.json` (the current gate board) and `automation_log` (the history of scheduled runs)
— rather than a new incident table and a new producer service. Start/end/severity come from
transitions in those signals. The output is `status_incidents.json`, a DB-INDEPENDENT static file so
status.html keeps working during the very outage it reports (status.html is already static-first).

Two incident sources, one shape:
  • automation_log history — per job_name, walking runs by triggered_at: a failed/warning run OPENS
    an incident, the next success CLOSES it (ended_at = that success). Severity = the worst status
    seen inside the window (failed > warning). These are resolved, historical incidents.
  • platform_health.json — any validator currently FAIL/WARN is an OPEN incident (no ended_at yet),
    severity from its status. The live picture the automation history cannot show.

Run it after a board (or on a schedule); it writes status_incidents.json. Read-only on the DB.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEALTH = ROOT / "platform_health.json"
OUT = ROOT / "status_incidents.json"

SEV = {"failed": "major", "warning": "minor", "fail": "major", "warn": "minor"}
_RANK = {"minor": 1, "major": 2}


def _psql(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive",
         "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-t", "-A"],
        input=sql, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(" ".join((r.stderr or "").split()))
    return (r.stdout or "").strip()


def from_automation_log() -> list[dict]:
    """Walk each job's runs in time order; a bad run opens an incident, a success closes it."""
    rows = _psql("select job_name, triggered_at, status from public.automation_log "
                 "order by job_name, triggered_at;")
    incidents, open_by_job = [], {}
    for line in filter(None, (l.strip() for l in rows.splitlines())):
        parts = line.split("|")
        if len(parts) < 3:
            continue
        job, ts, status = parts[0], parts[1], parts[2].lower()
        if status in ("failed", "warning"):
            inc = open_by_job.get(job)
            if inc is None:
                inc = {"id": f"auto-{job}-{ts}", "source": "automation", "title": job,
                       "severity": SEV[status], "started_at": ts, "ended_at": None,
                       "status": "resolved", "_last": ts}
                open_by_job[job] = inc
                incidents.append(inc)
            else:
                inc["_last"] = ts                          # remember the most recent bad run
                if _RANK[SEV[status]] > _RANK[inc["severity"]]:
                    inc["severity"] = SEV[status]          # escalate to the worst seen
        elif status == "success" and job in open_by_job:
            open_by_job.pop(job)["ended_at"] = ts          # a success closes the open incident
    # A job that FAILED but never recovered (no closing success) still has ended_at=None while marked
    # resolved — a 'resolved with no window' that reddens status-incidents. It is a HISTORICAL blip in
    # the log, not a live outage (the live picture comes from platform_health), so close it at its LAST
    # bad run: a point-in-time historical incident, ended_at = the most recent failure we recorded.
    for inc in open_by_job.values():
        inc["ended_at"] = inc.get("_last") or inc["started_at"]
    for inc in incidents:
        inc.pop("_last", None)
    return incidents


def from_health() -> list[dict]:
    """Any validator currently red/amber is an OPEN incident — the live picture."""
    if not HEALTH.exists():
        return []
    h = json.loads(HEALTH.read_text(encoding="utf-8"))
    out = []
    for v in h.get("validators", []):
        st = str(v.get("status", "")).lower()
        if v.get("ok") is False and not st:
            st = "fail"
        if st in ("fail", "warn"):
            out.append({"id": f"gate-{v.get('id')}", "source": "gate",
                        "title": v.get("id") or "(unnamed gate)",
                        "severity": SEV[st], "started_at": h.get("timestamp"),
                        "ended_at": None, "status": "open"})
    return out


def main() -> int:
    incidents = from_health() + from_automation_log()
    # newest first; open incidents (no ended_at) sort ahead of resolved
    incidents.sort(key=lambda i: (i["ended_at"] is not None, i["started_at"] or ""), reverse=False)
    incidents.reverse()
    doc = {
        "_doc": "T71 status incidents, DERIVED from platform_health.json + automation_log by "
                "tools/derive_status_incidents.py. DB-independent so status.html survives the outage.",
        "generated_from": {"health": HEALTH.name, "automation_log": "public.automation_log"},
        "open": sum(1 for i in incidents if i["status"] == "open"),
        "resolved": sum(1 for i in incidents if i["status"] == "resolved"),
        "incidents": incidents,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(f"status_incidents.json: {doc['open']} open · {doc['resolved']} resolved "
          f"({len(incidents)} total) from {len(from_health())} gate + automation history")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
