import io
import random
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, jsonify, request, send_from_directory, Response, abort, redirect

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
from seeders.reset import reset_all

import subprocess
import sys

app = Flask(__name__)

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
}


def _log_to_state(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    JOB_STATE["log"].append(f"[{ts}] {msg}")
    print(msg)


def _run_job(name: str, fn):
    JOB_STATE.update({
        "running": True,
        "name": name,
        "log": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "result": None,
        "error": None,
    })

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
              "community_posts"]:
        try:
            res = client.table(t).select("id", count="exact").limit(1).execute()
            counts[t] = res.count or 0
        except Exception:
            counts[t] = "?"
    return counts


def get_test_logins():
    """Returns up to 6 sample workers (username + display_name) for the dashboard."""
    try:
        client = get_client()
        res = client.table("worker_profiles").select("username, display_name").limit(6).execute()
        return res.data or []
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
        "hives_workers": lambda c, log: seed_hives_and_workers(c, log),
    }

    needs_ctx_map = {
        "assets": seed_assets,
        "pm": seed_pm,
        "logbook": seed_logbook,
        "inventory": seed_inventory,
        "skill_matrix": seed_skill_matrix,
        "marketplace": seed_marketplace,
        "community": seed_community,
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
    proc = subprocess.Popen(
        [str(py), str(runner)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=str(Path(__file__).parent), bufsize=1,
        text=True, encoding="utf-8", errors="replace",
    )
    import re
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    last_summary = ""
    for line in proc.stdout:
        clean = ansi.sub("", line.rstrip())
        if clean:
            log(clean)
            if "Summary" in clean:
                last_summary = clean
    proc.wait()
    return {"summary": last_summary, "exit_code": proc.returncode}


@app.route("/api/run-tests", methods=["POST"])
def api_run_tests():
    """Runs the automated data-level test suite."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("run_tests", lambda c, log: _run_subprocess("run_tests.py", log))
    return jsonify({"started": True})


@app.route("/api/run-flows", methods=["POST"])
def api_run_flows():
    """Runs the Playwright UI flow suite (drives Chromium against the proxy)."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409
    _run_job("run_flows", lambda c, log: _run_subprocess("run_flows.py", log))
    return jsonify({"started": True})


@app.route("/api/run-gate", methods=["POST"])
def api_run_gate():
    """Runs the full release gate (pre-flight + reseed + static + data + UI)."""
    if JOB_STATE["running"]:
        return jsonify({"error": "another job is running"}), 409

    def _run(client, log):
        # release_gate.py lives at project root, one level above the seeder
        gate = WORKHIVE_ROOT / "release_gate.py"
        if not gate.exists():
            log(f"ERROR: release_gate.py not found at {gate}")
            return {"exit_code": 1}
        proc = subprocess.Popen(
            [sys.executable, str(gate)],
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

    _run_job("release_gate", _run)
    return jsonify({"started": True})


# ---------- Production findings + testing checklist (running backlogs) ----------

FINDINGS_FILE = WORKHIVE_ROOT / "PRODUCTION_FIXES.md"
TESTING_FILE = WORKHIVE_ROOT / "TESTING_CHECKLIST.md"


def _storage_key(label: str) -> str:
    """Stable JS-safe localStorage key (no backslashes, no quotes)."""
    safe = label.lower()
    return "wh_checks::" + "".join(ch if (ch.isalnum() or ch in "_-.") else "_" for ch in safe)


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


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
