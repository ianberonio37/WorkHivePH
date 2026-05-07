#!/usr/bin/env python3
"""
WorkHive Video Marketing Tool
Auto-generates ad video ideas and full production scripts using AI.

Usage:
    python tools/video_idea_generator.py ideas [N]           -- generate N new ideas (default 5)
    python tools/video_idea_generator.py list                -- list all ideas with status
    python tools/video_idea_generator.py script <id>         -- generate full production script
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
STATUSES = ["idea", "scripted", "filming", "produced", "published"]

# ── Platform context comes from platform_intel ────────────────────────────────

def _get_platform_context(ideas: list = None) -> str:
    try:
        from tools.platform_intel import build_prompt_context
        return build_prompt_context(ideas or [])
    except Exception:
        return "PLATFORM: WorkHive — Free Industrial Intelligence Tools for Filipino industrial workers."

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
    Mirrors the platform's AI fallback chain: Groq -> Cerebras -> OpenRouter.
    Same chain used by the ai-orchestrator edge function.
    """
    # 1. Groq — primary (30 req/min free tier)
    if GROQ_KEY:
        model = "llama-3.3-70b-versatile" if high_quality else "llama-3.1-8b-instant"
        try:
            return _call_groq(prompt, model)
        except Exception as exc:
            print(f"  [Groq failed: {exc}] Trying Cerebras...")

    # 2. Cerebras — first fallback (free tier)
    if CEREBRAS_KEY:
        model = "llama-3.3-70b" if high_quality else "llama3.1-8b"
        try:
            return _call_cerebras(prompt, model)
        except Exception as exc:
            print(f"  [Cerebras failed: {exc}] Trying OpenRouter...")

    # 3. OpenRouter — second fallback
    if OPENROUTER_KEY:
        model = (
            "anthropic/claude-sonnet-4-6"
            if high_quality
            else "anthropic/claude-haiku-4-5-20251001"
        )
        try:
            return _call_openrouter(prompt, model)
        except Exception as exc:
            print(f"  [OpenRouter failed: {exc}]")

    raise RuntimeError(
        "All providers failed. Check GROQ_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY in supabase/functions/.env"
    )

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

You are a creative director who specializes in viral industrial content in the Philippines.
Your job: generate {n} DISTINCT WorkHive advertisement video ideas.{avoid}

Rules:
- Each idea targets ONE pain point only
- Each idea maps to ONE WorkHive feature only
- Hooks must feel real, not like marketing copy
- Mix video types across the batch (storytelling, testimonial, comparison, educational, emotional)
- At least one idea must target field technicians, one must target supervisors/managers
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
- **Voice style:** [accent, pace, energy — e.g. Filipino male, calm authority, steady pace]
- **Full narration (paste this):**
  [All narration lines combined in order, one paragraph, ready to copy-paste into ElevenLabs]

---

## Music Direction
- **Mood:** [describe the emotional feel]
- **Style:** [e.g. lo-fi hip-hop, industrial ambient, quiet urgency, upbeat OPM-adjacent]
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
