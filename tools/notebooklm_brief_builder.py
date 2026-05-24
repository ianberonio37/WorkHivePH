"""
notebooklm_brief_builder.py — assemble the source bundle that NotebookLM
ingests when generating long-form artifacts for a WorkHive video idea.

Strategy:
  * NotebookLM is grounded — its outputs only quote what you upload. So we
    deliberately stuff the notebook with structured markdown that captures
    WorkHive product context, the specific idea/pain-point/feature, and the
    full production script (which already encodes voice, audience, emotion).
  * Sources are written to .tmp/notebooklm/<idea_id>/sources/ as standalone
    .md files. NotebookLM accepts MD/PDF/TXT cleanly.
  * Each source has a stable filename so re-runs overwrite in place and the
    notebook can be refreshed without duplicate sources.

Public entrypoint:
  build_sources(idea_id) -> list[Path]
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

BACKLOG_PATH    = Path(".tmp/video_ideas_backlog.json")
NOTEBOOKLM_ROOT = Path(".tmp/notebooklm")


# ── Idea + script lookup ──────────────────────────────────────────────────────

def _load_backlog() -> dict:
    if not BACKLOG_PATH.exists():
        return {"ideas": []}
    return json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))


def find_idea(idea_id: str) -> dict:
    for i in _load_backlog().get("ideas", []):
        if i.get("id") == idea_id:
            return i
    raise KeyError(f"Idea {idea_id} not in backlog. Generate one first via the dashboard or video_idea_generator.py.")


def _read_script(idea: dict) -> str:
    sf = idea.get("script_file")
    if not sf:
        return ""
    p = Path(sf)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _platform_context() -> str:
    """Cheap pull from the existing platform_intel module. Falls back to a
    minimal stub if the module isn't importable from the current CWD."""
    try:
        from tools.platform_intel import build_prompt_context
        return build_prompt_context([])
    except Exception as exc:                         # noqa: BLE001
        return (
            "WORKHIVE PLATFORM\n"
            "=================\n"
            "Free Industrial Intelligence Tools for plant workers, supervisors, "
            "managers, engineers, and planners in Philippine industrial sites.\n"
            f"(platform_intel import failed: {exc})\n"
        )


# ── Source-file authors ───────────────────────────────────────────────────────

_BRAND_VOICE = """\
# WorkHive Brand Voice & Style Guide

This document is authoritative — every artifact generated from this notebook
must follow these rules. Cite this file when narrating in voice or video.

## Tone
- Plain simple English. Short sentences. Conversational.
- Industrial credibility — speak like someone who has worked a shift, not a marketing intern.
- Use real maintenance vocabulary: OEE, MTBF, MTTR, FMEA, PM compliance, downtime, root cause.

## Forbidden
- No Tagalog, no Taglish, no code-switching inside the same artifact.
  English-version artifacts are pure English. Tagalog-version artifacts (when
  explicitly requested) are pure Filipino.
- No hype words: "revolutionary", "game-changer", "disruptive", "synergy".
- No vague claims. Every benefit must be measurable (hours saved, % uptime gained, etc.).

## Audience defaults
- Field technician: practical, immediate, hands-on. Focus on shift-level pain.
- Supervisor: visibility across the plant, shift handover, accountability.
- Plant manager: downtime cost, compliance, capex, ROI.
- Engineer: standards alignment, calc accuracy, FMEA / Weibull credibility.
- Planner: parts availability, PM schedule integrity.

## Brand
- Color: orange `#F7A21B` for highlights.
- Font: Poppins for headings, system-default body.
- CTA pattern: "Try WorkHive free at workhiveph.com" — no email-gate language.
"""


_PRODUCT_OVERVIEW = """\
# WorkHive — Product Overview (for AI grounding)

WorkHive is a free industrial intelligence platform for Philippine maintenance
operations. Workers, supervisors, and managers use it to log faults, plan
preventive maintenance, track OEE, and let an AI companion answer field
questions hands-free while wearing PPE.

## Pillars
1. **Maintenance Logbook** — voice + text fault logging, knowledge graph behind it.
2. **PM Scheduler** — preventive maintenance compliance, drift detection.
3. **Analytics & OEE Dashboard** — real-time availability / performance / quality.
4. **Predictive Analytics + Auto-Staging** — failure prediction *and* automatic
   spare-parts reservation in the inventory. Unique in the PH market.
5. **Asset Brain** — plant equipment hierarchy with reliability data.
6. **Shift Brain** — shift handover, briefing, cross-shift learning.
7. **Voice Command Routing** — workers in PPE log entries, query status,
   trigger actions hands-free.
8. **AI Maintenance Assistant** — companion grounded in plant fault history.
9. **Skill Matrix** — apprentice/standard/senior depth per worker.
10. **Alert Hub** — predictive thresholds + escalation chain.
11. **PH Industry Intelligence** — benchmarks against PH manufacturing peers.
12. **CMMS Integrations** — SAP PM, IBM Maximo, OPC-UA, MQTT.
13. **Audit Log & Compliance** — ISO/PDPA-ready audit trail.

## Engineering credibility layer
Reliability math is not ML guesswork — Weibull β/η, P-F intervals, FMEA scoring,
ISO 50001 EnPI, MTBF/MTTR derivations. Skeptical engineers can verify.

## Free-tier-only AI chain
All AI inference uses the free-tier model chain (Groq → Cerebras → SambaNova →
Gemini → OpenRouter :free → DeepSeek). Zero per-token cost. Per-hive AI context
+ RAG over fault knowledge graph.
"""


def _idea_card(idea: dict) -> str:
    return f"""\
# Idea Brief — {idea.get('id', '?')}: {idea.get('title', 'Untitled')}

| Field    | Value |
|----------|-------|
| ID       | {idea.get('id', '')} |
| Title    | {idea.get('title', '')} |
| Hook     | {idea.get('hook', '')} |
| Problem  | {idea.get('problem', '')} |
| Feature  | {idea.get('solution_feature', '')} |
| Audience | {idea.get('audience', '')} |
| Emotion  | {idea.get('emotion', '')} |
| Duration | {idea.get('duration', '')} |
| Type     | {idea.get('video_type', '')} |
| Status   | {idea.get('status', '')} |

## How AI artifacts should use this idea
- The IDEA is the *core message*. Every artifact (audio, video, slides, blog)
  must lead with the same pain point and resolve with the same feature.
- The AUDIENCE field is non-negotiable. If audience is "Plant Manager", do not
  drift into technician-level language.
- The EMOTION drives delivery pacing (Fear of downtime → urgent / Pride → warm).
- The FEATURE is the *only* WorkHive capability the artifact should pitch.
  Other features may be mentioned as ripples, never as the headline.
"""


def _extract_paste_blocks(script_md: str) -> str:
    """Pull the 'paste-ready' narration + music-direction blocks out of the
    script Markdown so the audio/video lanes can reuse them verbatim. Only
    appends a section if the captured body actually has content."""
    parts: list[str] = []

    def _grab(pattern: str, heading: str):
        m = re.search(pattern, script_md, re.IGNORECASE)
        if not m:
            return
        body = m.group(1).strip()
        if body:
            parts.append(f"## {heading}\n\n{body}")

    _grab(
        r"ElevenLabs Narration.*?\(paste-ready\)\s*\n([\s\S]*?)(?=\n---|\n##|\Z)",
        "Narration (paste-ready, English)",
    )
    _grab(
        r"Music Direction\s*\n([\s\S]*?)(?=\n---|\n##|\Z)",
        "Music Direction",
    )
    _grab(
        r"15-Second Cut.*?\n([\s\S]*?)(?=\n---|\n##|\Z)",
        "15-Second Paid Ad Cut",
    )

    return "\n\n---\n\n".join(parts) if parts else ""


# ── Public entrypoint ─────────────────────────────────────────────────────────

def build_sources(idea_id: str) -> list[Path]:
    """Materialise a source bundle for this idea. Idempotent — re-running
    overwrites the same files. Returns the list of file paths in upload order.
    """
    idea = find_idea(idea_id)
    workspace = NOTEBOOKLM_ROOT / idea_id / "sources"
    workspace.mkdir(parents=True, exist_ok=True)

    sources: list[Path] = []

    # 1. Brand voice — always first so NotebookLM treats it as global guidance.
    p = workspace / "01_brand_voice.md"
    p.write_text(_BRAND_VOICE, encoding="utf-8")
    sources.append(p)

    # 2. Product overview.
    p = workspace / "02_product_overview.md"
    p.write_text(_PRODUCT_OVERVIEW, encoding="utf-8")
    sources.append(p)

    # 3. Live platform intel snapshot (real Supabase signals when available).
    p = workspace / "03_platform_context.md"
    p.write_text(
        "# Live Platform Context (snapshot)\n\n"
        "This is pulled from tools/platform_intel.py at brief-build time. "
        "It reflects the actual state of the WorkHive backend when this "
        "notebook was assembled.\n\n"
        + _platform_context(),
        encoding="utf-8",
    )
    sources.append(p)

    # 4. The idea card.
    p = workspace / "04_idea_brief.md"
    p.write_text(_idea_card(idea), encoding="utf-8")
    sources.append(p)

    # 5. The full production script (if generated already).
    script_md = _read_script(idea)
    if script_md:
        p = workspace / "05_video_script.md"
        p.write_text(
            "# Video Script — full production breakdown\n\n"
            "This is the canonical 60-second ad script. Long-form artifacts "
            "(podcasts, cinematic videos, blog posts) must STAY ON MESSAGE with "
            "this script — same pain, same feature, same audience — but may "
            "expand into deeper structure.\n\n"
            + script_md,
            encoding="utf-8",
        )
        sources.append(p)

        paste = _extract_paste_blocks(script_md)
        if paste and paste.strip():
            p = workspace / "06_narration_and_music.md"
            p.write_text(
                "# Paste-ready Narration & Music Direction\n\n"
                "Use the narration block as the *spine* of any audio artifact. "
                "Use the music direction to choose tempo/mood for video.\n\n"
                + paste,
                encoding="utf-8",
            )
            sources.append(p)
        else:
            # Remove a stale empty file from a previous run so it isn't uploaded.
            stale = workspace / "06_narration_and_music.md"
            if stale.exists() and stale.stat().st_size == 0:
                stale.unlink()

    return sources


# ── CLI for ad-hoc rebuilds ───────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tools/notebooklm_brief_builder.py <idea_id>")
        sys.exit(1)
    paths = build_sources(sys.argv[1])
    print(f"Built {len(paths)} source files:")
    for p in paths:
        print(f"  - {p}  ({p.stat().st_size // 1024} KB)")
