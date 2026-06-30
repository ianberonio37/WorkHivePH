#!/usr/bin/env python3
"""
WorkHive Video Marketing Tool
Auto-generates ad video ideas and full production scripts using AI.

Usage:
    python tools/video_idea_generator.py ideas [N]           -- generate N new ideas (default 5)
    python tools/video_idea_generator.py list                -- list all ideas with status
    python tools/video_idea_generator.py script <id>         -- generate full production script
    python tools/video_idea_generator.py flagship <id>       -- generate a FlagshipSpec JSON for render_flagship.py
    python tools/video_idea_generator.py mark <id> <status>  -- update status
    python tools/video_idea_generator.py help                -- show this message

Statuses: idea | scripted | filming | produced | published
"""

import json
import sys
import os
import re
import requests
from pathlib import Path
from datetime import date

# Make `from tools.X import ...` resolve when this file is run DIRECTLY
# (`python tools/video_idea_generator.py ...`, the documented CLI): a direct run
# puts tools/ on sys.path[0], not the repo root, so `import tools.*` would fail
# (ModuleNotFoundError: No module named 'tools'). Mirrors storyboard.py.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Environment ───────────────────────────────────────────────────────────────

def _load_env():
    for p in [
        Path(".env"),
        Path("supabase/functions/.env"),
    ]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

GROQ_KEY       = os.getenv("GROQ_API_KEY", "")
CEREBRAS_KEY   = os.getenv("CEREBRAS_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")

BACKLOG  = Path(".tmp/video_ideas_backlog.json")
SCRIPTS  = Path(".tmp/video_scripts")
SPECS    = Path(".tmp/video_specs")
PUBLIC_DIR = Path("remotion_scenes/public")
STATUSES = ["idea", "scripted", "filming", "produced", "published"]

# Real WorkHive screens available as the "product hero" in the flagship video.
# Add more by capturing pages clean at phone viewport into remotion_scenes/public/.
SCREEN_CATALOG = {
    "wh_home_clean.png": "Home dashboard: KPI tiles (Open Jobs, Risk Alerts, PM Overdue, Stock) + a Critical-Risk asset banner. Use for: visibility, early-warning, risk, breakdown-prevention, 'see everything'.",
    "wh_analytics_clean.png": "Analytics Engine: OEE %, Worst MTBF, PM Compliance with ISO/SMRP citations. Use for: reliability metrics, OEE, trends, benchmarks, proving uptime, planning the fix.",
    "wh_pm_clean.png": "PM Scheduler: overdue / due-soon / on-track PM cards + app bottom-nav. Use for: preventive maintenance, schedules, due dates, compliance.",
    "wh_logbook_clean.png": "Digital Logbook: '500 entries, 30 machines' + Log-a-Repair flow with Speak-to-fill + Photo-defect AI capture. Use for: shift handover, fault history, capturing work, voice/photo logging, replacing paper.",
    "wh_inventory_clean.png": "Spare-Parts Inventory: parts count, low-stock + out-of-stock tiles, reorder. Use for: spare parts, stockouts, reorder-before-breakdown, inventory control.",
    "wh_skillmatrix_clean.png": "Skill Matrix: disciplines on-target, quizzes available, badges. Use for: skills, training, certifications, career growth, who-is-qualified.",
    "wh_alerthub_clean.png": "Alert Hub: high-severity alert count, anomaly signals, Critical TX-001 feed with filter chips. Use for: alerts, alert overload, anomaly, prioritization, what-needs-attention.",
    "wh_assistant_clean.png": "AI Work Assistant: chat greeting 'I can see your job records', Ask-anything input. Use for: AI assistant, ask questions, work buddy, guidance, knowledge.",
    "wh_engdesign_clean.png": "Engineering Calculators: 53 calculations across 6 disciplines (HVAC, Mechanical, Electrical, Plumbing, Fire Protection, Machine Design), PEC/ASHRAE/NFPA anchored. Use for: engineering design, calculations, sizing, standards, design-with-confidence.",
}

# Shape the spec-generator must emit (mirrors FlagshipSpec / DEFAULT_SPEC in FlagshipReel.tsx).
EXAMPLE_SPEC = {
    "hook": [
        {"text": "3AM.", "size": 150, "weight": 900},
        {"text": "The line just stopped.", "size": 78},
        {"text": "Again.", "size": 88, "weight": 900, "color": "orange"},
    ],
    "stakes": [
        {"text": "No warning.", "size": 84},
        {"text": "No history.", "size": 84},
        {"text": "A whole shift, gone.", "size": 70, "color": "steel", "accentWords": ["gone"]},
    ],
    "reveal": {"caption": "WorkHive saw it coming.", "accent": ["WorkHive"], "screen": "wh_home_clean.png",
               "flagTitle": "Critical Risk · Today", "flagSub": "TX-001 · 96% · MTBF 9d", "flagColor": "orange", "flagSide": "left"},
    "plan": {"caption": "Fix it on your schedule.", "accent": ["your", "schedule"], "screen": "wh_analytics_clean.png",
             "flagTitle": "OEE · World Class", "flagSub": "87% · ISO 22400", "flagColor": "blue", "flagSide": "right"},
    "payoff": [
        {"text": "Less downtime.", "size": 86},
        {"text": "Longer asset life.", "size": 86, "color": "orange"},
        {"text": "Lower cost.", "size": 86, "color": "blue"},
    ],
    "endTagline": "Built for the plant floor.",
    "endSub": "Free. Mobile-first. Philippines.",
    "endCta": "workhiveph.com · start free",
}

# ── Platform context comes from platform_intel ────────────────────────────────

def _get_platform_context(ideas: list = None) -> str:
    try:
        from tools.platform_intel import build_prompt_context
        return build_prompt_context(ideas or [])
    except Exception:
        return "PLATFORM: WorkHive — Free Industrial Intelligence Tools for industrial workers. All copy in plain simple English."

PLATFORM_CONTEXT = _get_platform_context()

# ── AI call helpers ───────────────────────────────────────────────────────────

def _call_cerebras(prompt: str, model: str = "llama-3.3-70b") -> str:
    resp = requests.post(
        "https://api.cerebras.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {CEREBRAS_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_anthropic(prompt: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _call_openrouter(prompt: str, model: str) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://workhiveph.com",
            "X-Title": "WorkHive Video Marketing Tool",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_groq(prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def ai_call(prompt: str, high_quality: bool = False) -> str:
    """
    Delegates to tools.ai_chain.call_ai_chain — the canonical 14-model
    fallback chain that mirrors supabase/functions/_shared/ai-chain.ts.

    Backward-compatible signature. high_quality=True buys a larger token
    budget (4096 vs 2048) but does NOT pick a "premium" model — the chain
    picks whichever free model is first to respond healthy.

    Returns empty JSON "{}" instead of raising if every provider in the
    chain is unkeyed / rate-limited / errors. Callers parse that as empty
    JSON and handle gracefully (matches TS callAI behaviour).
    """
    from tools.ai_chain import call_ai_chain
    max_tokens = 4096 if high_quality else 2048
    out = call_ai_chain(prompt, max_tokens=max_tokens, json_mode=False)
    if out == "{}":
        # Preserve previous raise behaviour for callers that explicitly
        # check for failures (e.g. video idea generator). Platform pack
        # wraps this in its own try/except so it surfaces as a soft warning.
        raise RuntimeError(
            "All providers in the 14-model chain returned empty. "
            "Check GROQ_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY "
            "in supabase/functions/.env (or pass them via tester env)."
        )
    return out

# ── Backlog helpers ───────────────────────────────────────────────────────────

def load_backlog() -> dict:
    if not BACKLOG.exists():
        return {"ideas": []}
    return json.loads(BACKLOG.read_text(encoding="utf-8"))


def save_backlog(data: dict):
    BACKLOG.parent.mkdir(parents=True, exist_ok=True)
    BACKLOG.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def next_id(data: dict) -> str:
    if not data["ideas"]:
        return "idea_001"
    nums = [
        int(re.search(r"\d+", i["id"]).group())
        for i in data["ideas"]
        if re.search(r"\d+", i["id"])
    ]
    return f"idea_{max(nums) + 1:03d}"


# ── Command: ideas ────────────────────────────────────────────────────────────

def cmd_ideas(n: int = 5):
    """Generate N new video ideas and append to backlog."""
    data     = load_backlog()
    existing = [i["title"] for i in data["ideas"]]
    avoid    = (
        "\n\nALREADY IN BACKLOG (do not repeat these):\n"
        + "\n".join(f"- {t}" for t in existing)
        if existing
        else ""
    )

    prompt = f"""{PLATFORM_CONTEXT}

You are a creative director who specializes in viral industrial content.
Your job: generate {n} DISTINCT WorkHive advertisement video ideas.{avoid}

Rules:
- Each idea targets ONE pain point only
- Each idea maps to ONE WorkHive feature only
- Hooks must feel real, not like marketing copy
- Mix video types across the batch (storytelling, testimonial, comparison, educational, emotional)
- At least one idea must target field technicians, one must target supervisors/managers
- ALL copy (title, hook, problem) must be in PLAIN SIMPLE ENGLISH — no Tagalog, no Taglish, no code-switching, no Filipino slang
- Use short, common words. Short sentences.

Return ONLY a valid JSON array, no markdown fences, no explanation:
[
  {{
    "title": "short punchy title (4-7 words, plain English)",
    "hook": "opening line in plain simple English any plant worker would immediately feel (1-2 sentences, conversational)",
    "problem": "the pain point in plain English (1 sentence)",
    "solution_feature": "exact WorkHive feature name from the list above",
    "audience": "who this targets (e.g. Plant Manager, Field Technician, Supervisor, Engineer)",
    "emotion": "primary emotion triggered (e.g. Fear of downtime, Pride, Relief, Ambition)",
    "duration": "60s",
    "video_type": "storytelling | testimonial | comparison | educational | emotional"
  }}
]"""

    print(f"\nGenerating {n} new video ideas...")
    raw = ai_call(prompt)

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        print("ERROR: AI did not return valid JSON. Raw output:\n")
        print(raw[:600])
        return

    try:
        ideas_raw = json.loads(match.group())
    except json.JSONDecodeError as exc:
        print(f"ERROR: JSON parse failed: {exc}\n")
        print(raw[:600])
        return

    added = 0
    for idea in ideas_raw:
        idea_id = next_id(data)
        data["ideas"].append({
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
        })
        print(f"  + [{idea_id}] {idea.get('title', 'Untitled')}")
        added += 1

    save_backlog(data)
    print(f"\n{added} idea(s) added. Run `list` to see full backlog.")


# ── Command: list ─────────────────────────────────────────────────────────────

STATUS_ICONS = {
    "idea":      "[ IDEA ]    ",
    "scripted":  "[SCRIPTED]  ",
    "filming":   "[FILMING ]  ",
    "produced":  "[PRODUCED]  ",
    "published": "[ LIVE  ]   ",
}

def cmd_list():
    """List all ideas with status indicators."""
    data = load_backlog()
    if not data["ideas"]:
        print("\nBacklog is empty.")
        print("Run: python tools/video_idea_generator.py ideas 5")
        return

    print(f"\n{'ID':<12} {'STATUS':<14} {'TYPE':<14} {'AUDIENCE':<24} TITLE")
    print("-" * 95)
    for idea in sorted(data["ideas"], key=lambda x: x["id"]):
        icon = STATUS_ICONS.get(idea["status"], "[?]      ")
        print(
            f"{idea['id']:<12} {icon:<14} "
            f"{idea.get('video_type',''):<14} "
            f"{idea.get('audience',''):<24} "
            f"{idea['title']}"
        )
    total     = len(data["ideas"])
    published = sum(1 for i in data["ideas"] if i["status"] == "published")
    scripted  = sum(1 for i in data["ideas"] if i["status"] == "scripted")
    print(f"\n{total} total | {scripted} scripted | {published} published")


# ── Command: script ───────────────────────────────────────────────────────────

def cmd_script(idea_id: str):
    """Generate a full production script for the given idea."""
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        print(f"\nERROR: '{idea_id}' not found. Run `list` to see valid IDs.")
        return

    SCRIPTS.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^\w\s-]", "", idea["title"]).strip().lower()
    safe_title = re.sub(r"[\s-]+", "_", safe_title)[:35]
    out_file   = SCRIPTS / f"{idea_id}_{safe_title}.md"

    prompt = f"""{PLATFORM_CONTEXT}

You are a creative director writing a production-ready script for a WorkHive ad video.

LANGUAGE: PLAIN SIMPLE ENGLISH ONLY.
- No Tagalog, no Taglish, no Filipino slang, no code-switching anywhere in the script.
- Every NARRATION line, every TEXT OVERLAY, every CTA, every paste-ready block must be in plain English.
- Use short, common words. Short sentences. Conversational, not formal — but English only.
- If the IDEA BRIEF below contains any Tagalog or Taglish, translate it into plain English first.

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
**SHOT:** [describe the opening visual in one sentence]
**NARRATION:** "[exact words spoken]"
**TEXT OVERLAY:** "[text on screen, if any]"

---

## Problem Scene (5-30s)
[4-5 shots showing the pain point. For each shot:]
**SHOT X:** [visual description]
**NARRATION:** "[exact words]"
**TEXT OVERLAY:** "[on-screen text, if any]"

---

## Solution Reveal (30-55s)
[Show the WorkHive feature solving it. For each shot:]
**SHOT X:** [exactly what UI to show — be specific about which screen/button/flow]
**NARRATION:** "[exact words]"
**TEXT OVERLAY:** "[on-screen text, if any]"

---

## CTA (55-{idea['duration'].replace('s','')}s)
**SHOT:** [closing visual]
**NARRATION:** "[CTA line]"
**TEXT OVERLAY:** "[website or app store URL text]"
**CTA BUTTON TEXT:** "[button label]"

---

## AI Video Generation Prompts
### Hero Shot (Runway Gen-4 / Kling AI)
[1-2 sentence visual prompt — style, lighting, subject, mood. Be specific.]

### Problem Scene (Runway Gen-4 / Kling AI)
[1-2 sentence prompt for the problem scene footage]

---

## ElevenLabs Voice Direction
- **Voice style:** [accent, pace, energy — e.g. PH-accented English male, calm authority, steady pace]
- **Full narration (paste this — PLAIN ENGLISH ONLY):**
  [All narration lines combined in order, one paragraph, ready to copy-paste into ElevenLabs. English only, no Tagalog.]

---

## Music Direction
- **Mood:** [describe the emotional feel]
- **Style:** [e.g. lo-fi hip-hop, industrial ambient, cinematic build, quiet urgency]
- **BPM:** [approximate]
- **Reference:** [describe a song feel, no copyright names needed]

---

## CapCut Assembly Notes
- **Caption style:** [font, size, color — must match WorkHive brand: Poppins, orange #F7A21B]
- **Key edit beats:** [where cuts should land relative to narration]
- **Transitions:** [cut, L-cut, fade, or match cut — be specific per section]
- **Color grade:** [describe the look — e.g. desaturated industrial + warm orange highlights]

---

## 15-Second Cut (Paid Ad Version)
**SHOT 1 (0-3s):** [hook visual]
**NARRATION:** "[compressed hook]"
**SHOT 2 (3-10s):** [fastest problem + solution in one cut]
**NARRATION:** "[compressed value statement]"
**SHOT 3 (10-15s):** [CTA]
**TEXT OVERLAY:** "[CTA text]"
"""

    print(f"\nGenerating script for [{idea_id}] {idea['title']}...")
    print("(Using high-quality model -- this may take 30-60 seconds)")
    script_content = ai_call(prompt, high_quality=True)

    out_file.write_text(script_content, encoding="utf-8")

    for i in data["ideas"]:
        if i["id"] == idea_id:
            i["status"]      = "scripted"
            i["script_file"] = str(out_file)
    save_backlog(data)

    print(f"\nScript saved: {out_file}")
    print(f"Status: idea -> scripted")
    print("\n--- PREVIEW (first 25 lines) ---")
    lines = script_content.split("\n")
    print("\n".join(lines[:25]))
    if len(lines) > 25:
        print(f"\n... ({len(lines) - 25} more lines in file)")


# ── Command: flagship (idea -> data-driven FlagshipSpec for render_flagship.py) ─

def _available_screens() -> dict:
    return {f: d for f, d in SCREEN_CATALOG.items() if (PUBLIC_DIR / f).exists()}


def _coerce_spec(spec: dict, avail: list) -> dict:
    """Validate/clamp the AI output so the render never references a missing screen
    or an off-brand value. Missing pieces fall back to the reference defaults."""
    home = "wh_home_clean.png" if "wh_home_clean.png" in avail else (avail[0] if avail else "wh_home_clean.png")
    ana  = "wh_analytics_clean.png" if "wh_analytics_clean.png" in avail else home

    def clampf(v, lo, hi, d):
        try:
            return max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            return d

    def fix_lines(lines, dflt_size):
        out = []
        if isinstance(lines, list):
            for l in lines[:3]:
                if not isinstance(l, dict) or not str(l.get("text", "")).strip():
                    continue
                ln = {"text": str(l["text"])[:42], "size": int(clampf(l.get("size", dflt_size), 36, 160, dflt_size))}
                if l.get("weight") in (700, 800, 900):
                    ln["weight"] = l["weight"]
                if l.get("color") in ("cloud", "orange", "blue", "steel"):
                    ln["color"] = l["color"]
                if isinstance(l.get("accentWords"), list):
                    ln["accentWords"] = [str(w) for w in l["accentWords"][:4]]
                out.append(ln)
        return out

    def fix_prod(p, dflt_screen, dflt_color, side):
        p = p if isinstance(p, dict) else {}
        scr = p.get("screen")
        if scr not in avail:
            scr = dflt_screen
        acc = p.get("accent")
        return {
            "caption":  str(p.get("caption", ""))[:48] or "See it in WorkHive.",
            "accent":   [str(w) for w in acc[:4]] if isinstance(acc, list) else [],
            "screen":   scr,
            "flagTitle": str(p.get("flagTitle", ""))[:28],
            "flagSub":   str(p.get("flagSub", ""))[:32],
            "flagColor": p.get("flagColor") if p.get("flagColor") in ("orange", "blue") else dflt_color,
            "flagSide":  p.get("flagSide") if p.get("flagSide") in ("left", "right") else side,
        }

    hook   = fix_lines(spec.get("hook"), 90)   or [{"text": "It broke. Again.", "size": 120, "weight": 900}]
    stakes = fix_lines(spec.get("stakes"), 80) or [{"text": "And nobody saw it coming.", "size": 78}]
    payoff = fix_lines(spec.get("payoff"), 86) or [{"text": "Less downtime.", "size": 86},
                                                   {"text": "More control.", "size": 86, "color": "orange"}]
    return {
        "hook": hook, "stakes": stakes,
        "reveal": fix_prod(spec.get("reveal"), home, "orange", "left"),
        "plan":   fix_prod(spec.get("plan"),  ana,  "blue",  "right"),
        "payoff": payoff,
        # End card is a LOCKED brand closer on every video (consistent sign-off,
        # and avoids AI truncation). Not AI-varied.
        "endTagline": "Built for the plant floor.",
        "endSub":     "Free. Mobile-first. Philippines.",
        "endCta":     "workhiveph.com · start free",
    }


def _evidence_for_feature(feature_name: str):
    """Resolve a feature NAME to (feature_id, affordance_block) from the LIVE
    page-evidence — the REAL UI the flagship copy may reference. Born-grounded: the
    reveal/plan captions + flag callouts must trace to these, not invent UI (the
    same grounding the article + script generators already use). All lazy + guarded
    so a missing catalog/evidence can never break spec generation."""
    try:
        from tools.platform_catalog import build_catalog, _resolve_label_to_feature
        from tools.page_evidence import load_evidence
        cat = build_catalog()
        fid = _resolve_label_to_feature(feature_name, cat["features"])
        ev = load_evidence().get(fid) if fid else None
        if not ev:
            return fid, ""
        headings = (ev.get("headings") or [])[:8]
        actions  = (ev.get("actions") or [])[:10]
        tabs     = (ev.get("tabs") or [])[:8]
        block = (
            f"\nREAL UI AFFORDANCES of the {feature_name} page (the reveal/plan captions and the "
            f"flagTitle/flagSub data callouts must reference ONLY what actually exists here. Do NOT "
            f"invent buttons, tabs, screens, metrics, or capabilities the page does not have):\n"
            f"- headings: {', '.join(headings)}\n"
            f"- buttons/actions: {', '.join(actions)}\n"
            + (f"- tabs: {', '.join(tabs)}\n" if tabs else "")
        )
        return fid, block
    except Exception:
        return None, ""


def _spec_grounding_text(spec: dict) -> str:
    """The product-claim-bearing copy of a FlagshipSpec (captions + data callouts),
    for the capability gate. The locked end card is brand boilerplate, excluded."""
    parts: list[str] = []
    for grp in ("hook", "stakes", "payoff"):
        for line in spec.get(grp, []) or []:
            if isinstance(line, dict):
                parts.append(line.get("text", ""))
    for beat in ("reveal", "plan"):
        b = spec.get(beat, {}) or {}
        parts += [b.get("caption", ""), b.get("flagTitle", ""), b.get("flagSub", "")]
    return ". ".join(p for p in parts if p)


def cmd_flagship(idea_id: str):
    """Convert an idea into a FlagshipSpec JSON for tools/render_flagship.py."""
    data = load_backlog()
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        print(f"\nERROR: '{idea_id}' not found. Run `list` to see valid IDs.")
        return

    avail = _available_screens()
    if not avail:
        print(f"\nERROR: no product screens in {PUBLIC_DIR}. Capture some clean phone-viewport PNGs first.")
        return
    screens_desc = "\n".join(f'- "{f}": {d}' for f, d in avail.items())
    fid, evidence_block = _evidence_for_feature(idea['solution_feature'])

    prompt = f"""{PLATFORM_CONTEXT}

You are a senior product-marketing video director. Convert ONE WorkHive ad idea into a "FlagshipSpec"
for a ~17-second VERTICAL, MUTE-FIRST product video: on-screen kinetic captions carry the story, NO voiceover.

IDEA BRIEF:
- Title:    {idea['title']}
- Hook:     {idea['hook']}
- Problem:  {idea['problem']}
- Feature:  {idea['solution_feature']}
- Audience: {idea['audience']}
- Emotion:  {idea['emotion']}
{evidence_block}

THE 6-BEAT ARC (commit to ONE pain + ONE feature; NEVER list multiple features):
1) hook    : 2-3 very short kinetic lines = a SPECIFIC pain moment (not a slogan). First line is the biggest.
2) stakes  : 2-3 short lines = what that pain costs.
3) reveal  : WorkHive solving it = a caption + the product screen that shows it + a data callout flag.
4) plan    : the in-product payoff = a second caption + a screen + a callout.
5) payoff  : exactly 3 short outcome lines.
6) end card: tagline + sub + CTA.

AVAILABLE PRODUCT SCREENS (set reveal.screen and plan.screen to EXACTLY one of these filenames, whichever fits the feature best):
{screens_desc}

COPY RULES:
- Plain simple English only. No Tagalog, no Taglish.
- NO em dashes anywhere. Use periods, commas, colons, or the middot ·.
- Short, punchy, instantly mute-readable. One idea per line.
- 'accent' = the 1-3 words in that caption to highlight orange.
- 'flagColor' = "orange" or "blue". 'flagSide' = "left" or "right". per-line 'color' = cloud|orange|blue|steel.
- 'size' guidance: hook first line 130-150, other hook lines 70-90, stakes 78-86, payoff 84-90.
- flagTitle/flagSub should look like a real WorkHive data callout (short label + a number/metric).

Return ONLY valid JSON (no markdown fences, no commentary), in EXACTLY this shape:
{json.dumps(EXAMPLE_SPEC, ensure_ascii=False, indent=2)}
"""

    print(f"\nGenerating flagship spec for [{idea_id}] {idea['title']}...")
    print("(Using the AI chain -- this may take 20-40 seconds)")
    raw = ai_call(prompt, high_quality=True)

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        print("ERROR: AI did not return JSON. Raw:\n" + raw[:600])
        return
    try:
        spec_raw = json.loads(m.group())
    except json.JSONDecodeError as exc:
        print(f"ERROR: JSON parse failed: {exc}\n" + raw[:600])
        return

    spec = _coerce_spec(spec_raw, list(avail.keys()))
    SPECS.mkdir(parents=True, exist_ok=True)
    out_file = SPECS / f"{idea_id}_flagship.json"
    out_file.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    # Capability gate: the flagship spec is born-grounded like the article + script
    # generators — its captions and data callouts must trace to the feature's REAL
    # affordances, or they are invented UI. Guarded so it never blocks a render.
    if fid:
        try:
            from tools.content_grounding_gate import capability_issues_for_text
            issues = capability_issues_for_text(_spec_grounding_text(spec), fid)
            if issues:
                print(f"\n  WARNING capability-grounding: {len(issues)} possibly-invented UI claim(s):")
                for i in issues[:5]:
                    print(f"    - {i.get('claim') or i.get('reason')}")
                print("  Review the reveal/plan captions + flag callouts against the real page.")
            else:
                print("  capability-grounding: OK (spec references only real UI affordances).")
        except Exception:
            pass

    print(f"\nSpec saved: {out_file}")
    print(f"  reveal screen: {spec['reveal']['screen']}   plan screen: {spec['plan']['screen']}")
    print("\nRender it (9:16 + 1:1 + 16:9, with music + SFX, copied to Desktop):")
    print(f"  python tools/render_flagship.py --spec {out_file} --name {idea_id} --desktop")


# ── Command: mark ─────────────────────────────────────────────────────────────

def cmd_mark(idea_id: str, status: str):
    """Update the status of an idea."""
    if status not in STATUSES:
        print(f"\nERROR: Invalid status '{status}'.")
        print(f"Valid statuses: {' | '.join(STATUSES)}")
        return

    data = load_backlog()
    for idea in data["ideas"]:
        if idea["id"] == idea_id:
            old = idea["status"]
            idea["status"] = status
            save_backlog(data)
            print(f"\n[{idea_id}] {idea['title']}")
            print(f"  Status: {old} -> {status}")
            return

    print(f"\nERROR: '{idea_id}' not found. Run `list` to see valid IDs.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or args[0].lower() in ("help", "--help", "-h"):
        print(__doc__)
        return

    cmd = args[0].lower()

    if cmd == "ideas":
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
        cmd_ideas(n)

    elif cmd == "list":
        cmd_list()

    elif cmd == "script":
        if len(args) < 2:
            print("Usage: python tools/video_idea_generator.py script <idea_id>")
        else:
            cmd_script(args[1])

    elif cmd == "flagship":
        if len(args) < 2:
            print("Usage: python tools/video_idea_generator.py flagship <idea_id>")
        else:
            cmd_flagship(args[1])

    elif cmd == "mark":
        if len(args) < 3:
            print("Usage: python tools/video_idea_generator.py mark <idea_id> <status>")
            print(f"Statuses: {' | '.join(STATUSES)}")
        else:
            cmd_mark(args[1], args[2])

    else:
        print(f"Unknown command: '{cmd}'")
        print("Run `help` for usage.")


if __name__ == "__main__":
    main()
