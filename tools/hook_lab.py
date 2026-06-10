#!/usr/bin/env python3
"""
hook_lab.py — Hook A/B for the video pipeline (test the hook, don't guess).
===========================================================================
The 3-second hook is the highest-leverage element of a marketing video
(surviving 3s → 65% likelier to reach 10s; weak hooks get reach throttled).
This lab takes a generated script, produces 2 challenger hooks in different
pattern-interrupt registers (question / stat / bold claim), has the free-tier
judge score all 3 for scroll-stopping power, and rewrites the script's Hook
section with the winner. Fail-soft: any error keeps the original hook.

Used by the produce pipeline (_stage_script) and the /script route. Disable
with HOOK_AB=0.

CLI:
    python tools/hook_lab.py <idea_id>      # improve that idea's script on disk
    python tools/hook_lab.py --self-test    # offline: extraction + rewrite logic
"""
from __future__ import annotations
import io
import json
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"

_HOOK_SECTION = re.compile(r"(^#{1,3}\s*Hook.*?$)(.*?)(?=^#{1,3}\s|\Z)", re.M | re.S | re.I)
_NARR = re.compile(r"^(\*\*NARRATION:\*\*\s*)(.+)$", re.M)
_OVERLAY = re.compile(r"^(\*\*TEXT OVERLAY:\*\*\s*)(.+)$", re.M)


def extract_hook(script_text: str) -> dict | None:
    """Pull the current hook narration + overlay out of the script's Hook section."""
    m = _HOOK_SECTION.search(script_text)
    if not m:
        return None
    body = m.group(2)
    nm = _NARR.search(body)
    om = _OVERLAY.search(body)
    if not nm:
        return None
    return {
        "narration": nm.group(2).strip().strip('"'),
        "overlay": (om.group(2).strip().strip('"') if om else ""),
    }


def replace_hook(script_text: str, narration: str, overlay: str) -> str:
    """Rewrite ONLY the Hook section's narration + overlay lines."""
    m = _HOOK_SECTION.search(script_text)
    if not m:
        return script_text
    body = m.group(2)
    new_body = _NARR.sub(lambda mm: f'{mm.group(1)}"{narration}"', body, count=1)
    if overlay:
        if _OVERLAY.search(new_body):
            new_body = _OVERLAY.sub(lambda mm: f'{mm.group(1)}"{overlay}"', new_body, count=1)
    return script_text[:m.start(2)] + new_body + script_text[m.end(2):]


def _gen_variants(idea: dict, current: dict) -> list[dict]:
    from ai_chain import call_ai_chain
    prompt = f"""You write scroll-stopping 3-second hooks for industrial-worker video ads
(WorkHive: free maintenance software for Filipino plants). Current hook for the idea
"{idea.get('title','')}" (feature: {idea.get('solution_feature','')}, pain: {idea.get('problem','')}):
  NARRATION: "{current['narration']}"
  OVERLAY:   "{current['overlay']}"

Write 2 CHALLENGER hooks in DIFFERENT pattern-interrupt registers (pick 2 of: a sharp
question, a surprising stat/number, a bold claim). Rules: plain simple English, narration
max 10 words, overlay max 6 words, a plant worker must FEEL it instantly.

Return ONLY JSON: [{{"narration":"...","overlay":"..."}},{{"narration":"...","overlay":"..."}}]"""
    out = call_ai_chain(prompt, max_tokens=300, json_mode=False) or ""
    m = re.search(r"\[.*\]", out, re.DOTALL)
    if not m:
        return []
    arr = json.loads(m.group())
    return [{"narration": str(v.get("narration", "")).strip()[:120],
             "overlay": str(v.get("overlay", "")).strip()[:60]}
            for v in arr if v.get("narration")][:2]


def _judge(idea: dict, hooks: list[dict]) -> list[int]:
    """Score each hook 0-100 for scroll-stopping power. One small call; the
    candidate list is tiny (3) so index mapping is safe here."""
    from ai_chain import call_ai_chain
    listing = "\n".join(f"{i}. NARRATION: \"{h['narration']}\" | OVERLAY: \"{h['overlay']}\""
                        for i, h in enumerate(hooks))
    prompt = f"""Rate each hook 0-100 for SCROLL-STOPPING power for a Filipino plant worker
seeing a video ad (feature: {idea.get('solution_feature','')}). Reward: specific pain,
surprise, curiosity, numbers. Punish: generic marketing speak, vagueness.

{listing}

Return ONLY JSON: [{{"i":0,"score":<int>}},{{"i":1,"score":<int>}},{{"i":2,"score":<int>}}]"""
    out = call_ai_chain(prompt, max_tokens=160, json_mode=False) or ""
    m = re.search(r"\[.*\]", out, re.DOTALL)
    scores = [0] * len(hooks)
    if m:
        for row in json.loads(m.group()):
            i = int(row.get("i", -1))
            if 0 <= i < len(hooks):
                scores[i] = int(row.get("score", 0))
    return scores


def improve_hook(script_text: str, idea: dict) -> tuple[str, dict]:
    """A/B the hook; return (possibly-rewritten script, report). Fail-soft."""
    report = {"ran": False, "winner": "original", "candidates": []}
    try:
        current = extract_hook(script_text)
        if not current:
            report["note"] = "no hook section found"
            return script_text, report
        variants = _gen_variants(idea, current)
        if not variants:
            report["note"] = "no variants generated"
            return script_text, report
        hooks = [current] + variants
        scores = _judge(idea, hooks)
        report.update({
            "ran": True,
            "candidates": [{"narration": h["narration"], "overlay": h["overlay"], "score": s}
                           for h, s in zip(hooks, scores)],
        })
        best = max(range(len(hooks)), key=lambda i: scores[i])
        if best != 0 and scores[best] > scores[0]:
            w = hooks[best]
            report["winner"] = f"variant_{best}"
            return replace_hook(script_text, w["narration"], w["overlay"]), report
        return script_text, report
    except Exception as e:  # noqa: BLE001
        report["note"] = f"fail-soft: {str(e)[:120]}"
        return script_text, report


def self_test() -> int:
    fails = []
    script = """# T

## Hook (0-5s)
**SHOT:** [worker stares at machine]
**NARRATION:** "Old hook line here."
**TEXT OVERLAY:** "Old overlay"

## Problem Scene (5-30s)
**SHOT 1:** [x]
**NARRATION:** "Problem line."
"""
    cur = extract_hook(script)
    if not cur or cur["narration"] != "Old hook line here.":
        fails.append(f"extract_hook wrong: {cur}")
    out = replace_hook(script, "New hook!", "New overlay")
    if '"New hook!"' not in out or '"New overlay"' not in out:
        fails.append("replace_hook did not rewrite")
    if "Problem line." not in out:
        fails.append("replace_hook damaged other sections")
    if extract_hook(out)["narration"] != "New hook!":
        fails.append("round-trip failed")
    if fails:
        print(f"{RED}{BOLD}SELF-TEST FAILED:{RESET}")
        for f in fails:
            print("  x", f)
        return 1
    print(f"{GREEN}{BOLD}SELF-TEST PASSED{RESET} — hook extraction + surgical rewrite work.")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if len(sys.argv) > 1:
        from video_idea_generator import load_backlog
        idea = next((i for i in load_backlog()["ideas"] if i["id"] == sys.argv[1]), None)
        if not idea or not idea.get("script_file"):
            sys.exit(f"no script for {sys.argv[1]}")
        p = Path(idea["script_file"])
        text, report = improve_hook(p.read_text(encoding="utf-8"), idea)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if report.get("winner", "original") != "original":
            p.write_text(text, encoding="utf-8")
            print(f"script updated -> {p}")
    else:
        print("usage: python tools/hook_lab.py <idea_id> | --self-test")
