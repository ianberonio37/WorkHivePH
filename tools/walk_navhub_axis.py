#!/usr/bin/env python3
"""walk_navhub_axis.py - walk an axis's W4 nav-hub hosts SERIALLY and bank each passer, to completion.

★WHY THIS TOOL (2026-09-14). The 30-context ratchet (tools/prove_w4_navhub.mjs with no --host) is NOT viable on
the 8 GB host - run all-at-once it accumulates memory across contexts and crashes Docker + the session
([[feedback_over_driving_8gb_host_crashed_docker_and_session]]). But ONE host walked ALONE, in its own node
process that releases memory on exit, is the SERIAL discipline that memory prescribes, and it runs fine at ~1 GB
free. This tool is that discipline, mechanised (the "batch the walks, don't hand-walk them" runner,
[[feedback_batch_the_critic_walks_dont_hand_walk_them]]): for each un-banked nav-hub host of one axis it

  1. waits for free RAM >= --min-ram GB (up to --ram-wait s) so a heavy page does not crash its context,
  2. walks it in a FRESH `node tools/prove_w4_navhub.mjs --host <h> --axis "<axis>"` process (memory released on exit),
  3. banks the row to locking the instant its receipt satisfies the W4 evidence gate (advance_trajectory --batch,
     gate w4-nav-hub) - the receipt now carries per-page steps + fit (the 2026-09-14 walker/driver fix), so a
     passing walk closes its F+CA cells,
  4. records a crasher (an Oscar-Ramos-style context crash, or a timeout) to a retry list rather than stopping.

Never runs two browser contexts at once (the whole point), never queries the DB while a walk holds the browser
(the driver casts its persona up front). Idempotent: an already-locking row is skipped; re-running resumes.
PREFLIGHT (2026-09-14): before the loop and before every host it POSTs the login edge function with a bogus account;
a 5xx (a stopped runtime, or a wedged Docker host mount that answers 503 while the container reads Up) STOPS the axis
with the remedy printed (tools/recover_docker_desktop.ps1) instead of grading twenty hosts against a dead sign-in.
Each banked row names the gate for ITS axis (w4-nav-hub / w4-nav-hub-320-en / w4-nav-hub-390-fil).

  python tools/walk_navhub_axis.py --axis "phone-390 en"                 # walk + bank every un-banked host
  python tools/walk_navhub_axis.py --axis "narrow-320 en" --min-ram 0.8  # a stricter RAM floor
  python tools/walk_navhub_axis.py --axis "phone-390 en" --only marketplace-seller-profile.html,pm-scheduler.html
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def _free_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().available / 1e9
    except Exception:
        return 999.0  # no psutil -> do not gate on RAM


def _rows(axis: str) -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "nav-hub"
            and f"{(t.get('axis') or {}).get('device')} {(t.get('axis') or {}).get('language')}" == axis]


def _passes(rid: str, row: dict) -> bool:
    """True when the row's newest receipt satisfies the W4 evidence gate (reload the manifest each call)."""
    import importlib
    sys.path.insert(0, str(ROOT / "tools"))
    import live_walk_manifest as m
    importlib.reload(m)
    rec = m._w4_receipts()
    res = rec.get(rid)
    return bool(res and res.get("ok") and m._w4_missing(row, rec) == "")


GATE_BY_AXIS = {"phone-390 en": "w4-nav-hub", "narrow-320 en": "w4-nav-hub-320-en", "phone-390 fil": "w4-nav-hub-390-fil"}


def _anon_key() -> str:
    """The local anon key from `supabase status` (once per machine, cached in .tmp) - a POST to an edge function needs it."""
    cache = ROOT / ".tmp" / "local_anon_key.txt"
    try:
        if cache.exists() and cache.stat().st_size > 20:
            return cache.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    try:
        out = subprocess.run("supabase status -o env", capture_output=True, encoding="utf-8", errors="replace",
                             timeout=90, cwd=str(ROOT), shell=True).stdout or ""
    except Exception:
        out = ""
    for line in out.splitlines():
        if line.startswith("ANON_KEY="):
            key = line.split("=", 1)[1].strip().strip('"')
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(key, encoding="utf-8")
            except Exception:
                pass
            return key
    return ""


def _edge_ok() -> tuple[bool, str]:
    """★A LONG MEASUREMENT VERIFIES ITS DEPENDENCIES AT THE START, NOT TRUSTS THAT THEY HELD (2026-09-14): three
    narrow-320 re-walks "failed sign-in" while the login edge function answered 503 behind a WEDGED Docker host
    mount - the container read Up, the gateway answered OPTIONS 200, and only a POST told the truth. So: POST the
    login function with a bogus account. A healthy function REFUSES it (< 500); a wedged or stopped runtime answers
    5xx. A whole axis walked against a dead sign-in would bank nothing and show every host as "did not pass the
    gate". The remedy is printed, never guessed: tools/recover_docker_desktop.ps1."""
    import json as _json
    import urllib.error
    import urllib.request
    key = _anon_key()
    if not key:
        return True, "no anon key from `supabase status` - login preflight skipped"
    req = urllib.request.Request("http://127.0.0.1:54321/functions/v1/login", method="POST",
                                 data=_json.dumps({"email": "__preflight__@auth.workhiveph.com", "password": "x"}).encode(),
                                 headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # connection refused / timeout: the gateway itself is down
        return False, f"login function unreachable: {str(e)[:80]}"
    return code < 500, f"login function answered {code} to a bogus account"


def _bank(row: dict, axis: str) -> bool:
    """REFUSES. This tool walks with the Playwright LIBRARY, which is not this roadmap's instrument.

    Ian retracted it on 2026-09-15 - "I thought we are using relevant live MCPs for this roadmap?" -
    and every row banked this way was re-opened with the reason recorded in its own basis. The ROWS
    were retracted and THIS FUNCTION was not, so running the tool on 2026-09-16 re-banked 12 of them
    on the retracted prover, three of which had held correct playwright-mcp evidence that morning.
    A decision applied only to the output is not enforced, it is tidied.

    The walk above is still worth running - it exercises the hub fast and its receipt is real
    evidence for TRIAGE. It simply does not close a row. The path that does:

        browser_run_code_unsafe (params in .tmp/w4_args.json)  ->  the seeder writes
        .tmp/w4_steps/<id>.json  ->  tools/bank_mcp_navhub_walk.py --id <id> --axis "<axis>"
        --cast "<cast>"          ->  record_mcp_walk.py, instrument playwright-mcp

    which refuses a steps file carrying another id, a walk that reported problems, fewer than 11
    control groups, or a step with no overlap record.
    """
    host = row["w4"]["host"]
    print(f"  {YEL}not banked{RST} {host} ({row['id']}) - this tool walks with the Playwright LIBRARY, "
          f"retracted as an instrument 2026-09-15. The walk stands as TRIAGE evidence; bank it by "
          f"walking through the Playwright MCP, then tools/bank_mcp_navhub_walk.py --id {row['id']} "
          f'--axis "{axis}".')
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--axis", default="phone-390 en")
    ap.add_argument("--min-ram", type=float, default=0.72, help="GB free required before launching a walk")
    ap.add_argument("--force", action="store_true",
                    help="re-walk the --only hosts even if their rows are already banked (use when the PAGE changed after the walk)")
    ap.add_argument("--ram-wait", type=int, default=120, help="max seconds to wait for RAM before skipping a host")
    # 450, not 200 (measured 2026-09-14): a narrow-320 host takes ~365s on this host at ~0.5-0.9 GB free, and the
    # 200s default killed every host BEFORE the driver wrote its receipt - the whole axis banked nothing and the
    # buffered stdout showed no reason. A kill leaves no receipt; a cap must sit above the slowest honest walk.
    ap.add_argument("--walk-timeout", type=int, default=450)
    ap.add_argument("--only", default="", help="comma list of hosts to restrict to")
    ap.add_argument("--include-heavy", action="store_true",
                    help="also walk the hosts that OOM-crash this host's headless renderer (see HEAVY)")
    a = ap.parse_args()
    only = {h.strip() for h in a.only.split(",") if h.strip()}
    # ★THE HEAVY HOSTS CRASH THE RENDERER AT PAGE LOAD ON THIS 8 GB MACHINE (measured 2026-09-14, every persona,
    # every deviceScaleFactor): "Target page/context/browser has been closed", 0 steps. Walking them costs a RAM wait
    # plus a crash, ~5 min each, and banks nothing - so they are skipped BY DEFAULT and COUNTED (a silent cap reads as
    # "covered everything"). --include-heavy walks them anyway, for a host with headroom.
    HEAVY = {"analytics.html", "engineering-design.html", "index.html", "pm-scheduler.html", "shift-brain.html",
             "marketplace-seller-profile.html", "hive.html"}
    # --force re-opens an already-banked row for a re-walk, which is what a page edited AFTER its
    # walk needs: the straddle guard refuses the old receipt, and without this the walker would
    # answer "nothing to walk" to a row whose evidence describes a build that no longer exists.
    # Restricted to --only on purpose: forcing a whole axis is a ~3h job nobody means to start by
    # accident, and the real case is always specific.
    if a.force and not only:
        print("REFUSED --force without --only: name the hosts whose page changed "
              "(a forced full-axis re-walk is ~3h and is never what --force means).")
        return 1
    candidates = [t for t in _rows(a.axis)
                  if (a.force or t.get("status") not in ("locking", "locked"))
                  and (not only or t["w4"]["host"] in only)]
    if a.force:
        print("  --force: re-walking %d already-banked row(s) because their page changed after "
              "the walk" % len(candidates))
    heavy_skipped = [] if a.include_heavy else [t["w4"]["host"] for t in candidates if t["w4"]["host"] in HEAVY]
    rows = [t for t in candidates if a.include_heavy or t["w4"]["host"] not in HEAVY]
    if heavy_skipped:
        print(f"  {YEL}skipping {len(heavy_skipped)} heavy host(s){RST} that crash this host's renderer at load "
              f"(--include-heavy to walk them): {', '.join(sorted(heavy_skipped))}")
    if not rows:
        print(f"{GREEN}PASS{RST} walk-navhub-axis - every {a.axis} nav-hub row is already banked (nothing to walk)"
              + (f" - {len(heavy_skipped)} heavy host(s) skipped, still owed" if heavy_skipped else ""))
        return 0
    banked, crashed, skipped = [], [], []
    ok, why = _edge_ok()
    if not ok:
        print(f"{RED}STOP{RST} walk-navhub-axis - the sign-in edge function is down ({why}); every walk would fail at the "
              f"wall and bank nothing. Remedy: powershell -NoProfile -ExecutionPolicy Bypass -File tools/recover_docker_desktop.ps1, then re-run.")
        return 2
    print(f"  preflight: {why}")
    print(f"walking {len(rows)} un-banked {a.axis} nav-hub host(s), serial, RAM floor {a.min_ram}GB")
    for t in rows:
        host = t["w4"]["host"]
        ok, why = _edge_ok()
        if not ok:   # a dependency that died mid-axis stops the axis, it does not grade twenty hosts against it
            print(f"  {RED}STOP{RST} before {host}: the sign-in edge function went down mid-axis ({why}). "
                  f"Remedy: tools/recover_docker_desktop.ps1; re-run resumes at the un-banked hosts.")
            skipped.extend(r["w4"]["host"] for r in rows if r["w4"]["host"] not in banked and r["w4"]["host"] not in [h for h, _ in crashed])
            break
        waited = 0
        while _free_gb() < a.min_ram and waited < a.ram_wait:
            time.sleep(15)
            waited += 15
        if _free_gb() < a.min_ram:
            print(f"  {YEL}skip{RST} {host} - RAM {_free_gb():.2f}GB < {a.min_ram} after {waited}s")
            skipped.append(host)
            continue
        try:
            r = subprocess.run(["node", str(ROOT / "tools" / "prove_w4_navhub.mjs"), "--host", host, "--axis", a.axis],
                               capture_output=True, encoding="utf-8", errors="replace", timeout=a.walk_timeout,
                               cwd=str(ROOT))
            out = (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            out = "TIMEOUT"
        if _passes(t["id"], t) and _bank(t, a.axis):
            print(f"  {GREEN}bank{RST} {host}")
            banked.append(host)
        else:
            reason = "context crashed" if "has been closed" in out else ("timeout" if "TIMEOUT" in out else "did not pass the gate")
            print(f"  {RED}FAIL{RST} {host} - {reason}")
            crashed.append((host, reason))
        time.sleep(4)  # let memory settle between contexts
    print(f"\n{GREEN}banked {len(banked)}{RST} · {RED}failed {len(crashed)}{RST} · skipped {len(skipped)}")
    if crashed:
        print("  retry (crash/timeout/gate): " + ", ".join(f"{h} ({why})" for h, why in crashed))
    if skipped:
        print("  retry (RAM): " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    # line_buffering: this runs for an hour as a BACKGROUND job whose stdout is a file, and block-buffered
    # prints would show nothing until exit - a reader could not tell "walking host 3" from "hung" (2026-09-14).
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
