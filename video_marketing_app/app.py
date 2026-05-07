"""
WorkHive Video Marketing Dashboard - Flask backend
Run via video_marketing.bat or: python video_marketing_app/app.py
"""

from flask import Flask, jsonify, request, render_template, send_file
from pathlib import Path
from datetime import date
import sys, os, json, re, asyncio, requests

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

# Philippine English voices (edge-tts, completely free)
VOICE_OPTIONS = {
    "james":   {"id": "en-PH-JamesNeural",    "label": "James (PH Male)"},
    "rosa":    {"id": "en-PH-RosaNeural",      "label": "Rosa (PH Female)"},
    "angelo":  {"id": "fil-PH-AngeloNeural",   "label": "Angelo (Filipino Male)"},
    "blessica":{"id": "fil-PH-BlessicaNeural", "label": "Blessica (Filipino Female)"},
    "guy":     {"id": "en-US-GuyNeural",       "label": "Guy (US Male, calm)"},
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

    # If targeting a specific feature, add that constraint
    feature_constraint = ""
    if feature and feature in FEATURE_ECOSYSTEM:
        feat_info = get_feature_info(feature)
        connects  = ", ".join(feat_info.get("connects_to", [])[:3])
        feature_constraint = (
            f"\n\nFORCED FEATURE: ALL {n} ideas must focus on '{feature}'.\n"
            f"Loop role: {feat_info.get('loop_role','')}\n"
            f"Connected features to mention in Ripple step: {connects}\n"
        )

    prompt = f"""{platform_ctx}

You are a creative director for viral industrial content in the Philippines.
Generate {n} DISTINCT WorkHive advertisement video ideas.{avoid}{feature_constraint}

Rules:
- Each idea targets ONE pain point only, maps to ONE WorkHive feature only
- Hooks must feel real, not like marketing copy
- Mix video types across the batch (storytelling, testimonial, comparison, educational, emotional)
- At least one idea targets field technicians, one targets supervisors or managers
- Filipino-English mix in hooks is encouraged (Taglish OK)

Return ONLY a valid JSON array, no markdown fences, no explanation:
[
  {{
    "title": "short punchy title (4-7 words)",
    "hook": "opening line a Filipino worker would immediately feel (1-2 sentences, conversational)",
    "problem": "the pain point in plain language (1 sentence)",
    "solution_feature": "exact WorkHive feature name from the list above",
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
        for idea in ideas_raw:
            idea_id  = next_id(data)
            new_idea = {
                "id":               idea_id,
                "title":            idea.get("title", "Untitled"),
                "hook":             idea.get("hook", ""),
                "problem":          idea.get("problem", ""),
                "solution_feature": idea.get("solution_feature", ""),
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

    prompt = f"""{platform_ctx}

You are a creative director writing a production-ready script for a WorkHive ad video.
RIPPLE FEATURES TO MENTION: {ripple_hints}

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
- **Style:** [e.g. lo-fi hip-hop, industrial ambient, upbeat OPM-adjacent]
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
        return jsonify({"success": False, "error": "Idea not found"}), 404
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
    voice_key = request.json.get("voice", "james")
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

    try:
        asyncio.run(_generate_tts(narration, voice_id, out_file))
        return jsonify({
            "success":    True,
            "file":       str(out_file),
            "download":   f"/api/ideas/{idea_id}/voice/download?voice={voice_key}",
            "narration":  narration,
            "char_count": len(narration),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


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

    # Build search query from idea context
    feature  = idea.get("solution_feature", "")
    audience = idea.get("audience", "")
    keywords_map = {
        "Engineering Design Calculator": "engineer calculator industrial",
        "Maintenance Logbook":           "factory maintenance worker",
        "PM Checklist":                  "industrial checklist inspection",
        "Inventory Management":          "warehouse parts inventory",
        "Hive Dashboard":                "plant manager control room",
        "Shift Handover Report":         "factory workers shift change",
        "AI Maintenance Assistant":      "engineer technology digital",
        "Skill Matrix":                  "industrial training workers",
        "Day Planner":                   "engineer planning schedule",
        "Marketplace":                   "industrial parts equipment",
        "Community Forum":               "industrial workers team",
    }
    query = keywords_map.get(feature, "industrial factory worker")

    try:
        # Fetch up to 6 results — we'll pick 3 varied clips
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": query, "per_page": 6, "orientation": "landscape"},
            timeout=10,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            return jsonify({"success": False, "error": f"No Pexels videos found for: {query}"}), 404

        scenes_dir = ROOT / ".tmp/scene_clips"
        scenes_dir.mkdir(parents=True, exist_ok=True)

        def _best_file(video):
            files = sorted(video.get("video_files", []),
                           key=lambda f: f.get("width", 0), reverse=True)
            return next((f for f in files if f.get("width", 0) >= 1280), files[0]) if files else None

        # Download up to 3 clips
        downloaded = []
        credits    = []
        for video in videos[:3]:
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
