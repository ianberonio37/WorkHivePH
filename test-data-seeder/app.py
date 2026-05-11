import io
import json
import random
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, jsonify, request, send_from_directory, Response, abort, redirect, stream_with_context

from lib.supabase_client import get_client
from lib.config import SUPABASE_URL
from data.filipino_names import FIRST_NAMES_MALE, FIRST_NAMES_FEMALE, SURNAMES, random_full_name
from data.ph_equipment import EQUIPMENT_CATALOG
from data.ph_faults import FAULTS_BY_CATEGORY
from data.ph_locations import CITIES, HIVE_TEMPLATES

from seeders.orchestrator import seed_everything
from seeders.hives_workers import seed_hives_and_workers
from seeders.assets import seed_assets
from seeders.pm import seed_pm
from seeders.logbook import seed_logbook
from seeders.inventory import seed_inventory
from seeders.skill_matrix import seed_skill_matrix
from seeders.marketplace import seed_marketplace
from seeders.community import seed_community
from seeders.projects import seed_projects
from seeders.reset import reset_all
from seeders.achievements import seed_achievements

import subprocess
import sys

app = Flask(__name__)

# Phase 2 -- register mock CMMS API Blueprint
from mock_cmms.blueprint import mock_cmms_bp
app.register_blueprint(mock_cmms_bp)

# WorkHive proxy — serves the platform HTML files with Supabase URL/key
# rewritten to point at local Supabase. Lets the seeded test data render.
WORKHIVE_ROOT = Path(__file__).resolve().parent.parent
CLOUD_URL = "https://hzyvnjtisfgbksicrouu.supabase.co"
LOCAL_URL = "http://127.0.0.1:54321"
CLOUD_KEY = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"
LOCAL_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"

# Pages safe to expose (skips backups, test variants, node_modules)
PUBLIC_PAGES = [
    ("index.html", "Landing page"),
    ("hive.html", "Hive dashboard"),
    ("logbook.html", "Logbook"),
    ("inventory.html", "Inventory"),
    ("pm-scheduler.html", "PM Scheduler"),
    ("analytics.html", "Analytics dashboard"),
    ("analytics-report.html", "Analytics Report (print/PDF)"),
    ("skillmatrix.html", "Skill Matrix"),
    ("community.html", "Community"),
    ("public-feed.html", "Public feed"),
    ("marketplace.html", "Marketplace"),
    ("marketplace-seller.html", "Seller dashboard"),
    ("dayplanner.html", "Day planner"),
    ("engineering-design.html", "Engineering design"),
    ("assistant.html", "AI assistant"),
    ("report-sender.html", "Report sender"),
    ("platform-health.html", "Platform health"),
    ("architecture.html", "Architecture"),
    ("symbol-gallery.html", "Symbol gallery"),
    ("project-manager.html", "Project Manager"),
    ("integrations.html", "CMMS Integration"),
    ("ph-intelligence.html", "PH Intelligence Report"),
    ("project-report.html", "Project Report"),
    ("predictive.html", "Predictive Maintenance"),
    ("achievements.html", "Achievements"),
    ("asset-hub.html", "Asset Hub"),
    ("shift-brain.html", "Shift Brain"),
    ("alert-hub.html", "Alert Hub"),
    ("audit-log.html", "Audit Log"),
    ("voice-journal.html", "Voice Journal"),
]
PUBLIC_PAGE_SET = {p[0] for p in PUBLIC_PAGES}


# In-memory job state (single-user dev tool — no need for redis)
JOB_STATE = {
    "running": False,
    "name": None,
    "log": [],
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
    # Bumped on every _run_job call. The SSE stream watches this so it can
    # detect a new job starting (log was reset behind it) and snap its cursor
    # back to 0. Without this, the second click of any button shows nothing
    # in the live log because the cursor is stuck past the new log's length.
    "id": 0,
}

# Event that fires whenever a new log line is appended. The SSE stream
# (`/api/log-stream`) blocks on this so lines surface within ~10ms instead
# of the 1s the old polling loop had.
LOG_EVENT = threading.Event()


def _log_to_state(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    JOB_STATE["log"].append(f"[{ts}] {msg}")
    LOG_EVENT.set()
    # Console may be cp1252 on stock Windows; a stray Unicode arrow or emoji
    # would crash the worker thread mid-job. Fall back to ASCII replacement.
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc, "replace"))


def _run_job(name: str, fn):
    JOB_STATE.update({
        "running": True,
        "name": name,
        "log": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "result": None,
        "error": None,
        "id": JOB_STATE["id"] + 1,
    })
    # Wake the SSE stream so it observes the new job_id + running=True and
    # resets its cursor. Without this, the stream stays asleep until the
    # first log line lands, so the badge "RUNNING" indicator lags.
    LOG_EVENT.set()

    def worker():
        try:
            client = get_client()
            result = fn(client, _log_to_state)
            JOB_STATE["result"] = result
        except Exception as e:
            JOB_STATE["error"] = f"{type(e).__name__}: {e}"
            _log_to_state(f"FAILED: {JOB_STATE['error']}")
        finally:
            JOB_STATE["running"] = False
            JOB_STATE["finished_at"] = datetime.now(timezone.utc).isoformat()
            LOG_EVENT.set()  # wake the SSE stream so it can emit `done`

    threading.Thread(target=worker, daemon=True).start()


def _ctx_required():
    """Some standalone seeders need 'hives', 'workers', 'assets' from DB."""
    client = get_client()
    hives = client.table("hives").select("*").execute().data
    members = client.table("hive_members").select("*").execute().data
    assets = client.table("assets").select("*").execute().data

    workers = []
    for m in members:
        workers.append({
            "worker_name": m["worker_name"],
            "display_name": m["worker_name"],
            "auth_uid": m.get("auth_uid"),
            "role": m["role"],
            "tier": "active",
            "logbook_target": 100,
            "hive_id": m["hive_id"],
        })
    assets_by_hive: dict = {}
    for a in assets:
        if a.get("hive_id"):
            assets_by_hive.setdefault(a["hive_id"], []).append(a)

    return {"hives": hives, "workers": workers, "assets": assets, "assets_by_hive": assets_by_hive}


def sample_workers(n=5):
    return [random_full_name() for _ in range(n)]


def sample_equipment(n=5):
    return random.sample(EQUIPMENT_CATALOG, k=min(n, len(EQUIPMENT_CATALOG)))


def sample_faults(n=5):
    flat = []
    for category, faults in FAULTS_BY_CATEGORY.items():
        for f in faults:
            flat.append({"category": category, **f})
    return random.sample(flat, k=min(n, len(flat)))


def sample_hives(n=5):
    out = []
    for _ in range(n):
        tpl = random.choice(HIVE_TEMPLATES)
        city = random.choice(CITIES)
        out.append({"name": tpl["name"].format(city=city), "industry": tpl["industry"]})
    return out


def get_db_counts():
    """Quick count of seeded tables."""
    counts = {}
    client = get_client()
    for t in ["hives", "hive_members", "assets", "logbook", "pm_assets",
              "pm_completions", "inventory_items", "inventory_transactions",
              "skill_profiles", "skill_badges", "marketplace_listings",
              "community_posts",
              "projects", "project_items", "project_links", "project_progress_logs",
              "asset_nodes", "shift_plans", "failure_signature_alerts",
              "asset_risk_scores", "parts_staging_recommendations",
              "parts_staged_reservations", "worker_achievements"]:
        try:
            res = client.table(t).select("id", count="exact").limit(1).execute()
            counts[t] = res.count or 0
        except Exception:
            counts[t] = "?"
    return counts


def get_test_logins():
    """Returns sample workers with their hive name + invite code, grouped so
    every hive has at least one supervisor + one worker shown.

    The platform prompts for a hive code on first login because localStorage
    has no wh_active_hive_id yet. Surfacing the code here saves the user from
    having to dig through the database for it.
    """
    try:
        client = get_client()
        # Pull all hives (id, name, invite_code)
        hives_res = client.table("hives").select("id, name, invite_code").execute()
        hives = {h["id"]: h for h in (hives_res.data or [])}
        if not hives:
            return []

        # Pull all hive_members (auth_uid → hive_id, role)
        members_res = client.table("hive_members").select(
            "auth_uid, hive_id, role"
        ).eq("status", "active").execute()
        member_by_uid = {m["auth_uid"]: m for m in (members_res.data or []) if m.get("auth_uid")}

        # Pull worker_profiles (username, display_name, auth_uid)
        profiles_res = client.table("worker_profiles").select(
            "username, display_name, auth_uid"
        ).execute()
        profiles = profiles_res.data or []

        # Build enriched rows
        rows = []
        for p in profiles:
            m = member_by_uid.get(p.get("auth_uid"))
            if not m:
                continue
            h = hives.get(m["hive_id"])
            if not h:
                continue
            rows.append({
                "username":     p.get("username", ""),
                "display_name": p.get("display_name", ""),
                "role":         m.get("role", "worker"),
                "hive_name":    h.get("name", ""),
                "invite_code":  h.get("invite_code", ""),
            })

        # Group by hive. Pick the FIRST supervisor and the FIRST worker per
        # hive so the user can test both roles in every hive.
        by_hive = {}
        for r in rows:
            by_hive.setdefault(r["hive_name"], []).append(r)

        out = []
        for hive_rows in by_hive.values():
            sup = next((r for r in hive_rows if r["role"] == "supervisor"), None)
            wkr = next((r for r in hive_rows if r["role"] != "supervisor"), None)
            if sup: out.append(sup)
            if wkr: out.append(wkr)
        return out
    except Exception:
        return []


@app.route("/")
def index():
    connected = False
    error = None
    counts = {}

    try:
        counts = get_db_counts()
        connected = True
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    return render_template(
        "index.html",
        connected=connected,
        supabase_url=SUPABASE_URL,
        error=error,
        counts=counts,
        test_logins=get_test_logins() if connected else [],
        stats={
            "first_names_male": len(FIRST_NAMES_MALE),
            "first_names_female": len(FIRST_NAMES_FEMALE),
            "surnames": len(SURNAMES),
            "equipment_archetypes": len(EQUIPMENT_CATALOG),
            "fault_categories": len(FAULTS_BY_CATEGORY),
            "fault_templates": sum(len(v) for v in FAULTS_BY_CATEGORY.values()),
            "cities": len(CITIES),
            "hive_templates": len(HIVE_TEMPLATES),
        },
        samples={
            "workers": sample_workers(8),
            "hives": sample_hives(5),
            "equipment": sample_equipment(6),
            "faults": sample_faults(5),
        },
    )


@app.route("/api/status")
def api_status():
    return jsonify({
        "running": JOB_STATE["running"],
        "name": JOB_STATE["name"],
        "log": JOB_STATE["log"][-200:],
        "result": JOB_STATE["result"],
        "error": JOB_STATE["error"],
        "counts": get_db_counts() if not JOB_STATE["running"] else None,
    })


@app.route("/api/log-stream")
def api_log_stream():
    """Server-Sent Events stream that pushes log lines as they're written.

    Replaces the 1s polling loop with sub-100ms push. The client opens an
    EventSource(); we block on LOG_EVENT until `_log_to_state` fires it,
    then flush any new lines past the cursor. On job completion we emit
    `event: done` with fresh counts so the UI can refresh the table.
    The stream stays open across runs so the next job streams immediately.
    """
    @stream_with_context
    def gen():
        cursor = len(JOB_STATE["log"])
        last_running = JOB_STATE["running"]
        last_id = JOB_STATE["id"]
        # Hint to the browser/proxy: don't buffer.
        yield ": connected\n\n"
        # Replay nothing initially — the client clears its panel on trigger.
        while True:
            log = JOB_STATE["log"]
            job_id = JOB_STATE["id"]
            running = JOB_STATE["running"]
            # New job started behind our back: log was replaced, so our
            # cursor is stale. Snap it back to 0 and treat the transition
            # as if we observed running=True (otherwise a fast-finishing
            # job between two waits would collapse start+end into one wake
            # and we'd never emit the `done` event the UI needs to re-enable
            # buttons).
            if job_id != last_id:
                cursor = 0
                last_id = job_id
                last_running = True
            if cursor < len(log):
                batch = log[cursor:]
                cursor = len(log)
                payload = json.dumps({
                    "lines":   batch,
                    "running": running,
                    "name":    JOB_STATE["name"],
                })
                yield f"data: {payload}\n\n"
            if last_running and not running:
                final = {
                    "name":    JOB_STATE["name"],
                    "error":   JOB_STATE["error"],
                    "counts":  get_db_counts(),
                }
                yield f"event: done\ndata: {json.dumps(final)}\n\n"
            last_running = running
            # Block until a new line arrives. Heartbeat every 15s keeps
            # the connection alive through proxies/load-balancers.
            if not LOG_EVENT.wait(timeout=15.0):
                yield ": heartbeat\n\n"
            LOG_EVENT.clear()

    return Response(gen(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@app.route("/api/seed/all", methods=["POST"])
def api_seed_all():
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("seed_all", seed_everything)
    return jsonify({"started": True})


@app.route("/api/seed/<module>", methods=["POST"])
def api_seed_module(module):
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409

    standalone_map = {
        "hives_workers":  lambda c, log: seed_hives_and_workers(c, log),
        "achievements":   lambda c, log: seed_achievements(c, log),
    }

    from seeders.dayplanner import seed_dayplanner
    from seeders.engineering import seed_engineering
    from seeders.fault_knowledge import seed_fault_knowledge
    from seeders.edge_post_seed import run_post_seed_edges
    needs_ctx_map = {
        "assets": seed_assets,
        "pm": seed_pm,
        "logbook": seed_logbook,
        "inventory": seed_inventory,
        "skill_matrix": seed_skill_matrix,
        "marketplace": seed_marketplace,
        "community": seed_community,
        "projects": seed_projects,
        "dayplanner": seed_dayplanner,
        "engineering": seed_engineering,
        "fault_knowledge": seed_fault_knowledge,
        "post_seed_edges": run_post_seed_edges,
    }

    if module in standalone_map:
        _run_job(f"seed_{module}", standalone_map[module])
        return jsonify({"started": True})

    if module in needs_ctx_map:
        fn = needs_ctx_map[module]

        def wrapped(client, log):
            ctx = _ctx_required()
            return fn(client, log, ctx)

        _run_job(f"seed_{module}", wrapped)
        return jsonify({"started": True})

    return jsonify({"error": f"unknown module: {module}"}), 400


@app.route("/api/reset", methods=["POST"])
def api_reset():
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("reset", reset_all)
    return jsonify({"started": True})


def _run_subprocess(script_name: str, log):
    """Helper: run a Python script in the venv, stream stripped output."""
    runner = Path(__file__).parent / script_name
    py = Path(__file__).parent / "venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = "python"
    if not runner.exists():
        log(f"ERROR: script not found at {runner}")
        return {"summary": "", "exit_code": 1}
    log(f"Launching {script_name} via {py}")
    # -u: unbuffered stdout/stderr, so the live log streams in real time
    # instead of pooling lines until the OS pipe buffer fills.
    try:
        proc = subprocess.Popen(
            [str(py), "-u", str(runner)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).parent), bufsize=1,
            text=True, encoding="utf-8", errors="replace",
        )
    except Exception as e:
        log(f"ERROR: failed to launch subprocess: {type(e).__name__}: {e}")
        return {"summary": "", "exit_code": 1}
    log(f"Subprocess PID {proc.pid} started, streaming output...")
    import re
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    last_summary = ""
    line_count = 0
    for line in proc.stdout:
        clean = ansi.sub("", line.rstrip())
        if clean:
            log(clean)
            line_count += 1
            if "Summary" in clean:
                last_summary = clean
    proc.wait()
    log(f"Subprocess exited code={proc.returncode} after {line_count} output lines")
    return {"summary": last_summary, "exit_code": proc.returncode}


@app.route("/api/run-tests", methods=["POST"])
def api_run_tests():
    """Runs the automated data-level test suite."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("run_tests", lambda c, log: _run_subprocess("run_tests.py", log))
    return jsonify({"started": True})


@app.route("/api/service-status")
def api_service_status():
    """Check which backing services are reachable."""
    import socket

    def port_open(host, port, timeout=1.5):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            try:
                s.connect((host, port))
                return True
            except Exception:
                return False

    supabase_db     = port_open("127.0.0.1", 54321)
    supabase_studio = port_open("127.0.0.1", 54323)
    edge_functions  = port_open("127.0.0.1", 54321)   # same host, functions on path

    # Quick probe of the Edge Functions endpoint
    edge_ok = False
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:54321/functions/v1",
            headers={"Authorization": "Bearer " + LOCAL_KEY},
        )
        urllib.request.urlopen(req, timeout=2)
        edge_ok = True
    except Exception:
        edge_ok = supabase_db   # if Supabase is up, functions may just need a moment

    return jsonify({
        "supabase":       supabase_db,
        "studio":         supabase_studio,
        "edge_functions": edge_ok,
        "seeder":         True,          # we're responding, so seeder is up
    })


@app.route("/api/quick-demo", methods=["POST"])
def api_quick_demo():
    """One-click: Generate dataset → Seed Client Hive → Run CRUD validators.

    Body: { industry, size, cmms_type, seed (optional) }
    Streams progress through JOB_STATE so the UI can poll /api/status.
    """
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409

    data      = request.get_json(silent=True) or {}
    industry  = (data.get("industry")  or "food_processing").strip()
    size      = (data.get("size")      or "medium").strip()
    cmms_type = (data.get("cmms_type") or "sap_pm").strip()
    seed_raw  = data.get("seed")
    seed      = int(seed_raw) if seed_raw is not None else None

    def run_quick_demo(client, log):
        import subprocess as _sp

        # Step 1: Seed client hive
        log("Quick Demo — Step 1: Seeding client hive...")
        from seeders.client_hive import seed_client_hive
        result = seed_client_hive(client, log,
                                  industry=industry, size=size,
                                  cmms_type=cmms_type, seed=seed)
        hive_name = result["hive"]["name"]
        supervisor = result["supervisor"]
        log(f"  Hive ready: {hive_name} | login: {supervisor['username']} / {supervisor['password']}")

        # Store dataset
        from seeders.cmms import generate_dataset
        ds = generate_dataset(industry=industry, size=size, cmms_type=cmms_type,
                              seed=result["dataset_summary"]["seed"])
        CMMS_STATE["dataset"]      = ds
        CMMS_STATE["summary"]      = ds.summary()
        CMMS_STATE["generated_at"] = datetime.now(timezone.utc).isoformat()

        # Step 2: Run CRUD validators (scripts live in WORKHIVE_ROOT)
        log("Quick Demo — Step 2: Running CRUD validators...")
        validator_results = {}
        seeder_dir = Path(__file__).parent
        py = seeder_dir / "venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = Path("python")

        for script_name in [
            "validate_logbook_consistency.py",
            "validate_pattern_alerts.py",
            "validate_inventory_integrity.py",
        ]:
            script_path = WORKHIVE_ROOT / script_name
            log(f"  Running {script_name}...")
            try:
                proc = subprocess.Popen(
                    [str(py), str(script_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(seeder_dir), bufsize=1,
                    text=True, encoding="utf-8", errors="replace",
                )
                import re as _re
                ansi = _re.compile(r"\x1b\[[0-9;]*m")
                last = ""
                for line in proc.stdout:
                    clean = ansi.sub("", line.rstrip())
                    if clean:
                        log(clean)
                        if "Summary" in clean or "pass" in clean.lower():
                            last = clean
                proc.wait()
                validator_results[script_name] = {"summary": last, "exit_code": proc.returncode}
            except Exception as e:
                log(f"  ERROR: {e}")
                validator_results[script_name] = {"summary": str(e), "exit_code": 1}

        passed = sum(1 for r in validator_results.values() if r.get("exit_code") == 0)
        log(f"  Validators: {passed}/{len(validator_results)} passed")

        return {
            "hive":       result["hive"],
            "supervisor": supervisor,
            "bridge":     result["bridge"],
            "validators": validator_results,
            "validators_passed": passed,
            "login_url":  "http://127.0.0.1:5000/workhive/index.html",
        }

    _run_job("quick_demo", run_quick_demo)
    return jsonify({"started": True})


@app.route("/api/run-crud-tests", methods=["POST"])
def api_run_crud_tests():
    """Runs the CRUD-verification validators — checks that Supabase writes actually land.

    Catches silent-save-failure bugs: update returns error:null but 0 rows updated,
    parts deducted even when status update failed, delete that removes nothing.
    """
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409

    def run_crud(client, log):
        # Validators live in WORKHIVE_ROOT, not in the seeder subfolder.
        # Use the seeder venv's python but point at the correct script path.
        results = {}
        seeder_dir = Path(__file__).parent
        py = seeder_dir / "venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = Path("python")

        for script_name in [
            "validate_logbook_consistency.py",
            "validate_pattern_alerts.py",
            "validate_inventory_integrity.py",
        ]:
            script_path = WORKHIVE_ROOT / script_name
            log(f"  Running {script_name}...")
            try:
                proc = subprocess.Popen(
                    [str(py), str(script_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(seeder_dir), bufsize=1,
                    text=True, encoding="utf-8", errors="replace",
                )
                import re as _re
                ansi = _re.compile(r"\x1b\[[0-9;]*m")
                last_summary = ""
                for line in proc.stdout:
                    clean = ansi.sub("", line.rstrip())
                    if clean:
                        log(clean)
                        if "Summary" in clean or "pass" in clean.lower():
                            last_summary = clean
                proc.wait()
                results[script_name] = {"summary": last_summary, "exit_code": proc.returncode}
            except Exception as e:
                log(f"  ERROR running {script_name}: {e}")
                results[script_name] = {"summary": str(e), "exit_code": 1}
        summary_passes = sum(1 for r in results.values() if r.get("exit_code") == 0)
        summary_fails  = len(results) - summary_passes
        return {
            "validators": results,
            "passed": summary_passes,
            "failed": summary_fails,
            "summary": f"{summary_passes}/{len(results)} validators passed",
        }

    _run_job("crud_tests", run_crud)
    return jsonify({"started": True})


@app.route("/api/run-flows", methods=["POST"])
def api_run_flows():
    """Runs the Playwright UI flow suite (drives Chromium against the proxy)."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("run_flows", lambda c, log: _run_subprocess("run_flows.py", log))
    return jsonify({"started": True})


def _run_release_gate(extra_args: list = None):
    """Helper to launch release_gate.py with optional flags."""
    def _run(client, log):
        gate = WORKHIVE_ROOT / "release_gate.py"
        if not gate.exists():
            log(f"ERROR: release_gate.py not found at {gate}")
            return {"exit_code": 1}
        # -u: unbuffered stdout/stderr, so live log streams in real time.
        cmd = [sys.executable, "-u", str(gate)] + (extra_args or [])
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(WORKHIVE_ROOT), bufsize=1,
            text=True, encoding="utf-8", errors="replace",
        )
        import re as _re
        ansi = _re.compile(r"\x1b\[[0-9;]*m")
        for line in proc.stdout:
            clean = ansi.sub("", line.rstrip())
            if clean:
                log(clean)
        proc.wait()
        return {"exit_code": proc.returncode}
    return _run


@app.route("/api/run-gate", methods=["POST"])
def api_run_gate():
    """Runs the full release gate (pre-flight + reseed + static + data + UI)."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("release_gate", _run_release_gate())
    return jsonify({"started": True})


@app.route("/api/run-gate-ai", methods=["POST"])
def api_run_gate_ai():
    """Runs the full release gate WITH AI Full pack (adds Groq API calls)."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("release_gate_ai", _run_release_gate(["--with-ai"]))
    return jsonify({"started": True})


@app.route("/api/run-gate-visual", methods=["POST"])
def api_run_gate_visual():
    """Gate + visual regression only (no AI, no perf). Faster than Mega Gate.

    ~3-4 min on a warm cache. Useful for verifying visual baselines after a
    seeder change, without paying for the AI or perf passes.
    """
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("release_gate_visual", _run_release_gate(["--with-visual"]))
    return jsonify({"started": True})


@app.route("/api/run-mega-gate", methods=["POST"])
def api_run_mega_gate():
    """Mega Gate: release gate + AI Full + visual regression + performance budgets.

    The most thorough single-click validation. ~7-10 min on a warm cache.
    """
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job(
        "mega_gate",
        _run_release_gate(["--with-ai", "--with-visual", "--with-perf"]),
    )
    return jsonify({"started": True})


# ---------- Health panel data (Phase 2) ----------

def _parse_backlog_items():
    """Parse PRODUCTION_FIXES.md into categorized item lists.

    Returns a dict keyed by category with a list of {num, title, status, date}.
    Used by both the count summary and the drill-down endpoint.
    """
    items = {"critical": [], "important": [], "nice_to_have": [], "fixed": []}
    if not FINDINGS_FILE.exists():
        return items
    text = FINDINGS_FILE.read_text(encoding="utf-8")
    import re as _re
    sections = {
        "critical":     r"## 🔴 Critical",
        "important":    r"## 🟡 Important",
        "nice_to_have": r"## 🟢 Nice to have",
        "fixed":        r"## ✅ Fixed",
    }
    for key, header in sections.items():
        m = _re.search(rf"{header}.*?(?=\n## |\Z)", text, _re.DOTALL)
        if not m:
            continue
        body = m.group(0)
        if "_(none" in body:
            continue
        for entry in _re.finditer(r"^###\s+([\w-]+)\.\s+(.+?)$", body, _re.MULTILINE):
            num = entry.group(1)
            line = entry.group(2).strip()
            tail = _re.search(
                r"\s+[—\-]\s+(FIXED|OPEN|WIP|DEFERRED)(?:\s+(\d{4}-\d{2}-\d{2}))?\s*$",
                line,
            )
            if tail:
                title = line[:tail.start()].rstrip()
                status = tail.group(1)
                date = tail.group(2)
            else:
                title = line
                status = "FIXED" if key == "fixed" else "OPEN"
                date = None
            items[key].append({
                "num": num,
                "title": title,
                "status": status,
                "date": date,
            })
    return items


def _parse_backlog():
    """Count entries per PRODUCTION_FIXES.md category (used by /api/health)."""
    items = _parse_backlog_items()
    return {k: len(v) for k, v in items.items()}


@app.route("/api/health")
def api_health():
    """Returns the unified health snapshot for the dashboard panel."""
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from lib.health_score import compute_score, tier_for
        from lib.run_history import latest_run, load_streak
    except Exception as e:
        return jsonify({"error": f"health libs unavailable: {e}"}), 500

    streak = load_streak()
    last = latest_run()

    response = {
        "streak": {
            "current": streak.get("current_streak", 0),
            "best": streak.get("best_streak", 0),
            "last_green_date": streak.get("last_green_date"),
            "last_green_commit": (streak.get("last_green_commit") or "")[:8],
            "last_run_date": streak.get("last_run_date"),
            "last_run_verdict": streak.get("last_run_verdict"),
            "broken_at": streak.get("broken_at"),
            "broken_after_days": streak.get("broken_after_days"),
        },
        "last_run": last,
        "backlog": _parse_backlog(),
    }

    if last:
        # Recompute score with stale-aware penalty (last run > 24h ago = -10)
        recomputed = compute_score(last.get("layers", {}), last_run_iso=last.get("timestamp"))
        response["score"] = recomputed["score"]
        response["tier"] = recomputed["tier"]
        response["stale"] = recomputed["stale"]
        response["breakdown"] = recomputed["breakdown"]
    else:
        response["score"] = None
        response["tier"] = "No runs yet"
        response["stale"] = False
        response["breakdown"] = []

    return jsonify(response)


@app.route("/api/health/details/<layer>")
def api_health_details(layer):
    """Returns per-test detail for a single layer (drill-down view)."""
    layer = layer.lower()
    seeder_tmp = Path(__file__).parent / ".tmp"

    if layer == "static":
        # Read platform_health.json from project root
        ph = WORKHIVE_ROOT / "platform_health.json"
        if not ph.exists():
            return jsonify({"layer": layer, "sections": [], "error": "platform_health.json not found. Run the gate first."}), 200
        try:
            data = json.loads(ph.read_text(encoding="utf-8"))
        except Exception as e:
            return jsonify({"layer": layer, "sections": [], "error": str(e)}), 200
        # Format for drill-down
        validators = data.get("validators", [])
        tests = []
        for v in validators:
            status = (v.get("status") or "").upper()
            tests.append({
                "status": status,
                "message": v.get("label") or v.get("id") or "?",
                "elapsed": v.get("elapsed"),
            })
        return jsonify({
            "layer": layer,
            "timestamp": data.get("timestamp"),
            "sections": [{"section": "All validators", "tests": tests}],
        })

    if layer == "data":
        f = seeder_tmp / "last_data_run.json"
        if not f.exists():
            return jsonify({"layer": layer, "sections": [], "error": "Run data tests once to populate this view."}), 200
        return jsonify({"layer": layer, **json.loads(f.read_text(encoding="utf-8"))})

    if layer == "ui":
        f = seeder_tmp / "last_ui_run.json"
        if not f.exists():
            return jsonify({"layer": layer, "sections": [], "error": "Run UI tests once to populate this view."}), 200
        return jsonify({"layer": layer, **json.loads(f.read_text(encoding="utf-8"))})

    return jsonify({"layer": layer, "error": "unknown layer"}), 400


@app.route("/api/failures/summary")
def api_failures_summary():
    """Aggregate all FAIL (and optionally WARN) entries across Static + Data + UI layers.

    Returns a structured list ready for copy-paste into a chat or bug report.
    Query param: ?include_warn=1 to include WARNs too.
    """
    include_warn = request.args.get("include_warn", "0") == "1"
    seeder_tmp   = Path(__file__).parent / ".tmp"
    failures     = []

    # ── Static layer ──────────────────────────────────────────────────────────
    ph = WORKHIVE_ROOT / "platform_health.json"
    if ph.exists():
        try:
            data       = json.loads(ph.read_text(encoding="utf-8"))
            validators = data.get("validators", [])
            for v in validators:
                status = (v.get("status") or "").upper()
                if status == "FAIL" or (include_warn and status in ("WARN", "SKIP")):
                    failures.append({
                        "layer":   "Static",
                        "status":  status,
                        "test":    v.get("label") or v.get("id") or "?",
                        "detail":  v.get("detail") or v.get("error") or "",
                    })
        except Exception:
            pass

    # ── Data + UI layers ──────────────────────────────────────────────────────
    for layer_name, fname in [("Data", "last_data_run.json"), ("UI", "last_ui_run.json")]:
        f = seeder_tmp / fname
        if not f.exists():
            continue
        try:
            run_data = json.loads(f.read_text(encoding="utf-8"))
            for section in run_data.get("sections", []):
                sec_label = section.get("section", "")
                for test in section.get("tests", []):
                    status = (test.get("status") or "").upper()
                    if status == "FAIL" or (include_warn and status == "WARN"):
                        failures.append({
                            "layer":   layer_name,
                            "status":  status,
                            "test":    f"{sec_label} — {test.get('message', '?')}",
                            "detail":  "",
                        })
        except Exception:
            pass

    # Build plain-text summary for copy-paste
    lines = [f"Gate failures ({len([f for f in failures if f['status']=='FAIL'])} FAIL"
             + (f", {len([f for f in failures if f['status']=='WARN'])} WARN" if include_warn else "")
             + "):"]
    lines.append("")
    current_layer = None
    for f in failures:
        if f["layer"] != current_layer:
            current_layer = f["layer"]
            lines.append(f"── {current_layer} ──")
        prefix = "✗" if f["status"] == "FAIL" else "⚠"
        lines.append(f"  {prefix} {f['test']}")
        if f["detail"]:
            lines.append(f"      {f['detail'][:120]}")

    return jsonify({
        "failures": failures,
        "fail_count": len([x for x in failures if x["status"] == "FAIL"]),
        "warn_count": len([x for x in failures if x["status"] == "WARN"]),
        "text": "\n".join(lines),
    })


@app.route("/api/health/history")
def api_health_history():
    """Returns the last N runs as a flat array (oldest first) for the sparkline."""
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from lib.run_history import load_history
    except Exception as e:
        return jsonify({"error": f"history libs unavailable: {e}", "runs": []}), 500
    try:
        n = int(request.args.get("n", "30"))
    except ValueError:
        n = 30
    n = max(1, min(n, 50))
    history = load_history()[-n:]
    runs = []
    for r in history:
        runs.append({
            "timestamp":    r.get("timestamp"),
            "commit_short": r.get("commit_short"),
            "verdict":      r.get("verdict"),
            "score":        r.get("score"),
            "tier":         r.get("tier"),
            "flags":        r.get("flags") or [],
        })
    return jsonify({"runs": runs, "count": len(runs)})


@app.route("/api/health/trends")
def api_health_trends():
    """Detect notable trends in the run history.

    Each alert is fired only when the signal is meaningful (not noise).
    Returns a list ready for the dashboard to render as chips.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from lib.run_history import load_history
    except Exception as e:
        return jsonify({"error": f"history libs unavailable: {e}", "alerts": []}), 500

    history = load_history()
    if not history:
        return jsonify({"alerts": [], "runs_analyzed": 0})

    alerts = []

    def _score(r):
        s = r.get("score")
        return None if s is None else int(s)

    def _verdict(r):
        return (r.get("verdict") or "").upper()

    latest = history[-1]
    latest_score = _score(latest)
    latest_verdict = _verdict(latest)
    latest_flags = latest.get("flags") or []

    # ── Alert: score delta vs previous run ────────────────────────────────
    if len(history) >= 2 and latest_score is not None:
        prev = history[-2]
        prev_score = _score(prev)
        if prev_score is not None:
            delta = latest_score - prev_score
            if delta <= -5:
                alerts.append({
                    "kind": "score_decline",
                    "severity": "warn",
                    "title": f"Score dropped {abs(delta)} points",
                    "detail": f"{prev_score} → {latest_score} (since previous run). Check the layer drill-down to see where.",
                })
            elif delta >= 5:
                alerts.append({
                    "kind": "score_recovery",
                    "severity": "good",
                    "title": f"Score recovered +{delta} points",
                    "detail": f"{prev_score} → {latest_score}. Whatever you fixed is working.",
                })

    # ── Alert: latest is a personal best (or matches it) ──────────────────
    if latest_score is not None and len(history) >= 3:
        prior_max = max((_score(r) or 0) for r in history[:-1])
        if latest_score > prior_max:
            alerts.append({
                "kind": "personal_best",
                "severity": "good",
                "title": f"New personal best: {latest_score}",
                "detail": f"Beat previous best of {prior_max}.",
            })

    # ── Alert: streak broken (latest run is BLOCK after a PASS streak) ────
    if latest_verdict in {"BLOCK", "NO-GO", "FAIL"} and len(history) >= 2:
        # Count consecutive PASSes before the latest BLOCK
        passes_before = 0
        for r in reversed(history[:-1]):
            if _verdict(r) == "PASS":
                passes_before += 1
            else:
                break
        if passes_before >= 2:
            alerts.append({
                "kind": "streak_broken",
                "severity": "warn",
                "title": f"Streak broken (was {passes_before} green run{'s' if passes_before != 1 else ''})",
                "detail": "Latest run blocked. The drill-down shows what regressed.",
            })

    # ── Alert: streak forming / extended (3+ consecutive PASSes) ──────────
    if latest_verdict == "PASS":
        consecutive = 0
        for r in reversed(history):
            if _verdict(r) == "PASS":
                consecutive += 1
            else:
                break
        if consecutive >= 3:
            alerts.append({
                "kind": "streak_extended",
                "severity": "good",
                "title": f"{consecutive} consecutive green runs",
                "detail": "Stable territory. Safe to keep shipping.",
            })

    # ── Alert: sustained block (2+ consecutive BLOCKs) ────────────────────
    if latest_verdict in {"BLOCK", "NO-GO", "FAIL"}:
        consecutive_blocks = 0
        for r in reversed(history):
            if _verdict(r) in {"BLOCK", "NO-GO", "FAIL"}:
                consecutive_blocks += 1
            else:
                break
        if consecutive_blocks >= 2:
            alerts.append({
                "kind": "sustained_block",
                "severity": "bad",
                "title": f"{consecutive_blocks} consecutive blocked runs",
                "detail": "The same regression keeps blocking. Pin it as critical in the backlog.",
            })

    # ── Alert: layer regression (specific layer dropped pass-rate) ────────
    if len(history) >= 2:
        latest_layers = latest.get("layers") or {}
        prev_layers = history[-2].get("layers") or {}
        for layer_key in ("static", "data", "ui"):
            l_now = latest_layers.get(layer_key)
            l_prev = prev_layers.get(layer_key)
            if not l_now or not l_prev:
                continue
            now_total  = (l_now.get("pass") or 0) + (l_now.get("fail") or 0) + (l_now.get("warn") or 0)
            prev_total = (l_prev.get("pass") or 0) + (l_prev.get("fail") or 0) + (l_prev.get("warn") or 0)
            now_fail  = l_now.get("fail") or 0
            prev_fail = l_prev.get("fail") or 0
            # Fire if fail count grew by 1+ AND wasn't already failing
            if now_fail > prev_fail and prev_fail == 0:
                alerts.append({
                    "kind": "layer_regression",
                    "severity": "warn",
                    "title": f"{layer_key.title()} layer started failing",
                    "detail": f"{now_fail} fail(s) in latest run, was 0 before. Click '{layer_key}' in the drill-down.",
                })

    return jsonify({
        "alerts": alerts,
        "runs_analyzed": len(history),
        "latest": {
            "score": latest_score,
            "verdict": latest_verdict,
            "flags": latest_flags,
            "timestamp": latest.get("timestamp"),
        },
    })


def _next_backlog_num():
    """Return the next available item number across all sections.

    Items are globally numbered (e.g. #2, #7, #8, #10 are scattered across
    Important and Fixed). New entries take max+1 to avoid collisions.
    """
    if not FINDINGS_FILE.exists():
        return 1
    text = FINDINGS_FILE.read_text(encoding="utf-8")
    import re as _re
    nums = []
    for m in _re.finditer(r"^###\s+(\d+)(?:[-\d]*)?\.\s+", text, _re.MULTILINE):
        try:
            nums.append(int(m.group(1)))
        except ValueError:
            pass
    return (max(nums) + 1) if nums else 1


def _append_backlog_entry(category: str, title: str, body: str) -> dict:
    """Insert a new entry into the matching PRODUCTION_FIXES.md section.

    Returns {ok, num, category} or {ok: False, error}.

    Strategy:
    - If the section currently shows `_(none currently)_`, replace that
      placeholder with the new entry (keeps the section clean).
    - Otherwise, append the entry just before the section's trailing `---`
      so existing entries are preserved and date order is roughly newest-last.
    """
    if category not in {"critical", "important", "nice_to_have"}:
        return {"ok": False, "error": f"unknown category: {category}"}
    if not title.strip():
        return {"ok": False, "error": "title is required"}

    headers = {
        "critical":     "## 🔴 Critical",
        "important":    "## 🟡 Important",
        "nice_to_have": "## 🟢 Nice to have",
    }
    header = headers[category]

    if not FINDINGS_FILE.exists():
        # Bootstrap a minimal file from scratch
        FINDINGS_FILE.write_text(
            "# Production Fixes — Discovered During Testing\n\n"
            "## 🔴 Critical — breaks a user flow\n\n_(none currently)_\n\n---\n\n"
            "## 🟡 Important — degrades UX or data quality\n\n_(none currently)_\n\n---\n\n"
            "## 🟢 Nice to have — polish, refactors, doc gaps\n\n_(none currently)_\n\n---\n\n"
            "## ✅ Fixed — for the changelog\n\n_(none currently)_\n",
            encoding="utf-8",
        )

    text = FINDINGS_FILE.read_text(encoding="utf-8")
    import re as _re

    # Find the FIRST occurrence of the target section and its end (next ## or EOF)
    sec_match = _re.search(
        rf"({_re.escape(header)}[^\n]*\n)(.*?)(?=\n## |\Z)",
        text,
        _re.DOTALL,
    )
    if not sec_match:
        return {"ok": False, "error": f"section header not found: {header}"}

    section_header_line = sec_match.group(1)  # e.g. "## 🔴 Critical — breaks…\n"
    section_body = sec_match.group(2)
    sec_start = sec_match.start()
    sec_end = sec_match.end()

    num = _next_backlog_num()
    today = datetime.now(timezone.utc).date().isoformat()
    entry = f"\n### {num}. {title.strip()} — OPEN {today}\n\n{body.rstrip()}\n\n"

    if "_(none currently)_" in section_body:
        # Replace the placeholder
        new_body = section_body.replace("_(none currently)_\n", entry.lstrip("\n"), 1)
    else:
        # Append to the end of the section, keeping any trailing `---`
        # Strip a trailing `---\n` if present so we can put the entry above it
        body_stripped = section_body.rstrip()
        if body_stripped.endswith("---"):
            body_stripped = body_stripped[:-3].rstrip()
            new_body = body_stripped + "\n" + entry + "---\n\n"
        else:
            new_body = section_body.rstrip() + entry

    new_text = text[:sec_start] + section_header_line + new_body + text[sec_end:]
    # Update the "Last updated" line if present
    new_text = _re.sub(
        r"^\*\*Last updated:\*\*\s*\d{4}-\d{2}-\d{2}",
        f"**Last updated:** {today}",
        new_text,
        count=1,
        flags=_re.MULTILINE,
    )
    FINDINGS_FILE.write_text(new_text, encoding="utf-8")
    return {"ok": True, "num": num, "category": category}


# ── Phase 15: AI-Assisted Repro ───────────────────────────────────────────────
# When a test fails, build a paste-ready prompt with all the context an LLM
# would need to suggest a root cause + fix. Lets the user lean on Claude/Groq/
# their AI of choice without copy-pasting context manually.

@app.route("/api/ai/diagnose-prompt", methods=["POST"])
def api_ai_diagnose_prompt():
    """Build a context-rich diagnostic prompt for a failing test or backlog item."""
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from lib.run_history import latest_run, load_history
    except Exception:
        latest_run = lambda: None
        load_history = lambda: []

    data = request.get_json(silent=True) or {}
    layer = (data.get("layer") or "?").strip()
    section = (data.get("section") or "").strip()
    status = (data.get("status") or "FAIL").strip().upper()
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"ok": False, "error": "message is required"}), 400

    # Pull the latest run snapshot
    last = latest_run() or {}
    history = load_history()
    recent = history[-5:] if history else []

    # Pull recent FIXED entries from PRODUCTION_FIXES.md (max 3)
    fixed_summaries = []
    if FINDINGS_FILE.exists():
        text = FINDINGS_FILE.read_text(encoding="utf-8")
        m = re.search(r"## ✅ Fixed.*", text, re.DOTALL)
        if m:
            fixed_block = m.group(0)
            for entry in re.finditer(r"^###\s+([\w-]+)\.\s+(.+?)$", fixed_block, re.MULTILINE):
                num = entry.group(1)
                line = entry.group(2).strip()
                tail = re.search(r"\s+[—\-]\s+(FIXED|OPEN|WIP|DEFERRED)(?:\s+(\d{4}-\d{2}-\d{2}))?\s*$", line)
                title = line[:tail.start()].rstrip() if tail else line
                fixed_summaries.append(f"- #{num}: {title}")
                if len(fixed_summaries) >= 3:
                    break

    # Build the prompt
    parts = []
    parts.append("# WorkHive gate failure — diagnosis request")
    parts.append("")
    parts.append("I'm running the WorkHive Tester gate (test-data-seeder + release_gate.py) and one")
    parts.append("test is failing. Please help diagnose the root cause and propose a fix.")
    parts.append("")
    parts.append("## The failing test")
    parts.append("")
    parts.append(f"- **Layer:** `{layer}` (one of static / data / ui)")
    if section:
        parts.append(f"- **Section:** `{section}`")
    parts.append(f"- **Status:** `{status}`")
    parts.append(f"- **Message:** `{message}`")
    parts.append("")
    parts.append("## Latest gate run")
    if last:
        parts.append(f"- timestamp: {last.get('timestamp', '?')}")
        parts.append(f"- verdict: {last.get('verdict', '?')}, score: {last.get('score', '?')}/100, tier: {last.get('tier', '?')}")
        flags = last.get("flags") or []
        if flags:
            parts.append(f"- flags: {' '.join(flags)}")
        layers = last.get("layers") or {}
        if layers:
            parts.append("- per-layer:")
            for k, v in layers.items():
                parts.append(f"  - {k}: {v.get('pass', 0)} pass / {v.get('warn', 0)} warn / {v.get('fail', 0)} fail")
    else:
        parts.append("- no run history yet")
    parts.append("")
    if recent and len(recent) >= 2:
        parts.append("## Last few runs (oldest first)")
        for r in recent:
            parts.append(f"- {r.get('timestamp','?')[:19]} · {r.get('verdict','?')} · score {r.get('score','?')} · {' '.join(r.get('flags') or [])}")
        parts.append("")
    if fixed_summaries:
        parts.append("## Recent fixed bugs (might be related)")
        parts.extend(fixed_summaries)
        parts.append("")
    parts.append("## Repo context")
    parts.append("")
    parts.append("- Industrial intelligence web platform, ~30 HTML pages at the project root.")
    parts.append("- Backend: Supabase (Postgres, edge functions in `supabase/functions/<name>/index.ts`).")
    parts.append("- Static layer: `validate_*.py` validators registered in `run_platform_checks.py`.")
    parts.append("- Data layer: `test-data-seeder/run_tests.py` runs in-memory data checks against seeded tables.")
    parts.append("- UI layer: `test-data-seeder/run_flows.py` drives Chromium via Playwright.")
    parts.append("- Migrations under `supabase/migrations/` are the canonical schema source of truth.")
    parts.append("")
    parts.append("## Please respond with")
    parts.append("")
    parts.append("1. **Likely root cause** (1-2 sentences, specific not generic)")
    parts.append("2. **Where to look** (file paths and line numbers if you can infer them from the message)")
    parts.append("3. **How to reproduce** (concrete steps)")
    parts.append("4. **Suggested fix** (the smallest change that should restore green)")
    parts.append("5. **Validator/test that should catch this kind of regression in future**")
    parts.append("")
    parts.append("If the message looks like a known false-positive (visual baseline drift, time-sensitive UI, unconfigured optional feature), call that out before suggesting a code fix.")

    prompt = "\n".join(parts)
    return jsonify({
        "ok": True,
        "prompt": prompt,
        "context_size": len(prompt),
    })


# ── Phase 14: Skill Self-Improvement ──────────────────────────────────────────
# Skills live at ~/.claude/skills/<id>/SKILL.md. Each captures lessons learned
# across sessions. After every bug fix, the user (per CLAUDE.md) should add
# what was learned to the relevant skills. This wizard makes that one click.

SKILLS_ROOT = Path.home() / ".claude" / "skills"


@app.route("/api/skills/list")
def api_skills_list():
    """Return the list of available skills with id + frontmatter description."""
    if not SKILLS_ROOT.is_dir():
        return jsonify({"skills": [], "error": f"skills dir not found: {SKILLS_ROOT}"})
    skills = []
    for d in sorted(SKILLS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        # Pull description from frontmatter
        desc = ""
        m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL | re.MULTILINE)
        if m:
            fm = m.group(1)
            dm = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
            if dm:
                desc = dm.group(1).strip().strip('"').strip("'")
        skills.append({
            "id": d.name,
            "description": desc,
            "size_kb": round(skill_md.stat().st_size / 1024, 1),
        })
    return jsonify({"skills": skills, "count": len(skills)})


@app.route("/api/skills/append-lesson", methods=["POST"])
def api_skills_append_lesson():
    """Append a new lesson section to a skill's SKILL.md."""
    data = request.get_json(silent=True) or {}
    skill_id = (data.get("skill_id") or "").strip()
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    source = (data.get("source") or "").strip()

    if not skill_id or not re.match(r"^[a-z][a-z0-9-]+$", skill_id):
        return jsonify({"ok": False, "error": "skill_id must be a kebab-case name"}), 400
    if not title:
        return jsonify({"ok": False, "error": "title is required"}), 400
    if not body:
        return jsonify({"ok": False, "error": "body is required"}), 400

    skill_md = SKILLS_ROOT / skill_id / "SKILL.md"
    if not skill_md.exists():
        return jsonify({"ok": False, "error": f"skill not found: {skill_id}"}), 404

    today = datetime.now(timezone.utc).date().isoformat()
    section_header = f"## Lesson {today}: {title}"

    # Idempotency: refuse if a section with the exact same header already exists
    existing = skill_md.read_text(encoding="utf-8")
    if section_header in existing:
        return jsonify({
            "ok": False,
            "error": f"a section titled '{section_header}' already exists in this skill",
        }), 409

    lines = [
        "",
        section_header,
        "",
    ]
    if source:
        lines += [f"**Source:** {source}", ""]
    lines += [body.rstrip(), ""]
    new_section = "\n".join(lines)

    if not existing.endswith("\n"):
        existing += "\n"
    skill_md.write_text(existing + new_section, encoding="utf-8")

    return jsonify({
        "ok": True,
        "skill_id": skill_id,
        "section_header": section_header,
        "skill_md": str(skill_md),
    })


# ── Phase 9: New Feature Wizard ───────────────────────────────────────────────
# Scaffolds new edge functions (and later, HTML pages) with all the
# registrations the Auto-discovery validator looks for. Removes the
# "I forgot to add it to config.toml" mistake.

EDGE_FN_TEMPLATE = '''/**
 * {name} — short description here
 *
 * POST /functions/v1/{name}
 * Body: {{ ... }}
 *
 * TODO: replace this stub with the real handler.
 */

import {{ serve }} from 'https://deno.land/std@0.168.0/http/server.ts';

/* ── CORS ──────────────────────────────────────────────────────────────── */
function getCorsHeaders(req: Request): Record<string, string> {{
  const origin = req.headers.get('origin') || '';
  const allowed = [
    'https://workhiveph.com',
    'https://www.workhiveph.com',
    'http://localhost',
    'null', // file:// local testing
  ];
  const allowedOrigin = allowed.includes(origin) ? origin : allowed[0];
  return {{
    'Access-Control-Allow-Origin':  allowedOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  }};
}}

function json(data: unknown, status: number, req: Request) {{
  return new Response(JSON.stringify(data), {{
    status,
    headers: {{ 'Content-Type': 'application/json', ...getCorsHeaders(req) }},
  }});
}}

function errJson(error: string, status: number, req: Request) {{
  return new Response(JSON.stringify({{ error }}), {{
    status,
    headers: {{ 'Content-Type': 'application/json', ...getCorsHeaders(req) }},
  }});
}}

/* ── Handler ───────────────────────────────────────────────────────────── */
serve(async (req: Request) => {{
  if (req.method === 'OPTIONS') {{
    return new Response('ok', {{ headers: getCorsHeaders(req) }});
  }}
  if (req.method !== 'POST') {{
    return errJson('method not allowed', 405, req);
  }}

  let body: Record<string, unknown> = {{}};
  try {{
    body = await req.json();
  }} catch {{
    return errJson('invalid JSON body', 400, req);
  }}

  // TODO: implement {name} logic here.
  return json({{ ok: true, received: body }}, 200, req);
}});
'''


def _is_valid_fn_name(name: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9-]{1,40}[a-z0-9]$", name)) if name else False


@app.route("/api/wizard/edge-function", methods=["POST"])
def api_wizard_edge_function():
    """Scaffold a new Supabase edge function and register it in config.toml."""
    import re as _re
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    verify_jwt = bool(data.get("verify_jwt"))

    # Validate name (kebab-case, 3-42 chars, no dirty chars)
    if not _is_valid_fn_name(name):
        return jsonify({
            "ok": False,
            "error": "Invalid name. Use kebab-case, 3-42 chars, e.g. 'report-export' or 'send-pricing-email'.",
        }), 400

    fns_dir = WORKHIVE_ROOT / "supabase" / "functions" / name
    config_toml = WORKHIVE_ROOT / "supabase" / "config.toml"

    if fns_dir.exists():
        return jsonify({"ok": False, "error": f"supabase/functions/{name}/ already exists"}), 409

    if not config_toml.exists():
        return jsonify({"ok": False, "error": "supabase/config.toml not found"}), 500

    # Read config.toml — make sure no duplicate block
    config_text = config_toml.read_text(encoding="utf-8")
    if _re.search(rf"\[functions\.{_re.escape(name)}\]", config_text):
        return jsonify({"ok": False, "error": f"[functions.{name}] block already in config.toml"}), 409

    # Create directory + index.ts
    fns_dir.mkdir(parents=True, exist_ok=False)
    (fns_dir / "index.ts").write_text(
        EDGE_FN_TEMPLATE.format(name=name),
        encoding="utf-8",
    )

    # Append config.toml block (preserve trailing newline)
    if not config_text.endswith("\n"):
        config_text += "\n"
    config_text += (
        f"\n[functions.{name}]\n"
        f"enabled = true\n"
        f"verify_jwt = {'true' if verify_jwt else 'false'}\n"
    )
    config_toml.write_text(config_text, encoding="utf-8")

    # Re-run auto-discovery to confirm registration sticks
    auto_discovery_ok = None
    auto_discovery_msg = None
    try:
        proc = subprocess.run(
            [sys.executable, str(WORKHIVE_ROOT / "validate_auto_discovery.py")],
            cwd=str(WORKHIVE_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        auto_discovery_ok = proc.returncode == 0
        auto_discovery_msg = (proc.stdout or "")[-400:]
    except Exception as e:
        auto_discovery_msg = f"verifier crashed: {e}"

    return jsonify({
        "ok": True,
        "name": name,
        "files_created": [
            f"supabase/functions/{name}/index.ts",
        ],
        "config_block_added": f"[functions.{name}]",
        "verify_jwt": verify_jwt,
        "auto_discovery_pass": auto_discovery_ok,
        "auto_discovery_tail": auto_discovery_msg,
    })


# ── HTML page template (Phase 9.b) ────────────────────────────────────────────
# Minimal but functional skeleton matching the auth+nav boot pattern in
# dayplanner.html etc. The user replaces the placeholders with the real page.

HTML_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__DISPLAY_NAME__ | WorkHive</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<link rel="manifest" href="manifest.json">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0f1923; --surface: #162032; --card: #1d2e44;
    --gold: #F7A21B; --blue: #29B6D9; --text: #F4F6FA;
    --muted: rgba(255,255,255,0.55);
    --border: rgba(255,255,255,0.07);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Poppins', system-ui, sans-serif;
    background: var(--bg); color: var(--text);
    padding-top: 60px;
    min-height: 100vh;
  }
  main { max-width: 1140px; margin: 0 auto; padding: 24px; }
  h1 { font-weight: 800; margin-bottom: 16px; letter-spacing: -0.01em; }
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 20px 22px; margin: 14px 0;
  }
</style>
</head>
<body>
<main>
  <h1>__DISPLAY_NAME__</h1>
  <div class="card">
    <p>TODO: build the __DISPLAY_NAME__ page here.</p>
    <p style="margin-top:8px; color:var(--muted); font-size:0.85rem;">
      This file was scaffolded by the WorkHive Tester wizard. Replace this stub with the real UI,
      and remember to run <code>python validate_auto_discovery.py</code> after any registry changes.
    </p>
  </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script src="utils.js"></script>
<script>
  let WORKER_NAME = localStorage.getItem('wh_last_worker') || localStorage.getItem('wh_worker_name') || '';
  let _authUid = null;

  var db = supabase.createClient(
    'https://hzyvnjtisfgbksicrouu.supabase.co',
    'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ' // anon/publishable: safe to expose
  );
  (async () => {
    if (!WORKER_NAME && typeof restoreIdentityFromSession === 'function') {
      WORKER_NAME = await restoreIdentityFromSession(db);
    }
    if (!WORKER_NAME) { window.location.href = 'index.html?signin=1'; return; }
    try {
      const { data: { session } } = await db.auth.getSession();
      _authUid = session?.user?.id || null;
    } catch (e) {}
    console.log('[__NAME__] booted as', WORKER_NAME);
    // TODO: page-specific data loading goes here
  })();
</script>
<script src="nav-hub.js"></script>
<script src="floating-ai.js"></script>
</body>
</html>
"""


def _is_valid_page_name(name: str) -> bool:
    """kebab-case, 3-42 chars, lowercase + digits + hyphens."""
    return bool(re.match(r"^[a-z][a-z0-9-]{1,40}[a-z0-9]$", name))


def _register_in_live_tool_pages(name: str) -> dict:
    """Append a bare name to LIVE_TOOL_PAGES in validate_assistant.py."""
    f = WORKHIVE_ROOT / "validate_assistant.py"
    text = f.read_text(encoding="utf-8")
    if re.search(rf'["\']{re.escape(name)}["\']', text.split("LIVE_TOOL_PAGES", 1)[1].split("]", 1)[0] if "LIVE_TOOL_PAGES" in text else ""):
        return {"file": "validate_assistant.py", "skipped": "already in LIVE_TOOL_PAGES"}
    # Insert the new entry on its own indented line before the closing `]`.
    new_text, n = re.subn(
        r'(LIVE_TOOL_PAGES\s*=\s*\[[^\]]*?)(\n\])',
        rf'\1\n    "{name}",\2',
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        return {"file": "validate_assistant.py", "error": "could not locate LIVE_TOOL_PAGES list"}
    f.write_text(new_text, encoding="utf-8")
    return {"file": "validate_assistant.py", "added": f'"{name}" to LIVE_TOOL_PAGES'}


def _register_in_non_tool_pages(filename: str) -> dict:
    """Append a filename (e.g. 'foo.html') to NON_TOOL_PAGES set in validate_auto_discovery.py."""
    f = WORKHIVE_ROOT / "validate_auto_discovery.py"
    text = f.read_text(encoding="utf-8")
    if f'"{filename}"' in text:
        return {"file": "validate_auto_discovery.py", "skipped": "already in NON_TOOL_PAGES"}
    # Insert the new filename on its own indented line before the closing `}`.
    new_text, n = re.subn(
        r'(NON_TOOL_PAGES\s*=\s*\{[^}]*?)(\n\})',
        rf'\1\n    "{filename}",\2',
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        return {"file": "validate_auto_discovery.py", "error": "could not locate NON_TOOL_PAGES set"}
    f.write_text(new_text, encoding="utf-8")
    return {"file": "validate_auto_discovery.py", "added": f'"{filename}" to NON_TOOL_PAGES'}


def _register_in_nav_hub(name: str, label: str) -> dict:
    """Insert a new TOOLS array entry in nav-hub.js with a generic icon."""
    f = WORKHIVE_ROOT / "nav-hub.js"
    text = f.read_text(encoding="utf-8")
    if f"'{name}.html'" in text or f'"{name}.html"' in text:
        return {"file": "nav-hub.js", "skipped": "href already present"}
    # Generic placeholder icon — a small box / new-page glyph
    icon_svg = (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<line x1="12" y1="8" x2="12" y2="16"/>'
        '<line x1="8" y1="12" x2="16" y2="12"/>'
        '</svg>'
    )
    new_entry = (
        f"    {{ label: '{label}', href: '{name}.html', match: ['{name}'],\n"
        f"      icon: `{icon_svg}` }},\n"
    )
    # Insert before the comment marker that follows the marketplace entry.
    marker = "    // public-feed.html"
    if marker not in text:
        # Fallback: insert before the closing `];` of TOOLS
        new_text, n = re.subn(r"(\n  \];)", "\n" + new_entry + r"\1", text, count=1)
    else:
        new_text = text.replace(marker, new_entry + marker, 1)
        n = 1 if new_text != text else 0
    if n == 0:
        return {"file": "nav-hub.js", "error": "could not locate insertion point"}
    f.write_text(new_text, encoding="utf-8")
    return {"file": "nav-hub.js", "added": f"TOOLS entry for {name}.html"}


def _register_in_floating_ai(name: str, label: str, hint: str) -> dict:
    """Add a path.includes() line in floating-ai.js page-context block."""
    f = WORKHIVE_ROOT / "floating-ai.js"
    text = f.read_text(encoding="utf-8")
    if f"path.includes('{name}')" in text:
        return {"file": "floating-ai.js", "skipped": "page context already present"}
    new_line = (
        f"    if (path.includes('{name}'))    return {{ page: '{name}', "
        f"label: '{label}', hint: '{hint}' }};\n"
    )
    # Insert just before the existing community line — community is near the end
    # of the page-context cascade. If not found, insert before the "default"
    # fallback line.
    inserted = False
    for anchor in [
        "if (path.includes('community'))",
        "// default fallback",
        "return { page: 'index'",
        "return { page: 'home'",
    ]:
        if anchor in text:
            text = text.replace(anchor, new_line.lstrip() + "    " + anchor, 1)
            inserted = True
            break
    if not inserted:
        return {"file": "floating-ai.js", "error": "could not locate insertion point"}
    f.write_text(text, encoding="utf-8")
    return {"file": "floating-ai.js", "added": f"page context for {name}"}


def _register_in_assistant_prompt(name: str, label: str, summary: str) -> dict:
    """Insert a STAGE 2 bullet in assistant.html system prompt."""
    f = WORKHIVE_ROOT / "assistant.html"
    text = f.read_text(encoding="utf-8")
    if f"({name}.html)" in text:
        return {"file": "assistant.html", "skipped": "tool already mentioned in prompt"}
    new_bullet = f"- {label} ({name}.html): {summary}\n"
    # Insert before the NOTES: line that closes the STAGE 2 section
    marker = "NOTES: parts-tracker.html and checklist.html are retired"
    if marker not in text:
        return {"file": "assistant.html", "error": f"could not find marker '{marker}'"}
    text = text.replace(marker, new_bullet + "\n" + marker, 1)
    f.write_text(text, encoding="utf-8")
    return {"file": "assistant.html", "added": f"STAGE 2 bullet for {name}.html"}


# ── Phase 2 wizard helpers (added 2026-05-04) ────────────────────────────────
# Extends the wizard from "scaffold + 4 registries" to true one-click coverage:
# also writes to floating-ai PLATFORM TOOLS, the 5 Tester registries, and the
# 2 LIVE_PAGES validator scopes. Together with the existing 4 helpers above
# this makes the wizard register a new tool page in 9 places per click, which
# covers everything `run_platform_checks.py --fast` checks.

def _register_in_floating_ai_platform_tools(name: str, label: str, summary: str) -> dict:
    """Add a `- {label} ({name}.html): {summary}` bullet to the PLATFORM TOOLS
    section in floating-ai.js. This is separate from the page-context branch
    that `_register_in_floating_ai` adds — that one tells the AI the page name,
    this one tells the AI what the page DOES so it can answer
    'where do I find X?' questions. validate_assistant.py
    `check_platform_tools_completeness` enforces this.
    """
    f = WORKHIVE_ROOT / "floating-ai.js"
    text = f.read_text(encoding="utf-8")
    if f"({name}.html)" in text:
        return {"file": "floating-ai.js (PLATFORM TOOLS)", "skipped": "tool already in PLATFORM TOOLS"}

    new_bullet = f"- {label} ({name}.html): {summary}\n"
    # Insert just before the "Parts Tracker: Retired." line that closes the
    # PLATFORM TOOLS list. Fallback markers for resilience if the file changes.
    for marker in [
        "- Parts Tracker: Retired.",
        "You handle three types of conversations",
    ]:
        if marker in text:
            text = text.replace(marker, new_bullet + marker, 1)
            f.write_text(text, encoding="utf-8")
            return {"file": "floating-ai.js (PLATFORM TOOLS)", "added": f"bullet for {name}.html"}
    return {"file": "floating-ai.js (PLATFORM TOOLS)", "error": "could not locate insertion point"}


def _register_in_tester_public_pages(name: str, label: str) -> dict:
    """Add a `("{name}.html", "{label}")` tuple to PUBLIC_PAGES in
    test-data-seeder/app.py — the Tester needs this to serve the page."""
    f = WORKHIVE_ROOT / "test-data-seeder" / "app.py"
    text = f.read_text(encoding="utf-8")
    if f'"{name}.html"' in text:
        return {"file": "test-data-seeder/app.py (PUBLIC_PAGES)", "skipped": "page already listed"}
    new_text, n = re.subn(
        r'(PUBLIC_PAGES\s*=\s*\[[^\]]*?)(\n\])',
        rf'\1\n    ("{name}.html", "{label}"),\2',
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        return {"file": "test-data-seeder/app.py (PUBLIC_PAGES)", "error": "could not locate PUBLIC_PAGES list"}
    f.write_text(new_text, encoding="utf-8")
    return {"file": "test-data-seeder/app.py (PUBLIC_PAGES)", "added": f'"{name}.html" entry'}


def _register_in_tester_flow(name: str, flow_file: str) -> dict:
    """Add `"{name}.html"` to the PAGES list in a Tester flow file
    (smoke.py / visual.py / mobile.py / performance.py).

    These four files have slightly different PAGES list shapes:
      smoke.py:       list of (filename, label, selector) tuples
      visual/mobile/performance: flat list of filename strings
    We detect which by looking at the first item.
    """
    rel = f"test-data-seeder/flows/{flow_file}"
    f = WORKHIVE_ROOT / "test-data-seeder" / "flows" / flow_file
    text = f.read_text(encoding="utf-8")
    if f'"{name}.html"' in text or f"'{name}.html'" in text:
        return {"file": rel, "skipped": "page already in PAGES"}

    # Detect flow shape: smoke.py uses tuples (filename, label, selector)
    if flow_file == "smoke.py":
        # Best-effort label from name: "analytics-report" -> "Analytics Report"
        label = name.replace("-", " ").title()
        new_entry = f'    ("{name}.html",   "{label}",  "body"),'
    else:
        new_entry = f'    "{name}.html",'

    new_text, n = re.subn(
        r'(PAGES\s*=\s*\[[^\]]*?)(\n\])',
        rf'\1\n{new_entry}\2',
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        return {"file": rel, "error": "could not locate PAGES list"}
    f.write_text(new_text, encoding="utf-8")
    return {"file": rel, "added": f'"{name}.html" to PAGES'}


def _register_in_validator_live_pages(name: str, validator_file: str) -> dict:
    """Add `"{name}.html"` to the LIVE_PAGES list in a validator
    (validate_schema.py or validate_performance.py). These are the per-page
    DB / performance scopes — without registration, the validator silently
    skips your new page.
    """
    f = WORKHIVE_ROOT / validator_file
    text = f.read_text(encoding="utf-8")
    if f'"{name}.html"' in text:
        return {"file": validator_file + " (LIVE_PAGES)", "skipped": "page already in LIVE_PAGES"}
    new_text, n = re.subn(
        r'(LIVE_PAGES\s*=\s*\[[^\]]*?)(\n\])',
        rf'\1\n    "{name}.html",\2',
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        return {"file": validator_file + " (LIVE_PAGES)", "error": "could not locate LIVE_PAGES list"}
    f.write_text(new_text, encoding="utf-8")
    return {"file": validator_file + " (LIVE_PAGES)", "added": f'"{name}.html" entry'}


@app.route("/api/wizard/html-page", methods=["POST"])
def api_wizard_html_page():
    """Scaffold a new HTML page and register it in every registry the gate checks."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    classification = (data.get("classification") or "").strip().lower()
    display_name = (data.get("display_name") or "").strip()
    hint = (data.get("hint") or "").strip()
    summary = (data.get("summary") or "").strip()

    if not _is_valid_page_name(name):
        return jsonify({
            "ok": False,
            "error": "Invalid name. Use kebab-case, 3-42 chars, e.g. 'logbook-v2'.",
        }), 400

    if classification not in {"tool", "non_tool"}:
        return jsonify({
            "ok": False,
            "error": "classification must be 'tool' (registers in 4 places) or 'non_tool' (lands/satellite, registers in 1 place).",
        }), 400

    target = WORKHIVE_ROOT / f"{name}.html"
    if target.exists():
        return jsonify({"ok": False, "error": f"{name}.html already exists at the project root"}), 409

    # Defaults for tool fields
    if not display_name:
        display_name = name.replace("-", " ").title()
    if not hint:
        hint = f"Ask me about the {display_name} page."
    if not summary:
        summary = f"TODO — short description of what {display_name} does."

    # ── Create the HTML file ──────────────────────────────────────────────
    html = HTML_PAGE_TEMPLATE.replace("__DISPLAY_NAME__", display_name).replace("__NAME__", name)
    target.write_text(html, encoding="utf-8")

    # ── Register in registries based on classification ────────────────────
    # For "tool" pages we hit 9 registries in one pass, mirroring everything
    # `run_platform_checks.py --fast` checks. The 4 original (Phase 1) plus
    # the 5 new (Phase 2) below — together this is true one-click coverage.
    registry_results = []
    if classification == "tool":
        # Phase 1 — original 4 registries
        registry_results.append(_register_in_live_tool_pages(name))
        registry_results.append(_register_in_nav_hub(name, display_name))
        registry_results.append(_register_in_floating_ai(name, display_name, hint))
        registry_results.append(_register_in_assistant_prompt(name, display_name, summary))

        # Phase 2 — extended one-click coverage (added 2026-05-04)
        # PLATFORM TOOLS bullet — different from page-context branch above
        registry_results.append(_register_in_floating_ai_platform_tools(name, display_name, summary))
        # Tester registries (5: PUBLIC_PAGES + 4 flow PAGES lists) — without
        # these the new page never gets served by the Tester or covered by
        # smoke / visual / mobile / performance flows.
        registry_results.append(_register_in_tester_public_pages(name, display_name))
        for flow_file in ("smoke.py", "visual.py", "mobile.py", "performance.py"):
            registry_results.append(_register_in_tester_flow(name, flow_file))
        # LIVE_PAGES validator scopes — without these the page is silently
        # skipped by schema-coverage and performance-budget scans.
        for validator_file in ("validate_schema.py", "validate_performance.py"):
            registry_results.append(_register_in_validator_live_pages(name, validator_file))
    else:
        registry_results.append(_register_in_non_tool_pages(f"{name}.html"))

    # ── Re-run auto-discovery + tester-coverage validators to verify ─────────
    # auto-discovery alone catches ~half of the registries above; running
    # tester-coverage in addition gives full confidence the wizard worked.
    verifier_results = {}
    for vname in ("validate_auto_discovery.py", "validate_tester_coverage.py"):
        try:
            proc = subprocess.run(
                [sys.executable, str(WORKHIVE_ROOT / vname)],
                cwd=str(WORKHIVE_ROOT),
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=30,
            )
            verifier_results[vname] = {
                "pass": proc.returncode == 0,
                "tail": (proc.stdout or "")[-400:],
            }
        except Exception as e:
            verifier_results[vname] = {"pass": False, "tail": f"verifier crashed: {e}"}

    return jsonify({
        "ok": True,
        "name": name,
        "classification": classification,
        "display_name": display_name,
        "files_created": [f"{name}.html"],
        "registries_updated": registry_results,
        "verifiers": verifier_results,
        # Back-compat: keep the original keys so the existing modal still works
        "auto_discovery_pass": verifier_results.get("validate_auto_discovery.py", {}).get("pass"),
        "auto_discovery_tail": verifier_results.get("validate_auto_discovery.py", {}).get("tail"),
    })


@app.route("/api/findings/add", methods=["POST"])
def api_findings_add():
    """Append a new bug to PRODUCTION_FIXES.md from the layer drill-down UI."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    category = (data.get("category") or "important").strip().lower()
    notes = (data.get("notes") or "").strip()
    source = (data.get("source") or "").strip()
    test_message = (data.get("test_message") or "").strip()

    if not title:
        return jsonify({"ok": False, "error": "title is required"}), 400

    # Build the markdown body
    parts = []
    if source:
        parts.append(f"**Source:** `{source}`")
    if test_message and test_message != title:
        parts.append(f"**Test message:** {test_message}")
    parts.append(f"**Found:** {datetime.now(timezone.utc).isoformat(timespec='seconds')} via WorkHive Tester")
    if notes:
        parts.append(notes)
    body = "\n\n".join(parts)

    result = _append_backlog_entry(category, title, body)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/health/backlog")
def api_health_backlog():
    """Returns categorized PRODUCTION_FIXES.md items for the backlog drill-down."""
    items = _parse_backlog_items()
    labels = {
        "critical":     "Critical",
        "important":    "Important",
        "nice_to_have": "Nice to have",
        "fixed":        "Fixed",
    }
    sections = [
        {"key": k, "label": labels[k], "items": items.get(k, [])}
        for k in ("critical", "important", "nice_to_have", "fixed")
    ]
    return jsonify({
        "sections": sections,
        "exists": FINDINGS_FILE.exists(),
        "file_path": str(FINDINGS_FILE),
    })


# ---------- Production findings + testing checklist (running backlogs) ----------

FINDINGS_FILE = WORKHIVE_ROOT / "PRODUCTION_FIXES.md"
TESTING_FILE = WORKHIVE_ROOT / "TESTING_CHECKLIST.md"


def _storage_key(label: str) -> str:
    """Stable JS-safe localStorage key (no backslashes, no quotes)."""
    safe = label.lower()
    return "wh_checks::" + "".join(ch if (ch.isalnum() or ch in "_-.") else "_" for ch in safe)


@app.route("/lineage")
def lineage_page():
    """Platform Lineage — interactive visual dependency map."""
    return render_template("lineage.html")


@app.route("/api/lineage/scan")
def api_lineage_scan():
    """Scan the codebase and return the full dependency graph as JSON."""
    try:
        from lib.lineage_scanner import scan_all
        data = scan_all()
        return jsonify({"ok": True, **data})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.route("/findings")
def findings_view():
    """Render PRODUCTION_FIXES.md as styled HTML using marked.js."""
    if not FINDINGS_FILE.exists():
        content = "# PRODUCTION_FIXES.md not found\n\nExpected at project root."
    else:
        content = FINDINGS_FILE.read_text(encoding="utf-8")
    return render_template(
        "findings.html",
        content=content,
        file_path=str(FINDINGS_FILE),
        storage_key=_storage_key("production_fixes"),
        page_title="Production Fixes — Running Backlog",
    )


@app.route("/token-stats")
def token_stats_view():
    """Claude token usage dashboard — shows per-action stats and model recommendations."""
    import sys
    sys.path.insert(0, str(WORKHIVE_ROOT))
    table, summary, recent, error, min_samples = [], {}, [], None, 15
    try:
        from tools.claude_token_tracker import get_all_stats, get_recent_calls
        from tools.claude_model_router import ModelRouter, MIN_SAMPLES
        min_samples = MIN_SAMPLES
        router  = ModelRouter()
        table   = router.routing_table()
        summary = router.summary()
        recent  = get_recent_calls(30)
    except Exception as exc:
        error = str(exc)
    return render_template(
        "token_stats.html",
        table=table,
        summary=summary,
        recent=recent,
        min_samples=min_samples,
        error=error,
    )


@app.route("/api/token-stats")
def api_token_stats():
    """JSON endpoint for token usage data."""
    import sys
    sys.path.insert(0, str(WORKHIVE_ROOT))
    try:
        from tools.claude_token_tracker import get_all_stats, get_recent_calls
        from tools.claude_model_router import ModelRouter
        router = ModelRouter()
        return jsonify({
            "summary":       router.summary(),
            "routing_table": router.routing_table(),
            "recent_calls":  get_recent_calls(50),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/token-stats/log", methods=["POST"])
def api_token_log():
    """
    Manually log a token usage record (from edge functions / external callers).

    POST JSON body:
        { action_type, model, input_tokens, output_tokens,
          cache_read?, cache_write?, duration_ms?, prompt_preview?, notes? }
    """
    import sys
    sys.path.insert(0, str(WORKHIVE_ROOT))
    data = request.get_json(force=True) or {}
    required = {"action_type", "model", "input_tokens", "output_tokens"}
    missing = required - set(data.keys())
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400
    try:
        from tools.claude_token_tracker import TrackedClient
        TrackedClient().log_raw(
            action_type    = data["action_type"],
            model          = data["model"],
            input_tokens   = int(data["input_tokens"]),
            output_tokens  = int(data["output_tokens"]),
            cache_read     = int(data.get("cache_read",  0)),
            cache_write    = int(data.get("cache_write", 0)),
            duration_ms    = int(data.get("duration_ms", 0)),
            prompt_preview = data.get("prompt_preview", ""),
            notes          = data.get("notes"),
        )
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/testing")
def testing_view():
    """Render TESTING_CHECKLIST.md as styled HTML using marked.js."""
    if not TESTING_FILE.exists():
        content = "# TESTING_CHECKLIST.md not found\n\nExpected at project root."
    else:
        content = TESTING_FILE.read_text(encoding="utf-8")
    return render_template(
        "findings.html",
        content=content,
        file_path=str(TESTING_FILE),
        storage_key=_storage_key("testing_checklist"),
        page_title="Testing Checklist — Pre-Launch",
    )


# ---------- Absolute-path passthroughs ----------
# WorkHive HTML pages reference some files at absolute paths (`/sw.js`, `/manifest.json`)
# which would normally hit our proxy. Serve them from the project root so the test
# environment matches what the user sees in production.

@app.route("/sw.js")
def sw_js():
    f = WORKHIVE_ROOT / "sw.js"
    if not f.exists():
        abort(404)
    text = f.read_text(encoding="utf-8")
    return Response(_rewrite(text), mimetype="application/javascript")


@app.route("/manifest.json")
def manifest_json():
    f = WORKHIVE_ROOT / "manifest.json"
    if not f.exists():
        abort(404)
    return send_from_directory(WORKHIVE_ROOT, "manifest.json")


@app.route("/brand_assets/<path:filename>")
def brand_assets(filename):
    """Serve brand assets (logos, icons) referenced from manifest.json at the
    site root. Without this the manifest icon 404s and DevTools complains."""
    if ".." in filename or filename.startswith("/"):
        abort(404)
    folder = WORKHIVE_ROOT / "brand_assets"
    if not (folder / filename).exists():
        abort(404)
    return send_from_directory(folder, filename)


# ---------- WorkHive proxy routes ----------

def _rewrite(content: str) -> str:
    return content.replace(CLOUD_URL, LOCAL_URL).replace(CLOUD_KEY, LOCAL_KEY)


@app.route("/workhive/")
def workhive_index():
    """Lists every page available in test mode."""
    return render_template("workhive_index.html", pages=PUBLIC_PAGES, supabase_url=LOCAL_URL)


@app.route("/workhive/<path:filename>")
def workhive_file(filename):
    # Block path traversal
    if ".." in filename or filename.startswith("/"):
        abort(404)

    full = (WORKHIVE_ROOT / filename).resolve()
    try:
        full.relative_to(WORKHIVE_ROOT)
    except ValueError:
        abort(404)

    if not full.exists() or not full.is_file():
        abort(404)

    # Block backups, test variants, internal seeder folder, node_modules
    parts = full.relative_to(WORKHIVE_ROOT).parts
    if any(p in {"node_modules", "test-data-seeder", ".git", "supabase"} for p in parts):
        abort(404)
    if filename.endswith(".backup.html") or filename.endswith(".backup2.html") or "-test." in filename:
        abort(404)

    suffix = full.suffix.lower()
    if suffix in {".html", ".js", ".mjs"}:
        text = full.read_text(encoding="utf-8", errors="ignore")
        rewritten = _rewrite(text)
        mime = "text/html; charset=utf-8" if suffix == ".html" else "application/javascript; charset=utf-8"
        resp = Response(rewritten, mimetype=mime)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Static assets — let Flask serve directly with proper MIME
    return send_from_directory(WORKHIVE_ROOT, filename)


# ── Phase 1: CMMS Integration Tester ─────────────────────────────────────────
# Generates dual-state CMMS datasets and exports them as CSV for Tier 1 testing.
# The generated dataset lives in CMMS_STATE for the lifetime of the Flask process.

import csv
import io as _io

CMMS_STATE = {
    "dataset":      None,   # CMMSDataset instance
    "summary":      None,
    "generated_at": None,
}


def _cmms_to_csv_bytes(rows: list) -> bytes:
    """Serialize a list of flat dicts to UTF-8 CSV bytes."""
    if not rows:
        return b""
    buf = _io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    # utf-8-sig adds the BOM Excel needs to identify UTF-8 encoding.
    # Without it, Excel on Windows reads °C as Â°C (Windows-1252 misread).
    return buf.getvalue().encode("utf-8-sig")


@app.route("/api/cmms/generate", methods=["POST"])
def api_cmms_generate():
    """Generate a new CMMS dataset and store it in CMMS_STATE."""
    from seeders.cmms import generate_dataset
    data = request.get_json(silent=True) or {}
    industry  = (data.get("industry")  or "food_processing").strip()
    size      = (data.get("size")      or "medium").strip()
    cmms_type = (data.get("cmms_type") or "sap_pm").strip()
    seed_raw  = data.get("seed")
    seed      = int(seed_raw) if seed_raw is not None else None

    try:
        ds = generate_dataset(industry=industry, size=size, cmms_type=cmms_type, seed=seed)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    CMMS_STATE["dataset"]      = ds
    CMMS_STATE["summary"]      = ds.summary()
    CMMS_STATE["generated_at"] = datetime.now(timezone.utc).isoformat()

    overdue   = sum(1 for p in ds.expected_pm        if p.get("is_overdue"))
    low_stock = sum(1 for i in ds.expected_inventory if i.get("is_low_stock"))
    breakdown_machines = {
        e["machine"] for e in ds.expected_logbook
        if e.get("maintenance_type") == "Breakdown / Corrective"
    }

    return jsonify({
        "ok":           True,
        "summary":      CMMS_STATE["summary"],
        "generated_at": CMMS_STATE["generated_at"],
        "patterns": {
            "overdue_pm":    overdue,
            "low_stock":     low_stock,
            "repeat_assets": len(breakdown_machines),
        },
    })


@app.route("/api/cmms/status")
def api_cmms_status():
    """Return the current dataset summary (or null if none generated yet)."""
    if CMMS_STATE["dataset"] is None:
        return jsonify({"ok": True, "dataset": None})
    return jsonify({
        "ok":           True,
        "dataset":      CMMS_STATE["summary"],
        "generated_at": CMMS_STATE["generated_at"],
    })


@app.route("/api/cmms/export-csv/<entity>")
def api_cmms_export_csv(entity):
    """Download CMMS-format CSV (import direction: CMMS -> WorkHive).

    entity: work_orders | assets | pm_schedules | inventory
    """
    ds = CMMS_STATE.get("dataset")
    if ds is None:
        return jsonify({"error": "No dataset generated yet. POST /api/cmms/generate first."}), 400

    entity_map = {
        "work_orders":  ds.work_orders,
        "assets":       ds.assets,
        "pm_schedules": ds.pm_schedules,
        "inventory":    ds.inventory,
    }
    if entity not in entity_map:
        return jsonify({"error": "Unknown entity. Use: " + ", ".join(entity_map)}), 400

    rows = entity_map[entity]
    if not rows:
        return jsonify({"error": "No " + entity + " in current dataset."}), 404

    s = CMMS_STATE["summary"]
    filename = (
        "cmms_" + s["cmms_type"] + "_" + entity
        + "_" + s["industry"].lower().replace(" ", "_")
        + "_" + s["size"] + ".csv"
    )
    return Response(
        _cmms_to_csv_bytes(rows),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="' + filename + '"'},
    )


@app.route("/api/cmms/export-csv/wh-to-sap/<entity>")
def api_cmms_export_wh_to_sap(entity):
    """Download WorkHive->CMMS format CSV (export direction: WorkHive -> CMMS).

    entity: work_orders | inventory
    Simulates what WorkHive pushes back to the CMMS after field workers act.
    """
    ds = CMMS_STATE.get("dataset")
    if ds is None:
        return jsonify({"error": "No dataset generated yet."}), 400

    ext_id_key = (
        "AUFNR"   if ds.cmms_type == "sap_pm"
        else "WONUM" if ds.cmms_type == "maximo"
        else "work_order_no"
    )
    part_key = (
        "MATNR"   if ds.cmms_type == "sap_pm"
        else "ITEMNUM" if ds.cmms_type == "maximo"
        else "part_number"
    )

    if entity == "work_orders":
        rows = [
            {
                ext_id_key:        e["_external_id"],
                "WH_STATUS":       e["status"],
                "WH_ACTUAL_HOURS": e.get("downtime_hours", 0),
                "WH_CLOSED_AT":    e.get("closed_at", ""),
                "WH_ACTION":       e.get("action", ""),
                "WH_NOTES":        "Completed via WorkHive. Root cause: " + e.get("root_cause", ""),
            }
            for e in ds.expected_logbook
            if e.get("status") == "Closed"
        ]
    elif entity == "inventory":
        rows = [
            {
                part_key:               e["_external_id"],
                "WH_DESCRIPTION":       e.get("name", ""),
                "WH_QTY_ON_HAND":       e.get("qty_on_hand", 0),
                "WH_REORDER_POINT":     e.get("reorder_point", 0),
                "WH_LOW_STOCK":         "YES" if e.get("is_low_stock") else "NO",
            }
            for e in ds.expected_inventory
        ]
    else:
        return jsonify({"error": "entity must be 'work_orders' or 'inventory'"}), 400

    if not rows:
        return jsonify({"error": "No exportable " + entity + " data."}), 404

    s = CMMS_STATE["summary"]
    filename = (
        "workhive_to_" + s["cmms_type"] + "_" + entity
        + "_" + s["industry"].lower().replace(" ", "_") + ".csv"
    )
    return Response(
        _cmms_to_csv_bytes(rows),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="' + filename + '"'},
    )


@app.route("/api/cmms/send-webhook", methods=["POST"])
def api_cmms_send_webhook():
    """Send webhook event(s) from the mock CMMS to a target URL.

    Body params:
      event_type  -- work_order.created | work_order.updated |
                     work_order.completed | pm.overdue | asset.updated
      count       -- number of events to send (default 1)
      target_url  -- where to POST events (default: local mock webhook target)
      mixed       -- if true, cycle through all 5 event types instead of one
    """
    import requests as _req
    from seeders.cmms_webhook import generate_event, generate_mixed_batch, EVENT_TYPES

    ds = CMMS_STATE.get("dataset")
    if ds is None:
        return jsonify({"error": "Generate a CMMS dataset first."}), 400

    data       = request.get_json(silent=True) or {}
    event_type = data.get("event_type", "work_order.created")
    count      = min(int(data.get("count", 1)), 100)
    target_url = data.get("target_url") or "http://127.0.0.1:5000/mock/webhook-target/receive"
    mixed      = bool(data.get("mixed", False))

    if event_type not in EVENT_TYPES and not mixed:
        return jsonify({"error": f"Unknown event_type. Use: {EVENT_TYPES}"}), 400

    if mixed:
        from seeders.cmms_webhook import generate_mixed_batch
        events = generate_mixed_batch(ds, count=count)
    else:
        events = [generate_event(ds, event_type, index=i) for i in range(count)]
        events = [e for e in events if e is not None]

    sign     = bool(data.get("sign", False))
    secret   = data.get("secret", "test-webhook-secret-workhive-2026")

    results = []
    for evt in events:
        try:
            import json as _json, hashlib as _hs, hmac as _hm, time as _time
            body_str = _json.dumps(evt)
            headers  = {"Content-Type": "application/json"}
            if sign:
                ts  = str(int(_time.time()))
                sig = _hm.new(secret.encode(), f"{ts}.{body_str}".encode(), _hs.sha256).hexdigest()
                headers["X-CMMS-Signature"] = f"sha256={sig}"
                headers["X-CMMS-Timestamp"] = ts
            resp = _req.post(target_url, data=body_str, headers=headers, timeout=10)
            results.append({"event": evt["event"], "status": resp.status_code, "ok": resp.ok})
        except Exception as e:
            results.append({"event": evt.get("event", "?"), "status": 0, "ok": False,
                            "error": str(e)})

    sent_ok = sum(1 for r in results if r["ok"])
    return jsonify({
        "ok":        True,
        "target":    target_url,
        "sent":      len(results),
        "delivered": sent_ok,
        "failed":    len(results) - sent_ok,
        "results":   results,
    })


@app.route("/api/cmms/seed-client-hive", methods=["POST"])
def api_cmms_seed_client_hive():
    """Create a full client hive from CMMS data and populate all WorkHive tables.

    Runs as a background job (can take 30-60s for medium/large datasets).
    Body: { industry, size, cmms_type, seed (optional) }
    """
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409

    data      = request.get_json(silent=True) or {}
    industry  = (data.get("industry")  or "food_processing").strip()
    size      = (data.get("size")      or "medium").strip()
    cmms_type = (data.get("cmms_type") or "sap_pm").strip()
    seed_raw  = data.get("seed")
    seed      = int(seed_raw) if seed_raw is not None else None

    def run(client, log):
        from seeders.client_hive import seed_client_hive
        result = seed_client_hive(client, log,
                                  industry=industry, size=size,
                                  cmms_type=cmms_type, seed=seed)
        # Store dataset so tier tests work immediately
        from app import CMMS_STATE
        # re-generate dataset for CMMS_STATE (bridge consumed it already)
        from seeders.cmms import generate_dataset
        ds = generate_dataset(industry=industry, size=size,
                              cmms_type=cmms_type, seed=result["dataset_summary"]["seed"])
        CMMS_STATE["dataset"]      = ds
        CMMS_STATE["summary"]      = ds.summary()
        CMMS_STATE["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result

    _run_job("seed_client_hive", run)
    return jsonify({"started": True})


@app.route("/api/cmms/seed-integration-config", methods=["POST"])
def api_cmms_seed_integration_config():
    """Seed integration_configs + api_keys for an existing hive.

    Body: { hive_id (optional — defaults to first hive), cmms_type (optional) }
    Use this when you already have a seeded hive and just want to attach a
    CMMS Live Sync config + test API key so integrations.html has data.
    """
    from seeders.cmms_config_seeder import seed_integration_config

    data      = request.get_json(silent=True) or {}
    cmms_type = (data.get("cmms_type") or "sap_pm").strip()
    hive_id   = data.get("hive_id")

    try:
        client = get_client()

        if not hive_id:
            # Default to the first hive in the DB
            res = client.table("hives").select("id").limit(1).execute()
            if not res.data:
                return jsonify({"error": "No hives found — seed hives first."}), 400
            hive_id = res.data[0]["id"]

        result = seed_integration_config(client, hive_id, cmms_type=cmms_type,
                                         log=_log_to_state)
        return jsonify({"ok": True, "hive_id": hive_id, **result})
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/cmms/demo", methods=["POST"])
def api_cmms_demo():
    """Generate a dataset and compute the intelligence report synchronously.

    Also stores the dataset in CMMS_STATE so tier tests can run against it.
    Body: { industry, size, cmms_type, seed (optional) }
    """
    from seeders.cmms import generate_dataset
    from seeders.cmms_demo import compute_demo_report

    data      = request.get_json(silent=True) or {}
    industry  = (data.get("industry")  or "food_processing").strip()
    size      = (data.get("size")      or "medium").strip()
    cmms_type = (data.get("cmms_type") or "sap_pm").strip()
    seed_raw  = data.get("seed")
    seed      = int(seed_raw) if seed_raw is not None else None

    try:
        ds     = generate_dataset(industry=industry, size=size, cmms_type=cmms_type, seed=seed)
        report = compute_demo_report(ds)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    # Store so tier test buttons work immediately after demo
    CMMS_STATE["dataset"]      = ds
    CMMS_STATE["summary"]      = ds.summary()
    CMMS_STATE["generated_at"] = datetime.now(timezone.utc).isoformat()

    return jsonify({"ok": True, "report": report, "summary": CMMS_STATE["summary"]})


@app.route("/api/cmms/tier3-test", methods=["POST"])
def api_cmms_tier3_test():
    """Run all 5 Tier 3 tests (real-time loop, ordering, no-drift, HMAC signature)."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    ds = CMMS_STATE.get("dataset")
    if ds is None:
        return jsonify({"error": "Generate a CMMS dataset first."}), 400

    def run(client, log):
        CMMS_STATE["dataset"]      = ds
        CMMS_STATE["summary"]      = ds.summary()
        CMMS_STATE["generated_at"] = datetime.now(timezone.utc).isoformat()
        from flows.cmms_tier3 import run_all
        return run_all(client, ds, log)

    _run_job("cmms_tier3_tests", run)
    return jsonify({"started": True})


@app.route("/api/cmms/tier2-test", methods=["POST"])
def api_cmms_tier2_test():
    """Run all 6 Tier 2 verification tests (HTTP sync against mock CMMS API)."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    ds = CMMS_STATE.get("dataset")
    if ds is None:
        return jsonify({"error": "Generate a CMMS dataset first."}), 400

    def run(client, log):
        # Re-populate CMMS_STATE so the mock API endpoints find the dataset
        # even if Flask hot-reloaded between generate and this test run.
        CMMS_STATE["dataset"]      = ds
        CMMS_STATE["summary"]      = ds.summary()
        CMMS_STATE["generated_at"] = datetime.now(timezone.utc).isoformat()
        from flows.cmms_tier2 import run_all
        return run_all(client, ds, log)

    _run_job("cmms_tier2_tests", run)
    return jsonify({"started": True})


@app.route("/api/cmms/tier1-test", methods=["POST"])
def api_cmms_tier1_test():
    """Run all 6 Tier 1 verification tests against the active dataset."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    ds = CMMS_STATE.get("dataset")
    if ds is None:
        return jsonify({"error": "Generate a CMMS dataset first."}), 400

    def run(client, log):
        from flows.cmms_tier1 import run_all
        return run_all(client, ds, log)

    _run_job("cmms_tier1_tests", run)
    return jsonify({"started": True})


if __name__ == "__main__":
    # threaded=True so concurrent requests don't queue (the index page +
    # /api/status polling were piling up on a single Flask thread and
    # hanging the dashboard at "Loading...").
    # use_reloader=False because the auto-reloader was occasionally hanging
    # mid-request after .py files in test-data-seeder/ were edited; the
    # cost of disabling it is that you have to restart manually after a code
    # change, which is fine for the Tester workflow.
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
        threaded=True,
        use_reloader=False,
    )
