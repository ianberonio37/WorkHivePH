#!/usr/bin/env python3
"""host_headroom.py — free RAM on the 8GB host before a long browser run, reversibly.

Phase 0 of the P-program (2026-09-05). The measured problem, not a guess: Docker crashed or hung
THREE times in one session running boards, and at the moment this tool was written the host had
**0.43 GB free of 7.8 GB** with a Chrome fleet still to launch. The single largest consumer was
`workhive_glitchtip_worker` at 423 MB — an error-tracking worker that no rubric sweep or journey
walk reads. Roughly 1.2 GB sits in containers a browser prover never touches.

Two rules this encodes, both learned the hard way:
  1. **Stopping a container is a MOVE, not a ceiling** — "name resolution failed" and
     WH_DB_TIMEOUT have both turned out to be a stopped/starved container, so the reverse is also
     true: memory pressure is fixed by stopping what is not needed, then STARTING IT BACK.
  2. **Reversible, and it records what it stopped** (`.host_headroom_state.json`), so --restore
     puts back exactly what was running and nothing else. A tool that frees memory but loses the
     "before" state is a tool that quietly degrades the stack.

NEVER stopped (the prover's own dependencies): db, auth, rest, kong, realtime, storage, inbucket,
and the python API. Studio/pg_meta are UIs; glitchtip/grafana are observability; embed-server is
only needed by RAG/embedding work — all are stopped only when explicitly asked for.

  --status            show what is running, its memory, and what could be freed
  --free              stop the non-essential set (records prior state)
  --free --with-embed also stop embed-server (do NOT use for RAG/embedding runs)
  --restore           start back exactly what --free stopped
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".host_headroom_state.json"

# The prover's dependencies — never stopped by this tool, at any flag.
ESSENTIAL = {
    "supabase_db_workhive", "supabase_auth_workhive", "supabase_rest_workhive",
    "supabase_kong_workhive", "supabase_realtime_workhive", "supabase_storage_workhive",
    "supabase_inbucket_workhive", "workhive_python_api",
}
# Safe to stop for a browser prover run: observability + admin UIs.
NON_ESSENTIAL = [
    "workhive_glitchtip_worker", "supabase_analytics_workhive", "embed-server", "workhive_glitchtip_web", "workhive_glitchtip_redis",
    "workhive_grafana", "supabase_studio_workhive", "supabase_pg_meta_workhive",
]
# Only with --with-embed: RAG/embedding runs genuinely need this one.
OPTIONAL = ["embed-server"]


def _docker(*args: str) -> str:
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True,
                              timeout=120).stdout.strip()
    except Exception as e:
        print(f"docker call failed: {e}")
        return None                      # None means "could not read", which is not the same as "nothing"


def _running() -> list[str] | None:
    """The running containers, or None when the daemon could not answer.

    ★A FAILED READ IS NOT AN EMPTY ONE, AND THIS TOOL RUNS EXACTLY WHEN THE DAEMON IS STRUGGLING. Asked to
    free memory at 177 MB free, `docker ps` timed out inside this helper, the empty string became an empty
    list, and the tool announced "nothing to free - the non-essential set is already stopped." It had not
    looked. A tool whose whole purpose is to act under pressure must never turn its own timeout into a
    statement about the host, which is the same error every false green in this program is made of.
    """
    out = _docker("ps", "--format", "{{.Names}}")
    if out is None:
        return None
    return [n for n in out.splitlines() if n.strip()]


def _mem() -> dict[str, str]:
    out = {}
    # `docker stats` is the first call to hang when the daemon is under pressure, which is precisely when
    # this tool is wanted - a missing figure just prints as "?", it must never take the tool down with it
    raw = _docker("stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}")
    for line in (raw or "").splitlines():
        if "\t" in line:
            n, m = line.split("\t", 1)
            out[n] = m
    return out


def status() -> int:
    run, mem = _running(), _mem()
    if run is None:
        print("could NOT read what is running - the daemon did not answer, so nothing is reported about it.")
        return 1
    freeable = [c for c in NON_ESSENTIAL if c in run]
    print(f"{len(run)} containers running")
    for c in sorted(run):
        tag = ("ESSENTIAL " if c in ESSENTIAL else
               "freeable  " if c in NON_ESSENTIAL else
               "optional  " if c in OPTIONAL else "other     ")
        print(f"  {tag} {c:34} {mem.get(c, '?')}")
    print(f"\nfreeable now: {len(freeable)} container(s) — {', '.join(freeable) or 'none'}")
    if STATE.exists():
        print(f"state file present: --restore would start "
              f"{json.loads(STATE.read_text(encoding='utf-8')).get('stopped', [])}")
    return 0


def free(with_embed: bool) -> int:
    run = _running()
    if run is None:
        print("could NOT read what is running - the daemon did not answer. Nothing was stopped, and nothing "
              "is claimed about the host; retry when docker responds (`docker ps`).")
        return 1
    targets = [c for c in NON_ESSENTIAL + (OPTIONAL if with_embed else []) if c in run]
    targets = [c for c in targets if c not in ESSENTIAL]     # belt and braces
    if not targets:
        print("nothing to free — the non-essential set is already stopped.")
        return 0
    prior = json.loads(STATE.read_text(encoding="utf-8")).get("stopped", []) if STATE.exists() else []
    for c in targets:
        print(f"stopping {c} …")
        _docker("stop", c)
    # keep any earlier record so two --free calls do not lose the first one's containers
    STATE.write_text(json.dumps({"stopped": sorted(set(prior) | set(targets))},
                                indent=1) + "\n", encoding="utf-8")
    print(f"\nstopped {len(targets)}: {', '.join(targets)}")
    print("restore with: python tools/host_headroom.py --restore")
    return 0


def restore() -> int:
    if not STATE.exists():
        print("no state file — nothing was stopped by this tool.")
        return 0
    stopped = json.loads(STATE.read_text(encoding="utf-8")).get("stopped", [])
    for c in stopped:
        print(f"starting {c} …")
        _docker("start", c)
    STATE.unlink()
    print(f"\nrestored {len(stopped)}: {', '.join(stopped)}")
    return 0


def main() -> int:
    if "--free" in sys.argv:
        return free("--with-embed" in sys.argv)
    if "--restore" in sys.argv:
        return restore()
    return status()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
