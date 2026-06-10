#!/usr/bin/env python3
"""
video_quality_critic.py — Creative Quality Gate, Tier-2 (the opt-in critic).
============================================================================
The deterministic rubric (video_quality_gate.py) is the cheap, reliable floor —
it can verify a hook BEAT exists, but not whether the hook is GOOD. This adds a
free-tier LLM critic that reads the script + storyboard beats and scores the
qualitative craft the way a creative director would, against the same research:

  • hook strength    — does the first 3s stop the scroll (pattern-interrupt,
                       curiosity, a recognizable plant-floor pain)?
  • abcd coverage    — Attract / Brand / Connect / Direct present and clear?
  • mute readability — does the on-screen text carry the whole story on mute
                       (85% of social video is watched silent)?

Returns {score 0-100, hook, abcd, mute, summary, fixes[]}. Opt-in (the gate calls
it only with --critic / use_critic=True) and graceful — if no model is reachable
it reports available:false rather than failing the gate. Same Tier-1/Tier-2
pattern as the Content Grounding Gate's faithfulness judge.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _beats_brief(ctx: dict) -> str:
    lines = []
    for s in ctx.get("segments", [])[:12]:
        lines.append(f"  [{s.get('section')}] {s.get('seconds')}s · headline=\"{s.get('headline','')}\" "
                     f"· narration=\"{(s.get('narration','') or '')[:90]}\"")
    return "\n".join(lines)


def critique(ctx: dict) -> dict:
    try:
        try:
            from ai_chain import call_ai_chain
        except ImportError:
            from tools.ai_chain import call_ai_chain
    except Exception as e:  # noqa: BLE001
        return {"available": False, "note": f"no ai_chain ({e})"}

    idea = ctx.get("idea", {})
    prompt = f"""You are a senior performance-marketing creative director. Score this WorkHive
ad video against research-backed best practice (Google ABCD; the 3-second hook;
85% of social video watched on MUTE). WorkHive = free industrial maintenance
software for Filipino plant workers. Be specific and tough but fair.

VIDEO: "{idea.get('title','')}"  ({ctx.get('total_seconds','?')}s, feature: {idea.get('solution_feature','')})
Beats (section · seconds · on-screen headline · narration):
{_beats_brief(ctx)}

Score 0-100 on each, judging ONLY what the beats above show:
  hook  — does the first beat stop the scroll in 3s (a sharp, specific plant-floor pain / pattern-interrupt)?
  abcd  — Attract + Brand (WorkHive shown early) + Connect (emotion/people) + Direct (clear CTA)?
  mute  — do the on-screen HEADLINES alone carry the story with the sound off?

Return ONLY JSON, no prose:
{{"hook": <int>, "abcd": <int>, "mute": <int>, "summary": "<one sentence>", "fixes": ["<short fix>", "<short fix>"]}}"""
    try:
        out = call_ai_chain(prompt, max_tokens=400, json_mode=False) or ""
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return {"available": False, "note": "no JSON from critic"}
        d = json.loads(m.group())
        sub = [int(d.get(k, 0)) for k in ("hook", "abcd", "mute")]
        score = round(sum(sub) / 3, 1)
        return {"available": True, "score": score,
                "hook": sub[0], "abcd": sub[1], "mute": sub[2],
                "summary": str(d.get("summary", ""))[:200],
                "fixes": [str(x)[:120] for x in (d.get("fixes") or [])][:4]}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "note": f"critic error: {str(e)[:120]}"}


if __name__ == "__main__":
    # quick manual: python tools/video_quality_critic.py <idea_id>
    if len(sys.argv) > 1:
        import video_quality_gate as vqg
        ctx = vqg._ctx_for_idea(sys.argv[1])
        print(json.dumps(critique(ctx), indent=2, ensure_ascii=False))
    else:
        print("usage: python tools/video_quality_critic.py <idea_id>")
