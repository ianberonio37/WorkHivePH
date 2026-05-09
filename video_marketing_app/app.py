"""
WorkHive Video Marketing Dashboard - Flask backend
Run via video_marketing.bat or: python video_marketing_app/app.py
"""

from flask import Flask, jsonify, request, render_template, send_file
from pathlib import Path
from datetime import date
import sys, os, json, re, asyncio, requests, threading, time, uuid

# ── Path setup ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
os.chdir(ROOT)

# Pre-import supabase-py BEFORE inserting ROOT into sys.path.
# ROOT contains a supabase/ config folder which would shadow the installed
# supabase-py package once ROOT is at position 0.
try:
    import supabase as _sb  # noqa: F401
except ImportError:
    pass

sys.path.insert(0, str(ROOT))

def _load_env():
    for p in [ROOT / ".env", ROOT / "supabase/functions/.env"]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

from tools.video_idea_generator import ai_call, STATUSES
from tools.platform_intel import (
    build_prompt_context, compute_coverage, uncovered_features,
    all_features, get_feature_info, FEATURE_ECOSYSTEM, WORKHIVE_LOOP,
)

BACKLOG = ROOT / ".tmp/video_ideas_backlog.json"
SCRIPTS = ROOT / ".tmp/video_scripts"
VOICES  = ROOT / ".tmp/voice_files"

# Voice options (edge-tts, completely free). English voices are default since
# narration is plain simple English; Filipino voices kept for variety/testing.
VOICE_OPTIONS = {
    "james":   {"id": "en-PH-JamesNeural",     "label": "James (PH English Male)"},
    "rosa":    {"id": "en-PH-RosaNeural",      "label": "Rosa (PH English Female)"},
    "guy":     {"id": "en-US-GuyNeural",       "label": "Guy (US English Male, calm)"},
    "jenny":   {"id": "en-US-JennyNeural",     "label": "Jenny (US English Female, warm)"},
    "ryan":    {"id": "en-GB-RyanNeural",      "label": "Ryan (UK English Male, neutral)"},
    "angelo":  {"id": "fil-PH-AngeloNeural",   "label": "Angelo (Filipino Male)"},
    "blessica":{"id": "fil-PH-BlessicaNeural", "label": "Blessica (Filipino Female)"},
}

# ── Flask ─────────────────────────────────────────────────────────────────────

app = Flask(__name__, template_folder="templates")

# ── Backlog helpers ───────────────────────────────────────────────────────────

def load_backlog():
    if not BACKLOG.exists():
        return {"ideas": []}
    return json.loads(BACKLOG.read_text(encoding="utf-8"))


def save_backlog(data):
    BACKLOG.parent.mkdir(parents=True, exist_ok=True)
    BACKLOG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def next_id(data):
    if not data["ideas"]:
        return "idea_001"
    nums = [
        int(re.search(r"\d+", i["id"]).group())
        for i in data["ideas"]
        if re.search(r"\d+", i["id"])
    ]
    return f"idea_{max(nums) + 1:03d}"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/favicon.ico")
def favicon():
    return "", 204   # no favicon — silence the 404


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ideas")
def get_ideas():
    return jsonify(load_backlog()["ideas"])


@app.route("/api/demo-features")
def demo_features():
    """Return the list of features that have an auto-record demo sequence."""
    try:
        from tools.ui_recorder import DEMOS
        # Human-readable keys: start with uppercase (not snake_case aliases)
        features = [k for k in DEMOS.keys() if k[0].isupper()]
        return jsonify({"features": features})
    except Exception as exc:
        return jsonify({"features": [], "error": str(exc)})


@app.route("/api/platform-intel")
def platform_intel():
    data     = load_backlog()
    ideas    = data["ideas"]
    coverage = compute_coverage(ideas)
    uncov    = uncovered_features(ideas)

    return jsonify({
        "features":  all_features(),
        "coverage":  coverage,
        "uncovered": uncov,
        "ecosystem": {
            k: {
                "connects_to": v["connects_to"],
                "loop_role":   v["loop_role"],
                "audience":    v["audience"],
            }
            for k, v in FEATURE_ECOSYSTEM.items()
        },
    })


@app.route("/api/coverage")
def coverage_api():
    data  = load_backlog()
    ideas = data["ideas"]
    cov   = compute_coverage(ideas)
    return jsonify({
        "coverage":  cov,
        "uncovered": uncovered_features(ideas),
        "total_features": len(FEATURE_ECOSYSTEM),
        "covered_count":  sum(1 for v in cov.values() if v["status"] != "uncovered"),
    })


@app.route("/api/ideas/generate", methods=["POST"])
def generate_ideas():
    n       = request.json.get("n", 5)
    feature = request.json.get("feature")  # optional: target a specific feature
    data    = load_backlog()
    existing = [i["title"] for i in data["ideas"]]
    avoid = (
        "\n\nALREADY IN BACKLOG (do not repeat these):\n"
        + "\n".join(f"- {t}" for t in existing)
        if existing else ""
    )

    # Build live platform context (injects real Supabase data + coverage gaps)
    platform_ctx = build_prompt_context(data["ideas"])

    # ── Feature assignment: pre-bind each idea slot to a feature so the AI
    #    can't keep regenerating ideas about the same well-known features.
    #    Round-robin through uncovered first, then least-covered, never repeats
    #    within a single generation batch.
    import random as _r
    feature_constraint = ""
    if feature and feature in FEATURE_ECOSYSTEM:
        # Explicit override: all N ideas use this feature
        feat_info = get_feature_info(feature)
        connects  = ", ".join(feat_info.get("connects_to", [])[:3])
        feature_constraint = (
            f"\n\nFORCED FEATURE: ALL {n} ideas must focus on '{feature}'.\n"
            f"Loop role: {feat_info.get('loop_role','')}\n"
            f"Connected features to mention in Ripple step: {connects}\n"
        )
    else:
        # Auto-distribute: prioritise uncovered, never repeat in one batch
        uncov_list = uncovered_features(data["ideas"])
        cov_map    = compute_coverage(data["ideas"])
        # Sort covered features by current coverage count (least-covered first)
        covered_sorted = sorted(
            [f for f in FEATURE_ECOSYSTEM if cov_map[f]["status"] != "uncovered"],
            key=lambda f: len(cov_map[f]["idea_ids"])
        )

        _r.shuffle(uncov_list)
        assignment_pool = uncov_list + covered_sorted   # uncovered first, then least-covered
        assigned        = assignment_pool[:n] if len(assignment_pool) >= n else assignment_pool

        # If we still don't have n features (very small ecosystem), repeat the pool
        while len(assigned) < n:
            assigned.append(_r.choice(list(FEATURE_ECOSYSTEM.keys())))

        # Build per-slot assignment block — gives AI no wiggle room
        slots = []
        for i, feat in enumerate(assigned, 1):
            info     = get_feature_info(feat)
            connects = ", ".join(info.get("connects_to", [])[:3])
            slots.append(
                f"  IDEA {i} — Feature: '{feat}'\n"
                f"           Loop role: {info.get('loop_role','')}\n"
                f"           Ripple options: {connects}\n"
                f"           Audience: {', '.join(info.get('audience',['Field Technician']))}"
            )
        feature_constraint = (
            f"\n\nFEATURE ASSIGNMENTS (NON-NEGOTIABLE — every idea MUST target its assigned feature):\n"
            + "\n".join(slots)
            + "\n\nDo NOT generate two ideas about the same feature in this batch. "
              "Do NOT substitute a feature with a similar-sounding one. "
              "If an assigned feature is unfamiliar, use its loop role to invent a fresh angle.\n"
        )

    prompt = f"""{platform_ctx}

You are a creative director for viral industrial content.
Generate {n} DISTINCT WorkHive advertisement video ideas.{avoid}{feature_constraint}

Rules:
- Each idea targets ONE pain point only, maps to its ASSIGNED WorkHive feature (see above)
- Hooks must feel real, not like marketing copy
- Mix video types across the batch (storytelling, testimonial, comparison, educational, emotional)
- At least one idea targets field technicians, one targets supervisors or managers
- ALL copy (title, hook, problem) must be in PLAIN SIMPLE ENGLISH — no Tagalog, no Taglish, no code-switching, no Filipino slang
- Use short, common words. Short sentences. Anyone reading at high-school English level should follow it.
- The 9 newer features (Analytics & OEE Dashboard, Predictive Analytics, Asset Brain, Shift Brain, Achievements, Alert Hub, PH Industry Intelligence, CMMS Integrations, Project Manager) are revolutionary platform capabilities — frame them with the energy of a breakthrough, not a routine feature.

Return ONLY a valid JSON array of {n} objects in the SAME ORDER as the assignments above, no markdown fences, no explanation:
[
  {{
    "title": "short punchy title (4-7 words, plain English)",
    "hook": "opening line in plain simple English any plant worker would immediately feel (1-2 sentences, conversational)",
    "problem": "the pain point in plain English (1 sentence)",
    "solution_feature": "the EXACT assigned feature name for this slot",
    "audience": "who this targets (e.g. Plant Manager, Field Technician, Supervisor, Engineer)",
    "emotion": "primary emotion triggered (e.g. Fear of downtime, Pride, Relief, Ambition)",
    "duration": "60s",
    "video_type": "storytelling | testimonial | comparison | educational | emotional"
  }}
]"""

    try:
        raw   = ai_call(prompt)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return jsonify({"success": False, "error": "AI did not return JSON"}), 500

        ideas_raw = json.loads(match.group())
        added = []
        for slot_idx, idea in enumerate(ideas_raw):
            idea_id  = next_id(data)
            # Enforce the slot assignment: AI sometimes drifts off and returns a
            # similar-but-different feature. Override with the assigned one.
            ai_feature = idea.get("solution_feature", "")
            if not feature and slot_idx < len(assigned):
                authoritative_feature = assigned[slot_idx]
                if ai_feature != authoritative_feature:
                    print(f"  [generate] slot {slot_idx+1}: AI returned '{ai_feature}', "
                          f"forcing assigned '{authoritative_feature}'")
                solution_feature = authoritative_feature
            else:
                solution_feature = ai_feature

            new_idea = {
                "id":               idea_id,
                "title":            idea.get("title", "Untitled"),
                "hook":             idea.get("hook", ""),
                "problem":          idea.get("problem", ""),
                "solution_feature": solution_feature,
                "audience":         idea.get("audience", ""),
                "emotion":          idea.get("emotion", ""),
                "duration":         idea.get("duration", "60s"),
                "video_type":       idea.get("video_type", "storytelling"),
                "status":           "idea",
                "created_at":       str(date.today()),
                "script_file":      None,
            }
            data["ideas"].append(new_idea)
            added.append(new_idea)

        save_backlog(data)
        return jsonify({"success": True, "added": added})

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/ideas/<idea_id>/script", methods=["POST"])
def generate_script(idea_id):
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        return jsonify({"success": False, "error": "Idea not found"}), 404

    SCRIPTS.mkdir(parents=True, exist_ok=True)
    safe  = re.sub(r"[^\w\s-]", "", idea["title"]).strip().lower()
    safe  = re.sub(r"[\s-]+", "_", safe)[:35]
    ofile = SCRIPTS / f"{idea_id}_{safe}.md"

    dur_secs     = idea["duration"].replace("s", "")
    platform_ctx = build_prompt_context(load_backlog()["ideas"])
    feat_info    = get_feature_info(idea.get("solution_feature", ""))
    ripple_hints = ", ".join(feat_info.get("connects_to", [])[:3])

    prompt = _build_script_prompt(idea, platform_ctx, ripple_hints, dur_secs)

    try:
        content = ai_call(prompt, high_quality=True)
        ofile.write_text(content, encoding="utf-8")

        for i in data["ideas"]:
            if i["id"] == idea_id:
                i["status"]      = "scripted"
                i["script_file"] = str(ofile)
        save_backlog(data)

        return jsonify({"success": True, "content": content, "file": str(ofile)})

    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/ideas/<idea_id>/script/content")
def get_script_content(idea_id):
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea or not idea.get("script_file"):
        return jsonify({"success": False, "error": "No script generated yet"})

    p = Path(idea["script_file"])
    if not p.exists():
        return jsonify({"success": False, "error": "Script file missing from disk"})

    return jsonify({"success": True, "content": p.read_text(encoding="utf-8")})


@app.route("/api/ideas/<idea_id>", methods=["DELETE"])
def delete_idea(idea_id):
    data = load_backlog()
    before = len(data["ideas"])
    data["ideas"] = [i for i in data["ideas"] if i["id"] != idea_id]
    if len(data["ideas"]) == before:
        # Idempotent: already gone is success from the caller's point of view.
        return jsonify({"success": True, "already_gone": True})
    save_backlog(data)
    return jsonify({"success": True})


@app.route("/api/ideas/<idea_id>/status", methods=["PATCH"])
def update_status(idea_id):
    status = request.json.get("status")
    if status not in STATUSES:
        return jsonify({"success": False, "error": f"Invalid status: {status}"}), 400

    data = load_backlog()
    for idea in data["ideas"]:
        if idea["id"] == idea_id:
            idea["status"] = status
            save_backlog(data)
            return jsonify({"success": True, "idea": idea})

    return jsonify({"success": False, "error": "Idea not found"}), 404


# ── Video assembly (FFmpeg + Whisper) ────────────────────────────────────────

ASSEMBLED_DIR = ROOT / ".tmp/assembled_videos"


@app.route("/api/ideas/<idea_id>/assets")
def get_assets(idea_id):
    """Return which production assets are ready for this idea."""
    data    = load_backlog()
    idea    = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        return jsonify({"success": False, "error": "Idea not found"}), 404

    feature = idea.get("solution_feature", "")
    assets  = {}

    # Check narration files — return ALL generated voices, not just first
    from tools.video_assembler import VOICE_DIR, RECORDINGS_DIR, find_latest_recording
    generated_voices = []
    for vk in ["james", "rosa", "angelo", "blessica", "guy"]:
        p = VOICE_DIR / f"{idea_id}_{vk}.mp3"
        if p.exists():
            generated_voices.append({"key": vk, "file": str(p)})
    assets["narration"] = {
        "ready":   bool(generated_voices),
        "voices":  generated_voices,
        "default": generated_voices[-1]["key"] if generated_voices else None,
    }

    # Check UI recordings — return all available, newest first
    from tools.video_assembler import list_recordings
    all_recs = list_recordings(feature)
    if all_recs:
        assets["recording"] = {
            "ready":   True,
            "file":    str(all_recs[0]),
            "name":    all_recs[0].name,
            "size_kb": all_recs[0].stat().st_size // 1024,
            "all":     [{"name": r.name, "file": str(r), "size_kb": r.stat().st_size // 1024}
                        for r in all_recs],
        }
    else:
        assets["recording"] = {"ready": False}

    # Check assembled video
    assembled = sorted(ASSEMBLED_DIR.glob(f"{idea_id}_*.mp4"),
                       key=lambda f: f.stat().st_mtime) if ASSEMBLED_DIR.exists() else []
    assets["assembled"] = {
        "file":     str(assembled[-1]) if assembled else None,
        "ready":    bool(assembled),
        "download": f"/api/assembled/{assembled[-1].name}" if assembled else None,
    }

    return jsonify({"success": True, "assets": assets, "feature": feature})


@app.route("/api/ideas/<idea_id>/assemble", methods=["POST"])
def assemble_video(idea_id):
    body           = request.get_json(silent=True) or {}
    voice_key      = body.get("voice", "james")
    music_file     = body.get("music_file")
    scene_file     = body.get("scene_file")
    hook_file      = body.get("hook_file")
    recording_file = body.get("recording_file")   # user-chosen recording override
    captions       = body.get("captions", True)

    try:
        from tools.video_assembler import assemble
        from pathlib import Path as _Path

        result = assemble(
            idea_id        = idea_id,
            voice_key      = voice_key,
            music_path     = _Path(music_file)     if music_file     else None,
            scene_clip     = _Path(scene_file)     if scene_file     else None,
            hook_clip      = _Path(hook_file)      if hook_file      else None,
            recording_file = _Path(recording_file) if recording_file else None,
            captions       = captions,
        )
        size_mb = round(result.stat().st_size / 1_000_000, 1)
        return jsonify({
            "success":    True,
            "file":       str(result),
            "size_mb":    size_mb,
            "download":   f"/api/assembled/{result.name}",
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/assembled/<filename>")
def serve_assembled(filename):
    ASSEMBLED_DIR.mkdir(parents=True, exist_ok=True)
    p = ASSEMBLED_DIR / filename
    if not p.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(str(p), mimetype="video/mp4", as_attachment=True,
                     download_name=filename)


# ── Voice generation (Edge TTS -- completely free) ────────────────────────────

def _extract_narration(script_content: str) -> str:
    """Pull the paste-ready narration block out of a generated script."""
    match = re.search(
        r"ElevenLabs Narration.*?\(paste-ready\)\s*\n([\s\S]*?)(?=\n---|\n##|$)",
        script_content, re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    # Fallback: collect all NARRATION lines
    lines = re.findall(r'\*\*NARRATION:\*\*\s*["“]?([^"”\n]+)["”]?', script_content)
    return " ".join(lines).strip()


def _extract_music_direction(script_content: str) -> str:
    match = re.search(r"Music Direction\s*\n([\s\S]*?)(?=\n---|\n##|$)", script_content, re.IGNORECASE)
    return match.group(1).strip() if match else ""


async def _generate_tts(text: str, voice_id: str, out_path: Path):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice_id)
    await communicate.save(str(out_path))


@app.route("/api/voices")
def get_voices():
    return jsonify(VOICE_OPTIONS)


@app.route("/api/ideas/<idea_id>/voice", methods=["POST"])
def generate_voice(idea_id):
    body      = request.get_json(silent=True) or {}
    voice_key = body.get("voice", "james")
    voice_id  = VOICE_OPTIONS.get(voice_key, VOICE_OPTIONS["james"])["id"]

    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea or not idea.get("script_file"):
        return jsonify({"success": False, "error": "Generate a script first"}), 400

    script_path = Path(idea["script_file"])
    if not script_path.exists():
        return jsonify({"success": False, "error": "Script file missing"}), 400

    content   = script_path.read_text(encoding="utf-8")
    narration = _extract_narration(content)
    if not narration:
        return jsonify({"success": False, "error": "Could not extract narration from script"}), 400

    VOICES.mkdir(parents=True, exist_ok=True)
    out_file = VOICES / f"{idea_id}_{voice_key}.mp3"

    print(f"  [voice] {idea_id} -> {voice_key} ({voice_id}), {len(narration)} chars")
    try:
        # Use a fresh event loop per request — avoids 'event loop already running'
        # issues on Windows when Auto-Produce is also running in a background thread.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                asyncio.wait_for(_generate_tts(narration, voice_id, out_file), timeout=120)
            )
        finally:
            loop.close()

        if not out_file.exists() or out_file.stat().st_size < 1000:
            raise RuntimeError("Edge TTS returned no audio (file missing or empty)")

        size_kb = out_file.stat().st_size // 1024
        print(f"  [voice] OK: {out_file.name} ({size_kb} KB)")
        return jsonify({
            "success":    True,
            "file":       str(out_file),
            "download":   f"/api/ideas/{idea_id}/voice/download?voice={voice_key}",
            "narration":  narration,
            "char_count": len(narration),
        })
    except asyncio.TimeoutError:
        print(f"  [voice] TIMEOUT after 120s")
        return jsonify({
            "success": False,
            "error":   "Edge TTS timed out after 120s — Microsoft service may be down. Try again, or pick a different voice.",
        }), 504
    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": f"{type(exc).__name__}: {exc}"}), 500


@app.route("/api/ideas/<idea_id>/voice/download")
def download_voice(idea_id):
    voice_key = request.args.get("voice", "james")
    out_file  = VOICES / f"{idea_id}_{voice_key}.mp3"
    if not out_file.exists():
        return jsonify({"error": "Generate voice first"}), 404
    return send_file(str(out_file), mimetype="audio/mpeg", as_attachment=True,
                     download_name=f"{idea_id}_narration_{voice_key}.mp3")


@app.route("/api/ideas/<idea_id>/voice/stream")
def stream_voice(idea_id):
    voice_key = request.args.get("voice", "james")
    out_file  = VOICES / f"{idea_id}_{voice_key}.mp3"
    if not out_file.exists():
        return jsonify({"error": "Generate voice first"}), 404
    return send_file(str(out_file), mimetype="audio/mpeg", as_attachment=False)


@app.route("/api/ideas/<idea_id>/scene/auto", methods=["POST"])
def auto_download_scene(idea_id):
    """Auto-download a matching stock video clip from Pexels."""
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        return jsonify({"success": False, "error": "Idea not found"}), 404

    PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
    if not PEXELS_KEY:
        return jsonify({
            "success": False,
            "error": "PEXELS_API_KEY not set",
            "needs_key": True,
        }), 400

    # Build search query from idea context.
    # Each feature has a LIST of related queries — we pick one randomly per
    # request so two ideas about the same feature don't recycle the same clips.
    feature = idea.get("solution_feature", "")
    queries_map = {
        "Engineering Design Calculator": [
            "engineer calculator industrial",
            "engineer technical drawing CAD",
            "industrial engineer designing",
            "engineer with blueprint factory",
        ],
        "Maintenance Logbook": [
            "factory maintenance worker",
            "industrial technician fixing machine",
            "engineer writing maintenance notes",
            "manufacturing plant repair",
            "worker inspection equipment",
        ],
        "PM Checklist": [
            "industrial checklist inspection",
            "technician preventive maintenance",
            "factory worker clipboard inspection",
            "manufacturing quality check",
        ],
        "Inventory Management": [
            "warehouse parts inventory",
            "industrial spare parts shelf",
            "factory storeroom worker",
            "warehouse barcode scanning",
        ],
        "Hive Dashboard": [
            "plant manager control room",
            "factory operations center",
            "industrial dashboard monitor",
            "supervisor reviewing data screens",
        ],
        "Shift Handover Report": [
            "factory workers shift change",
            "night shift to day shift",
            "industrial team meeting briefing",
            "supervisor handover documents",
        ],
        "AI Maintenance Assistant": [
            "engineer technology digital",
            "industrial AI machine learning",
            "factory worker tablet technology",
            "smart manufacturing screen",
        ],
        "Skill Matrix": [
            "industrial training workers",
            "factory apprentice learning",
            "technician hands-on training",
            "manufacturing skills certification",
        ],
        "Day Planner": [
            "engineer planning schedule",
            "factory supervisor calendar",
            "industrial work scheduling",
            "manager planning whiteboard",
        ],
        "Marketplace": [
            "industrial parts equipment",
            "factory supplier delivery",
            "warehouse forklift operation",
            "industrial spare components",
        ],
        "Community Forum": [
            "industrial workers team",
            "factory team discussion",
            "engineers collaborating",
            "manufacturing workers conversation",
        ],
        # New 2026-05
        "Analytics & OEE Dashboard": [
            "factory data dashboard analytics",
            "industrial KPI screen monitor",
            "manufacturing performance metrics",
            "engineer reviewing graphs",
        ],
        "Predictive Analytics": [
            "industrial machine learning prediction",
            "factory sensor monitoring",
            "predictive maintenance technology",
            "smart factory data analysis",
        ],
        "Asset Brain": [
            "industrial machinery hierarchy plant",
            "factory equipment overview",
            "engineer inspecting industrial pump",
            "manufacturing plant aerial",
        ],
        "Shift Brain": [
            "factory shift change supervisor briefing",
            "early morning factory worker",
            "industrial shift planning",
            "supervisor briefing team",
        ],
        "Achievements": [
            "factory worker pride craftsmanship",
            "industrial worker satisfaction",
            "engineer celebrating success",
            "manufacturing team accomplishment",
        ],
        "Alert Hub": [
            "control room alarm warning panel",
            "factory warning lights",
            "industrial alert dashboard",
            "supervisor responding to alarm",
        ],
        "PH Industry Intelligence": [
            "philippines factory benchmark report",
            "manufacturing industry data",
            "industrial benchmarking analysis",
            "factory performance comparison",
        ],
        "CMMS Integrations": [
            "industrial software integration data sync",
            "factory IT systems",
            "manufacturing connected systems",
            "industrial data flow technology",
        ],
        "Project Manager": [
            "factory shutdown overhaul project planning",
            "industrial project team meeting",
            "manufacturing capex planning",
            "engineer project Gantt chart",
        ],
    }
    queries = queries_map.get(feature, [
        "industrial factory worker",
        "manufacturing plant",
        "industrial engineer",
    ])

    import random
    # Mix idea_id into seed so the same idea always picks the same query slot
    # within a single request, but different ideas (and re-runs) get variety.
    rand = random.Random(f"{idea_id}_{int(time.time())}")
    query   = rand.choice(queries)
    page_no = rand.randint(1, 3)            # randomize Pexels page (1-3) for fresh results
    per_pg  = 15                            # fetch a wider pool to sample from

    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_KEY},
            params={
                "query":       query,
                "per_page":    per_pg,
                "page":        page_no,
                "orientation": "landscape",
            },
            timeout=10,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            # Fall back to page 1 if random page returned empty
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": PEXELS_KEY},
                params={"query": query, "per_page": per_pg, "page": 1, "orientation": "landscape"},
                timeout=10,
            )
            videos = resp.json().get("videos", [])
        if not videos:
            return jsonify({"success": False, "error": f"No Pexels videos found for: {query}"}), 404
        # Random sample from the wider pool — 3 different clips each call
        videos = rand.sample(videos, min(3, len(videos)))

        scenes_dir = ROOT / ".tmp/scene_clips"
        scenes_dir.mkdir(parents=True, exist_ok=True)

        def _best_file(video):
            files = sorted(video.get("video_files", []),
                           key=lambda f: f.get("width", 0), reverse=True)
            return next((f for f in files if f.get("width", 0) >= 1280), files[0]) if files else None

        # Download up to 3 clips
        downloaded = []
        credits    = []
        # videos is already a random sample of 3 from the pool (see above)
        for video in videos:
            hd = _best_file(video)
            if not hd:
                continue
            out = scenes_dir / f"{idea_id}_pexels_{video['id']}.mp4"
            print(f"  Downloading: {video.get('id')} ({hd.get('width')}x{hd.get('height')})")
            with requests.get(hd["link"], stream=True, timeout=60) as r:
                r.raise_for_status()
                out.write_bytes(r.content)
            downloaded.append(out)
            credits.append(video.get("user", {}).get("name", "Pexels"))

        if not downloaded:
            return jsonify({"success": False, "error": "No downloadable clips found"}), 404

        # Concatenate the clips into one file using FFmpeg
        from tools.video_assembler import _ffmpeg_exe, _run_ffmpeg
        import tempfile, pathlib

        if len(downloaded) == 1:
            final_clip = downloaded[0]
        else:
            tmp_dir    = pathlib.Path(tempfile.mkdtemp())
            # Normalise each clip to same resolution first
            norm_clips = []
            for i, clip in enumerate(downloaded):
                norm = tmp_dir / f"norm_{i}.mp4"
                _run_ffmpeg([
                    "-i", str(clip),
                    "-vf", "scale=1280:900:force_original_aspect_ratio=decrease,"
                           "pad=1280:900:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-an", str(norm),
                ], f"normalise clip {i+1}")
                norm_clips.append(norm)

            concat_list = tmp_dir / "concat.txt"
            concat_list.write_text(
                "".join(f"file '{c}'\n" for c in norm_clips), encoding="utf-8"
            )
            final_clip = scenes_dir / f"{idea_id}_pexels_combined.mp4"
            _run_ffmpeg([
                "-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-c", "copy", str(final_clip),
            ], "concatenate clips")

        size_mb = round(final_clip.stat().st_size / 1_000_000, 1)
        return jsonify({
            "success":    True,
            "file":       str(final_clip),
            "filename":   final_clip.name,
            "size_mb":    size_mb,
            "clip_count": len(downloaded),
            "query":      query,
            "credit":     ", ".join(set(credits)),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/ideas/<idea_id>/music/auto", methods=["POST"])
def auto_download_music(idea_id):
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea or not idea.get("script_file"):
        return jsonify({"success": False, "error": "Generate a script first"}), 400

    script_path = Path(idea["script_file"])
    if not script_path.exists():
        return jsonify({"success": False, "error": "Script file missing"}), 400

    content = script_path.read_text(encoding="utf-8")

    try:
        from tools.music_finder import find_music_for_script
        music_path = find_music_for_script(content)
        return jsonify({
            "success":   True,
            "file":      str(music_path),
            "filename":  music_path.name,
            "size_kb":   music_path.stat().st_size // 1024,
        })
    except RuntimeError as exc:
        msg = str(exc)
        if "JAMENDO_CLIENT_ID" in msg:
            return jsonify({"success": False, "error": msg, "needs_key": True}), 400
        return jsonify({"success": False, "error": msg}), 500
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/ideas/<idea_id>/suno-prompt")
def get_suno_prompt(idea_id):
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea or not idea.get("script_file"):
        return jsonify({"success": False, "error": "No script yet"}), 400

    script_path = Path(idea["script_file"])
    if not script_path.exists():
        return jsonify({"success": False, "error": "Script file missing"}), 400

    content   = script_path.read_text(encoding="utf-8")
    music_dir = _extract_music_direction(content)

    # Build a Suno-formatted prompt from the music direction
    mood_match  = re.search(r"Mood:\*\*\s*(.+)", music_dir)
    style_match = re.search(r"Style:\*\*\s*(.+)", music_dir)
    bpm_match   = re.search(r"BPM:\*\*\s*(.+)", music_dir)

    mood  = mood_match.group(1).strip()  if mood_match  else "quiet urgency"
    style = style_match.group(1).strip() if style_match else "lo-fi ambient"
    bpm   = bpm_match.group(1).strip()   if bpm_match   else "80"

    suno_prompt = f"[{style}, {bpm}bpm, instrumental] {mood}. Industrial workplace background. No lyrics. 60 seconds."
    return jsonify({"success": True, "prompt": suno_prompt, "raw_direction": music_dir})


# ── UI Auto-Recording (Playwright) ───────────────────────────────────────────

@app.route("/api/ideas/<idea_id>/record", methods=["POST"])
def record_ui_demo(idea_id):
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        return jsonify({"success": False, "error": "Idea not found"}), 404

    feature = idea.get("solution_feature", "")

    try:
        from tools.ui_recorder import record, DEMOS
        if feature not in DEMOS:
            return jsonify({
                "success": False,
                "error":   f"No demo sequence for '{feature}' yet. Available: {[k for k in DEMOS if '_' not in k]}"
            }), 400

        body     = request.get_json(silent=True) or {}
        headless = body.get("headless", False)

        video_path = record(feature, headless=headless)

        if not video_path or not video_path.exists():
            return jsonify({"success": False, "error": "Recording failed — no video file produced"}), 500

        return jsonify({
            "success":    True,
            "feature":    feature,
            "video_file": str(video_path),
            "size_kb":    video_path.stat().st_size // 1024,
            "download":   f"/api/recordings/{video_path.name}",
        })

    except Exception as exc:
        import traceback
        traceback.print_exc()          # shows full error in the Flask terminal
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/ideas/<idea_id>/record-manual", methods=["POST"])
def record_manual(idea_id):
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        return jsonify({"success": False, "error": "Idea not found"}), 404

    feature    = idea.get("solution_feature", "")
    duration_s = int(idea.get("duration", "60s").replace("s", ""))

    try:
        from tools.ui_recorder import record_manual_session
        video_path = record_manual_session(feature, duration_s)
        if not video_path or not video_path.exists():
            return jsonify({"success": False, "error": "No video file produced"}), 500
        return jsonify({
            "success":   True,
            "feature":   feature,
            "duration":  duration_s,
            "video_file": str(video_path),
            "size_kb":   video_path.stat().st_size // 1024,
            "download":  f"/api/recordings/{video_path.name}",
        })
    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/recordings/<filename>")
def serve_recording(filename):
    from tools.ui_recorder import RECORDINGS_DIR
    file_path = RECORDINGS_DIR / filename
    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(str(file_path), mimetype="video/webm", as_attachment=True,
                     download_name=filename)


# ── Auto-Produce: full pipeline orchestrator ──────────────────────────────────
# One button kicks off: script -> narration -> UI recording -> scene clip ->
# music -> assemble. Each stage runs in a background thread; the frontend polls
# /api/produce-jobs/<job_id> to render a live progress bar.

PIPELINE_JOBS  = {}   # job_id -> dict
PIPELINE_LOCK  = threading.Lock()
PIPELINE_STAGES = ["script", "voice", "recording", "scene", "music", "assemble"]


def _job_set(job_id, **kwargs):
    with PIPELINE_LOCK:
        if job_id in PIPELINE_JOBS:
            PIPELINE_JOBS[job_id].update(kwargs)
            PIPELINE_JOBS[job_id]["updated_at"] = time.time()


def _job_log(job_id, msg):
    with PIPELINE_LOCK:
        if job_id in PIPELINE_JOBS:
            PIPELINE_JOBS[job_id].setdefault("log", []).append(msg)
            PIPELINE_JOBS[job_id]["updated_at"] = time.time()
    print(f"  [pipeline {job_id}] {msg}")


def _stage_script(idea):
    """Returns (idea_refreshed, script_path). Reuses if already generated."""
    if idea.get("script_file") and Path(idea["script_file"]).exists():
        return idea, Path(idea["script_file"])

    SCRIPTS.mkdir(parents=True, exist_ok=True)
    safe  = re.sub(r"[^\w\s-]", "", idea["title"]).strip().lower()
    safe  = re.sub(r"[\s-]+", "_", safe)[:35]
    ofile = SCRIPTS / f"{idea['id']}_{safe}.md"

    dur_secs     = idea["duration"].replace("s", "")
    platform_ctx = build_prompt_context(load_backlog()["ideas"])
    feat_info    = get_feature_info(idea.get("solution_feature", ""))
    ripple_hints = ", ".join(feat_info.get("connects_to", [])[:3])

    prompt = _build_script_prompt(idea, platform_ctx, ripple_hints, dur_secs)
    content = ai_call(prompt, high_quality=True)
    ofile.write_text(content, encoding="utf-8")

    data = load_backlog()
    for i in data["ideas"]:
        if i["id"] == idea["id"]:
            i["status"]      = "scripted"
            i["script_file"] = str(ofile)
            idea = i
    save_backlog(data)
    return idea, ofile


def _stage_voice(idea, voice_key):
    voice_id = VOICE_OPTIONS.get(voice_key, VOICE_OPTIONS["james"])["id"]
    script_path = Path(idea["script_file"])
    content   = script_path.read_text(encoding="utf-8")
    narration = _extract_narration(content)
    if not narration:
        raise RuntimeError("Could not extract narration from script")

    VOICES.mkdir(parents=True, exist_ok=True)
    out_file = VOICES / f"{idea['id']}_{voice_key}.mp3"
    if out_file.exists() and out_file.stat().st_size > 1000:
        return out_file
    # Fresh event loop per call — avoids cross-thread loop conflicts on Windows
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            asyncio.wait_for(_generate_tts(narration, voice_id, out_file), timeout=120)
        )
    finally:
        loop.close()
    if not out_file.exists() or out_file.stat().st_size < 1000:
        raise RuntimeError("Edge TTS returned no audio")
    return out_file


def _stage_recording(idea):
    """Reuse the most recent recording for this feature if one exists,
    otherwise auto-record headlessly via Playwright."""
    from tools.ui_recorder import record, DEMOS
    from tools.video_assembler import find_latest_recording

    feature  = idea.get("solution_feature", "")
    existing = find_latest_recording(feature)
    if existing and existing.exists():
        return existing
    if feature not in DEMOS:
        raise RuntimeError(
            f"No auto-record demo for '{feature}'. "
            "Record manually first or pick a feature with a demo."
        )
    return record(feature, headless=True)


def _stage_scene(idea):
    """
    Always re-download fresh Pexels clips on every Auto-Produce.
    The /scene/auto route uses randomized queries + pagination + sampling so
    re-runs don't recycle the same footage. The combined .mp4 overwrites the
    previous one to keep disk usage bounded.
    """
    if not os.getenv("PEXELS_API_KEY"):
        return None
    with app.test_client() as client:
        r = client.post(f"/api/ideas/{idea['id']}/scene/auto")
        body = r.get_json() or {}
        if not body.get("success"):
            raise RuntimeError(body.get("error", "scene download failed"))
        return Path(body["file"])


def _stage_music(idea):
    """Returns music path, or None if JAMENDO_CLIENT_ID not set or fetch fails."""
    if not os.getenv("JAMENDO_CLIENT_ID"):
        return None
    try:
        with app.test_client() as client:
            r = client.post(f"/api/ideas/{idea['id']}/music/auto")
            body = r.get_json() or {}
            if not body.get("success"):
                return None
            return Path(body["file"])
    except Exception:
        return None


def _stage_assemble(idea, voice_key, recording_path, scene_path, music_path):
    from tools.video_assembler import assemble
    return assemble(
        idea_id        = idea["id"],
        voice_key      = voice_key,
        recording_file = recording_path,
        scene_clip     = scene_path,
        music_path     = music_path,
        captions       = True,
    )


def _run_pipeline(job_id, idea_id, voice_key):
    """Background worker — runs the full pipeline and updates job state."""
    try:
        data = load_backlog()
        idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
        if not idea:
            raise RuntimeError(f"Idea {idea_id} not found")

        # ── 1. Script ────────────────────────────────────────────────────
        _job_set(job_id, stage="script", message="Generating script with AI...")
        idea, script_path = _stage_script(idea)
        _job_log(job_id, f"script: {script_path.name}")

        # ── 2. Voice narration ───────────────────────────────────────────
        _job_set(job_id, stage="voice",
                 message=f"Generating narration with {voice_key}...")
        narration_path = _stage_voice(idea, voice_key)
        _job_log(job_id, f"voice: {narration_path.name}")

        # ── 3. UI recording (fail-fast — don't waste time on scene/music
        #      if the recording can't happen at all) ────────────────────
        _job_set(job_id, stage="recording",
                 message="Recording WorkHive UI demo (Playwright)...")
        recording_path = _stage_recording(idea)   # raises on any failure
        _job_log(job_id, f"recording: {recording_path.name}")

        # ── 4. Scene clip (Pexels) ───────────────────────────────────────
        _job_set(job_id, stage="scene",
                 message="Downloading background scene clips from Pexels...")
        try:
            scene_path = _stage_scene(idea)
            _job_log(job_id, f"scene: {scene_path.name if scene_path else 'skipped (no PEXELS_API_KEY)'}")
        except Exception as exc:
            _job_log(job_id, f"scene skipped: {exc}")
            scene_path = None

        # ── 5. Music (Jamendo) ───────────────────────────────────────────
        _job_set(job_id, stage="music",
                 message="Finding royalty-free background music (Jamendo)...")
        music_path = _stage_music(idea)
        _job_log(job_id, f"music: {music_path.name if music_path else 'skipped'}")

        # ── 6. Assemble ──────────────────────────────────────────────────
        _job_set(job_id, stage="assemble",
                 message="Assembling final video with captions (FFmpeg + Whisper)...")
        out_path = _stage_assemble(idea, voice_key, recording_path, scene_path, music_path)
        _job_log(job_id, f"assembled: {out_path.name}")

        size_mb = round(out_path.stat().st_size / 1_000_000, 1)
        _job_set(job_id,
                 stage    = "done",
                 status   = "complete",
                 message  = "Production complete!",
                 output   = str(out_path),
                 download = f"/api/assembled/{out_path.name}",
                 size_mb  = size_mb)

    except Exception as exc:
        import traceback
        traceback.print_exc()
        _job_set(job_id,
                 status  = "error",
                 error   = str(exc),
                 message = f"Failed at '{PIPELINE_JOBS.get(job_id,{}).get('stage','?')}': {exc}")


def _build_script_prompt(idea, platform_ctx, ripple_hints, dur_secs):
    """Assemble the script prompt — kept here so both the orchestrator and the
    /script route can call it without duplication."""
    return f"""{platform_ctx}

You are a creative director writing a production-ready script for a WorkHive ad video.
RIPPLE FEATURES TO MENTION: {ripple_hints}

LANGUAGE: PLAIN SIMPLE ENGLISH ONLY.
- No Tagalog, no Taglish, no Filipino slang, no code-switching anywhere in the script.
- Every NARRATION line, every TEXT OVERLAY, every CTA, every paste-ready block must be in plain English.
- Use short, common words. Short sentences. Conversational, not formal — but English only.
- If the IDEA BRIEF below contains any Tagalog or Taglish, translate it into plain English first, then write the script.

IDEA BRIEF:
- Title:    {idea['title']}
- Hook:     {idea['hook']}
- Problem:  {idea['problem']}
- Feature:  {idea['solution_feature']}
- Audience: {idea['audience']}
- Emotion:  {idea['emotion']}
- Duration: {idea['duration']}
- Type:     {idea['video_type']}

Write the full script using exactly this structure:

# {idea['title']}

## Brief
| Field | Value |
|---|---|
| Duration | {idea['duration']} |
| Type | {idea['video_type']} |
| Audience | {idea['audience']} |
| Emotion | {idea['emotion']} |
| Feature | {idea['solution_feature']} |

---

## Hook (0-5s)
**SHOT:** [opening visual in one sentence]
**NARRATION:** "[exact words spoken]"
**TEXT OVERLAY:** "[on-screen text if any]"

---

## Problem Scene (5-30s)
[4-5 shots showing the pain point. For each shot:]
**SHOT X:** [visual description]
**NARRATION:** "[exact words]"
**TEXT OVERLAY:** "[on-screen text if any]"

---

## Solution Reveal (30-55s)
[Show WorkHive feature solving it. For each shot:]
**SHOT X:** [exactly which screen, button, or flow to show]
**NARRATION:** "[exact words]"
**TEXT OVERLAY:** "[on-screen text if any]"

---

## CTA (55-{dur_secs}s)
**SHOT:** [closing visual]
**NARRATION:** "[CTA line]"
**CTA BUTTON TEXT:** "[button label]"

---

## AI Video Generation Prompts
### Hero Shot (Runway Gen-4 / Kling AI)
[1-2 sentence visual prompt for the hero shot]

### Problem Scene (Runway Gen-4 / Kling AI)
[1-2 sentence prompt for the problem scene footage]

---

## ElevenLabs Narration (paste-ready)
[All narration lines combined in order, one paragraph, ready to paste directly into ElevenLabs]

---

## Music Direction
- **Mood:** [describe the emotional feel]
- **Style:** [e.g. lo-fi hip-hop, industrial ambient, cinematic build, quiet urgency]
- **BPM:** [approximate]

---

## 15-Second Cut (Paid Ad)
**SHOT 1 (0-3s):** [hook visual]
**NARRATION:** "[compressed hook]"
**SHOT 2 (3-10s):** [fastest problem + solution in one cut]
**NARRATION:** "[value statement]"
**SHOT 3 (10-15s):** [CTA]
**TEXT:** "[CTA text]"
"""


@app.route("/api/ideas/<idea_id>/produce-all", methods=["POST"])
def produce_all(idea_id):
    body      = request.get_json(silent=True) or {}
    voice_key = body.get("voice", "james")

    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        return jsonify({"success": False, "error": "Idea not found"}), 404

    job_id = f"job_{idea_id}_{uuid.uuid4().hex[:8]}"
    with PIPELINE_LOCK:
        PIPELINE_JOBS[job_id] = {
            "job_id":     job_id,
            "idea_id":    idea_id,
            "voice":      voice_key,
            "status":     "running",
            "stage":      "starting",
            "stages":     PIPELINE_STAGES,
            "message":    "Starting pipeline...",
            "log":        [],
            "started_at": time.time(),
            "updated_at": time.time(),
        }

    threading.Thread(
        target=_run_pipeline,
        args=(job_id, idea_id, voice_key),
        daemon=True,
    ).start()

    return jsonify({"success": True, "job_id": job_id})


@app.route("/api/produce-jobs/<job_id>")
def produce_status(job_id):
    with PIPELINE_LOCK:
        job = PIPELINE_JOBS.get(job_id)
        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404
        return jsonify({"success": True, **job})


# ── Free tool stack info ───────────────────────────────────────────────────────

@app.route("/api/tools")
def get_tools():
    return jsonify([
        {
            "id":      "voice",
            "name":    "Voice (Built-in)",
            "desc":    "Generate narration audio right here. Microsoft Edge TTS. Philippine English voices.",
            "free":    "Unlimited, no account",
            "action":  "generate",
            "url":     None,
        },
        {
            "id":      "pexels",
            "name":    "Pexels Stock Video",
            "desc":    "Real industrial/factory footage. Auto-downloads a matching clip directly into the assembler. No credits, no signup.",
            "free":    "Forever free, no account needed",
            "action":  "pexels",
            "url":     "https://www.pexels.com/videos/",
        },
        {
            "id":      "pika",
            "name":    "Pika Labs",
            "desc":    "AI video generator. Email signup, no phone number needed. Use the scene prompt from your script.",
            "free":    "Free credits on signup",
            "action":  "open",
            "url":     "https://pika.art",
        },
        {
            "id":      "obs",
            "name":    "OBS Studio",
            "desc":    "Screen-record the WorkHive UI for the solution reveal section.",
            "free":    "Forever free",
            "action":  "open",
            "url":     "https://obsproject.com",
        },
        {
            "id":      "suno",
            "name":    "Suno AI",
            "desc":    "Generate royalty-free background music matched to your video mood.",
            "free":    "50 songs / day",
            "action":  "suno",
            "url":     "https://suno.com",
        },
        {
            "id":      "capcut",
            "name":    "CapCut",
            "desc":    "Assemble clips, add captions, color grade. Auto-caption button built in.",
            "free":    "Free, desktop + web",
            "action":  "open",
            "url":     "https://www.capcut.com",
        },
        {
            "id":      "canva",
            "name":    "Canva",
            "desc":    "Make the video thumbnail. Use WorkHive orange #F7A21B and Poppins font.",
            "free":    "Free tier",
            "action":  "open",
            "url":     "https://www.canva.com",
        },
    ])


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  WorkHive Video Marketing Dashboard")
    print("  Open: http://localhost:5001")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=False, port=5001, threaded=True)
