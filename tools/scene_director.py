"""
scene_director.py — the ADAPTIVE brain for the Remotion background.

Given a video idea (+ its production script), it picks the best animated scene
STYLE and fills the content, so every video's background fits the idea instead of
being one static template. Uses the same free AI chain as the rest of the bat,
with a deterministic rules fallback so it never blocks a render.

Styles:
  dashboard   — live data-viz motion (bars/line/gauge). Analytics, OEE, monitoring.
  kinetic     — kinetic typography of key phrases. Storytelling / emotional.
  infographic — animated stat cards + counters. Educational / comparison / numbers.
  mindmap     — hub-and-spoke node graph. "How it all connects" explainers.

Public: direct_scene(idea: dict, script_text: str = "") -> dict
        → {style, headline, subhead, phrases[], stats[], nodes[]}
"""
from __future__ import annotations

import sys
import json
import re
from pathlib import Path

# Ensure repo root is importable so `from tools.X import Y` works whether this is
# run standalone (python tools/scene_director.py) or imported by the pipeline.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

STYLES = {"dashboard", "kinetic", "infographic", "mindmap"}


def _read_script(idea: dict) -> str:
    sf = idea.get("script_file")
    if not sf:
        return ""
    p = Path(sf)
    try:
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except Exception:
        return ""


def _coerce(spec: dict, idea: dict) -> dict:
    """Validate / normalise the AI spec, filling any gaps from the idea."""
    feature = (idea.get("solution_feature") or "WorkHive").strip()
    style = str(spec.get("style", "")).lower().strip()
    if style not in STYLES:
        style = _rules_style(idea)
    headline = (spec.get("headline") or idea.get("title") or "WorkHive").strip()[:60]
    subhead = (spec.get("subhead") or f"WorkHive · {feature}").strip()[:42]

    def _strlist(v, n, fallback):
        if not isinstance(v, list) or not v:
            return fallback
        out = [str(x).strip() for x in v if str(x).strip()]
        return out[:n] or fallback

    phrases = _strlist(spec.get("phrases"), 5, _rules_phrases(idea))
    nodes = _strlist(spec.get("nodes"), 5, _rules_nodes(idea))

    stats = spec.get("stats")
    if not isinstance(stats, list) or not stats:
        stats = _rules_stats(idea)
    else:
        norm = []
        for s in stats[:4]:
            if isinstance(s, dict) and s.get("value") and s.get("label"):
                d = str(s.get("dir", "up")).lower()
                norm.append({"value": str(s["value"])[:8], "label": str(s["label"])[:22],
                             "dir": d if d in ("up", "down", "flat") else "up"})
        stats = norm or _rules_stats(idea)

    return {"style": style, "headline": headline, "subhead": subhead,
            "phrases": phrases, "stats": stats, "nodes": nodes}


# ── Deterministic fallbacks ─────────────────────────────────────────────────

def _rules_style(idea: dict) -> str:
    typ = (idea.get("type") or "").lower()
    feat = (idea.get("solution_feature") or "").lower()
    if any(k in feat for k in ("analytics", "oee", "dashboard", "predictive", "intelligence")):
        return "dashboard"
    if any(k in typ for k in ("compar", "educational")):
        return "infographic"
    if any(k in typ for k in ("story", "emotional", "testimon")):
        return "kinetic"
    if any(k in feat for k in ("hive", "integration", "project", "asset")):
        return "mindmap"
    return "dashboard"


def _sentences(idea: dict) -> list[str]:
    text = " ".join(str(idea.get(k, "")) for k in ("hook", "problem", "title"))
    parts = re.split(r"[.!?]\s+", text)
    return [p.strip() for p in parts if 2 <= len(p.split()) <= 6][:5]


def _rules_phrases(idea: dict) -> list[str]:
    s = _sentences(idea)
    return s if s else [idea.get("title", "WorkHive")]


def _rules_stats(idea: dict) -> list[dict]:
    return [
        {"value": "100%", "label": "Free to start", "dir": "up"},
        {"value": "24/7", "label": "Always on", "dir": "flat"},
        {"value": "1", "label": "Place for everything", "dir": "up"},
    ]


def _rules_nodes(idea: dict) -> list[str]:
    return ["Logbook", "PM Checklist", "Inventory", "Alerts"]


# ── Main ────────────────────────────────────────────────────────────────────

def direct_scene(idea: dict, script_text: str = "") -> dict:
    feature = idea.get("solution_feature", "WorkHive")
    if not script_text:
        script_text = _read_script(idea)
    narration = ""
    m = re.search(r"ElevenLabs Narration\s*\n+(.+?)(?:\n#|\Z)", script_text, re.S)
    if m:
        narration = m.group(1).strip()[:700]

    prompt = f"""You are an art director choosing an animated background for a short WorkHive marketing video.
Pick exactly ONE style that best fits this idea, and fill the content. Reply with STRICT JSON only.

IDEA
- Title: {idea.get('title','')}
- Type: {idea.get('type','')}
- Feature: {feature}
- Audience: {idea.get('audience') or idea.get('target_audience','')}
- Emotion: {idea.get('emotion','')}
- Hook: {idea.get('hook','')}
- Problem: {idea.get('problem','')}
NARRATION (excerpt): {narration}

STYLES
- "dashboard": live data-viz (bars/line/gauge). Best for analytics / OEE / monitoring.
- "kinetic": kinetic typography of punchy phrases. Best for storytelling / emotional.
- "infographic": animated stat cards with numbers. Best for educational / comparison / numbers.
- "mindmap": hub + connected nodes. Best for "how it all connects" / ecosystem.

Return JSON with ALL of these keys (fill every one, even if unused by the chosen style):
{{
  "style": "dashboard|kinetic|infographic|mindmap",
  "headline": "<= 6 words, punchy, no quotes",
  "subhead": "WorkHive · {feature}",
  "phrases": ["give 3-5 short phrases, <= 4 words each, from the hook/narration"],
  "stats": [{{"value":"87%","label":"<= 3 words","dir":"up|down|flat"}}, {{"value":"40%","label":"...","dir":"down"}}, {{"value":"24/7","label":"...","dir":"flat"}}],
  "nodes": ["give 3-5 short related concepts/features, 1-2 words each"]
}}
Give 2-4 stats (not just one) and 3-5 nodes/phrases so the visuals feel full. Numbers can be illustrative.
JSON:"""

    spec = {}
    try:
        from tools.video_idea_generator import ai_call
        raw = ai_call(prompt, high_quality=False)
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
        mjson = re.search(r"\{.*\}", raw, re.S)
        if mjson:
            spec = json.loads(mjson.group(0))
    except Exception as exc:
        print(f"  [scene-director] AI pick failed ({exc}); using rules fallback")

    return _coerce(spec if isinstance(spec, dict) else {}, idea)


if __name__ == "__main__":
    import sys
    BACKLOG = Path(".tmp/video_ideas_backlog.json")
    idea_id = sys.argv[1] if len(sys.argv) > 1 else None
    data = json.loads(BACKLOG.read_text(encoding="utf-8"))
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), data["ideas"][-1])
    print(json.dumps(direct_scene(idea), indent=2))
