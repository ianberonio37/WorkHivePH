#!/usr/bin/env python3
"""
video_quality_gate.py — the Creative Quality Gate (the 4th sibling gate).
=========================================================================
Three gates already make WorkHive output TRUSTWORTHY:
  Mega Gate (release_gate.py)      → platform CODE is correct
  Companion Dev Tool               → AI BEHAVIOUR doesn't regress
  Content Grounding Gate           → outward CONTENT is TRUE (no invented claims)
This is the 4th: it scores whether a produced marketing video is GOOD — measured
against the research-backed creative playbook, not taste:

  • Google/YouTube ABCD (Attract·Brand·Connect·Direct): +30% short-term sales,
    +17% long-term brand; 2+ shots in first 5s; brand in first 5s; clear CTA.
  • The 3-second hook: watching the first 3s → 65% more likely to reach 10s;
    losing >25% early throttles reach.
  • Length: <1 min ≈ 52% engagement (the peak); sharp drop-off past 90s.
  • Silent-first: 85% of social video is watched on mute → the on-screen message
    must carry the story; captions ≥48px sans-serif.
  • Motion as punctuation: short kinetic headlines (3–7 words), style VARIETY
    (no single looped clip).

It scores a produced video from artefacts we already have — the narration-driven
storyboard (tools/storyboard.py), the script, and the assembled mp4 — with
deterministic checks first (cheap, reliable) and an opt-in critic second (the
same Tier-1/Tier-2 pattern as the Content Grounding Gate). 4-axis creative
scorecard: hook · structure · craft · brand. Forward-only; blocking checks gate
ship (no hook / no CTA / out-of-band length / no on-screen message).

CLI:
    python tools/video_quality_gate.py score <idea_id> [--critic]
    python tools/video_quality_gate.py --self-test
"""
from __future__ import annotations
import argparse
import io
import json
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

RUBRIC_PATH = ROOT / "video_quality_rubric.json"
REPORT_PATH = ROOT / "video_quality_report.json"
ASSEMBLED_DIR = ROOT / ".tmp" / "assembled_videos"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

# Length targets (seconds): organic ≤60 ideal, hard band [12, 75].
LEN_MIN, LEN_IDEAL_MAX, LEN_HARD_MAX = 12.0, 60.0, 75.0
HOOK_MAX_S = 6.0          # the hook beat should be short (≤~5s)
KINETIC_MAX_WORDS = 7     # short kinetic headline


# ── helpers ───────────────────────────────────────────────────────────────────

def _words(s: str) -> int:
    return len(re.findall(r"\b[\w']+\b", s or ""))


def _cumulative_starts(segs: list[dict]) -> list[float]:
    starts, acc = [], 0.0
    for s in segs:
        starts.append(acc)
        acc += float(s.get("seconds", 0))
    return starts


# ── the rubric (deterministic checks) ─────────────────────────────────────────
# Each check: id, axis, blocking, fn(ctx)->(passed: bool, detail: str)

def _c_hook_present(ctx):
    segs = ctx["segments"]
    if not segs:
        return False, "no segments"
    first = segs[0]
    ok = first.get("section") == "hook" and float(first.get("seconds", 99)) <= HOOK_MAX_S
    return ok, (f"first beat section='{first.get('section')}' @ {first.get('seconds')}s"
                + ("" if ok else " — needs a hook beat in the first ~5s"))


def _c_shots_first_5s(ctx):
    segs, starts = ctx["segments"], _cumulative_starts(ctx["segments"])
    in5 = [s for s, t in zip(segs, starts) if t < 5.0]
    distinct_styles = len({s.get("style") for s in in5})
    ok = len(in5) >= 2 or distinct_styles >= 2
    return ok, f"{len(in5)} beat(s)/{distinct_styles} style(s) in first 5s (ABCD wants 2+)"


def _c_hook_punchy(ctx):
    segs = ctx["segments"]
    if not segs:
        return False, "no segments"
    w = _words(segs[0].get("headline", ""))
    ok = 1 <= w <= 9
    return ok, f"hook headline = {w} words (want a tight, punchy line)"


def _c_structure_abcd(ctx):
    sections = {s.get("section") for s in ctx["segments"]}
    has = sections.intersection
    ok = "hook" in sections and bool(has({"problem", "solution"})) and "cta" in sections
    return ok, f"sections present: {sorted(sections)} (want hook + problem/solution + cta)"


def _c_cta_present(ctx):
    ok = any(s.get("section") == "cta" for s in ctx["segments"])
    return ok, "a CTA / end-card beat " + ("present" if ok else "is MISSING (Direct in ABCD)")


def _c_brand_in_5s(ctx):
    starts = _cumulative_starts(ctx["segments"])
    early = [s for s, t in zip(ctx["segments"], starts) if t < 5.0]
    blob = " ".join((s.get("overlay", "") + " " + s.get("subhead", "") + " "
                     + s.get("ui", {}).get("feature", "")) for s in early).lower()
    ok = "workhive" in blob or any(s.get("ui", {}).get("feature") for s in early)
    return ok, "brand/feature named in first 5s " + ("yes" if ok else "NO (Brand in ABCD)")


def _c_message_overlays(ctx):
    segs = ctx["segments"]
    if not segs:
        return False, "no segments"
    with_msg = sum(1 for s in segs if (s.get("headline") or s.get("overlay")))
    ok = with_msg == len(segs)
    return ok, f"{with_msg}/{len(segs)} beats carry an on-screen message (silent-first: every beat must)"


def _c_kinetic_length(ctx):
    segs = ctx["segments"]
    if not segs:
        return False, "no segments"
    short = sum(1 for s in segs if _words(s.get("headline", "")) <= KINETIC_MAX_WORDS)
    frac = short / len(segs)
    ok = frac >= 0.7
    return ok, f"{short}/{len(segs)} headlines ≤{KINETIC_MAX_WORDS} words ({frac*100:.0f}%; kinetic-friendly)"


def _c_style_variety(ctx):
    styles = [s.get("style") for s in ctx["segments"]]
    distinct = len(set(styles))
    ok = distinct >= 2
    return ok, f"{distinct} distinct background style(s) (no single looped clip)"


def _c_duration_band(ctx):
    d = ctx["total_seconds"]
    ok = LEN_MIN <= d <= LEN_HARD_MAX
    note = "" if d <= LEN_IDEAL_MAX else f" (>{LEN_IDEAL_MAX:.0f}s ideal cap; trim toward the ~52%-engagement sweet spot)"
    return ok, f"{d:.1f}s in band [{LEN_MIN:.0f},{LEN_HARD_MAX:.0f}]{note}"


def _c_brand_colors(ctx):
    """Opt-in frame sampling: do the rendered frames actually carry brand colour?
    Graceful SKIP when the mp4 / ffmpeg / PIL aren't available."""
    mp4 = ctx.get("mp4_path")
    if not mp4 or not Path(mp4).exists():
        return None, "no assembled mp4 to sample (skip)"
    try:
        import subprocess, tempfile
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ff = "ffmpeg"
        from PIL import Image
        td = Path(tempfile.mkdtemp())
        frame = td / "f.png"
        subprocess.run([ff, "-y", "-ss", "2", "-i", str(mp4), "-frames:v", "1",
                        "-vf", "scale=160:-1", str(frame)],
                       capture_output=True, timeout=30)
        if not frame.exists():
            return None, "frame extract failed (skip)"
        im = Image.open(frame).convert("RGB")
        px = list(im.getdata())
        def near(c, t, tol=60):
            return all(abs(a - b) <= tol for a, b in zip(c, t))
        orange = sum(1 for p in px if near(p, (247, 162, 27)))
        navy = sum(1 for p in px if near(p, (22, 32, 50), 50))
        frac = (orange + navy) / max(1, len(px))
        ok = frac >= 0.03
        return ok, f"brand-colour pixels (orange+navy) ≈ {frac*100:.1f}% of a sampled frame"
    except Exception as e:  # noqa: BLE001
        return None, f"frame check unavailable ({type(e).__name__}) — skip"


CHECKS = [
    {"id": "hook_present",     "axis": "hook",      "blocking": True,  "fn": _c_hook_present},
    {"id": "shots_first_5s",   "axis": "hook",      "blocking": False, "fn": _c_shots_first_5s},
    {"id": "hook_punchy",      "axis": "hook",      "blocking": False, "fn": _c_hook_punchy},
    {"id": "structure_abcd",   "axis": "structure", "blocking": True,  "fn": _c_structure_abcd},
    {"id": "cta_present",      "axis": "structure", "blocking": True,  "fn": _c_cta_present},
    {"id": "brand_in_5s",      "axis": "structure", "blocking": False, "fn": _c_brand_in_5s},
    {"id": "message_overlays", "axis": "craft",     "blocking": True,  "fn": _c_message_overlays},
    {"id": "kinetic_length",   "axis": "craft",     "blocking": False, "fn": _c_kinetic_length},
    {"id": "style_variety",    "axis": "craft",     "blocking": False, "fn": _c_style_variety},
    {"id": "duration_band",    "axis": "craft",     "blocking": True,  "fn": _c_duration_band},
    {"id": "brand_colors",     "axis": "brand",     "blocking": False, "fn": _c_brand_colors},
]
AXES = ["hook", "structure", "craft", "brand"]


def write_rubric() -> None:
    RUBRIC_PATH.write_text(json.dumps({
        "rubric": "video_quality (Creative Quality Gate)",
        "axes": AXES,
        "checks": [{"id": c["id"], "axis": c["axis"], "blocking": c["blocking"]} for c in CHECKS],
        "length_band": [LEN_MIN, LEN_IDEAL_MAX, LEN_HARD_MAX],
        "sources": ["Google ABCD (Think with Google)", "Wistia State of Video",
                    "Meta sound-off/caption guidance", "short-form 3s-hook research"],
    }, indent=2), encoding="utf-8")


# ── scoring ───────────────────────────────────────────────────────────────────

def score(ctx: dict) -> dict:
    rows, axis_hits = [], {a: [0, 0] for a in AXES}   # axis -> [passed, total(non-skip)]
    blocking_fails = []
    for c in CHECKS:
        passed, detail = c["fn"](ctx)
        status = "SKIP" if passed is None else ("PASS" if passed else "FAIL")
        rows.append({"check": c["id"], "axis": c["axis"], "blocking": c["blocking"],
                     "status": status, "detail": detail})
        if passed is None:
            continue
        axis_hits[c["axis"]][1] += 1
        if passed:
            axis_hits[c["axis"]][0] += 1
        elif c["blocking"]:
            blocking_fails.append(c["id"])

    axes = {a: (round(100 * h[0] / h[1], 1) if h[1] else None) for a, h in axis_hits.items()}
    scored = [v for v in axes.values() if v is not None]
    overall = round(sum(scored) / len(scored), 1) if scored else 0.0
    verdict = "BLOCK" if blocking_fails else ("PASS" if overall >= 70 else "WARN")
    return {
        "score": overall,
        "axes": axes,
        "verdict": verdict,
        "blocking_fails": blocking_fails,
        "checks": rows,
        "total_seconds": ctx.get("total_seconds"),
    }


def _latest_mp4(idea_id: str) -> Path | None:
    if not ASSEMBLED_DIR.exists():
        return None
    cands = sorted(ASSEMBLED_DIR.glob(f"{idea_id}_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def _ctx_for_idea(idea_id: str) -> dict:
    from video_idea_generator import load_backlog
    import storyboard as sb
    idea = next((i for i in load_backlog()["ideas"] if i["id"] == idea_id), None)
    if not idea:
        raise SystemExit(f"unknown idea {idea_id!r}")
    narr = ROOT / ".tmp" / "voice_files" / f"{idea_id}_james.mp3"
    script_text = ""
    if idea.get("script_file") and Path(idea["script_file"]).exists():
        script_text = Path(idea["script_file"]).read_text(encoding="utf-8")
    story = sb.build_storyboard(idea, narration_path=narr if narr.exists() else None, script_text=script_text)
    return {
        "idea": idea, "script_text": script_text, "story": story,
        "segments": story["segments"], "total_seconds": story["total_seconds"],
        "mp4_path": str(_latest_mp4(idea_id) or ""),
    }


def score_idea(idea_id: str, use_critic: bool = False) -> dict:
    ctx = _ctx_for_idea(idea_id)
    result = score(ctx)
    if use_critic:
        try:
            import video_quality_critic as vc  # C2 (optional)
            result["critic"] = vc.critique(ctx)
        except Exception as e:  # noqa: BLE001
            result["critic"] = {"available": False, "note": str(e)[:120]}
    result["idea_id"] = idea_id
    REPORT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


# ── pretty print ──────────────────────────────────────────────────────────────

def _print(result: dict) -> None:
    v = result["verdict"]
    col = {"PASS": GREEN, "WARN": YEL, "BLOCK": RED}[v]
    print(f"\n{BOLD}Creative Quality Gate — {result.get('idea_id','?')}{RESET}")
    print("=" * 66)
    for r in result["checks"]:
        tag = {"PASS": GREEN + "PASS" + RESET, "FAIL": RED + "FAIL" + RESET, "SKIP": "skip"}[r["status"]]
        b = " (blocking)" if r["blocking"] else ""
        print(f"  {tag}  {r['check']:<16}{b}")
        print(f"        {r['detail']}")
    print("-" * 66)
    print(f"  axes: " + " · ".join(f"{a} {result['axes'][a]}" for a in AXES if result['axes'][a] is not None))
    print(f"  {col}{BOLD}{v}{RESET}  creative score {result['score']}/100"
          + (f"  — blocking: {', '.join(result['blocking_fails'])}" if result['blocking_fails'] else ""))
    if result.get("critic", {}).get("score") is not None:
        print(f"  critic: {result['critic']['score']}/100 — {result['critic'].get('summary','')[:80]}")
    print()


# ── self-test (synthetic storyboards, no LLM/mp4) ─────────────────────────────

def self_test() -> int:
    def ok(label):  print(f"  {GREEN}PASS{RESET}  {label}")
    def bad(label): print(f"  {RED}FAIL{RESET}  {label}")
    print(f"\n{BOLD}video_quality_gate.py --self-test{RESET}")
    print("=" * 55)
    fails = 0

    def check(cond, label):
        nonlocal fails
        (ok if cond else bad)(label)
        if not cond:
            fails += 1

    good = {"total_seconds": 58.0, "mp4_path": "", "segments": [
        {"section": "hook", "seconds": 4, "style": "kinetic", "headline": "Machine down at 3am", "overlay": "Machine down at 3am", "subhead": "WorkHive", "ui": {"feature": "Logbook"}},
        {"section": "problem", "seconds": 14, "style": "dashboard", "headline": "No record, no clue", "overlay": "x", "subhead": "WorkHive", "ui": {"feature": "Logbook"}},
        {"section": "solution", "seconds": 26, "style": "infographic", "headline": "Log it in one tap", "overlay": "x", "subhead": "WorkHive", "ui": {"feature": "Logbook"}},
        {"section": "cta", "seconds": 14, "style": "mindmap", "headline": "Free at workhiveph.com", "overlay": "x", "subhead": "WorkHive", "ui": {"feature": "Logbook"}},
    ]}
    bad_sb = {"total_seconds": 190.0, "mp4_path": "", "segments": [
        {"section": "solution", "seconds": 190, "style": "kinetic",
         "headline": "This is an extremely long headline that nobody can read in time on a muted feed at all", "overlay": "", "subhead": "", "ui": {"feature": ""}},
    ]}

    g = score(good)
    b = score(bad_sb)
    check(g["verdict"] in ("PASS", "WARN") and not g["blocking_fails"],
          f"a well-formed ABCD storyboard passes (score {g['score']}, verdict {g['verdict']})")
    check(b["verdict"] == "BLOCK" and {"hook_present", "cta_present", "duration_band"} <= set(b["blocking_fails"]),
          f"a bad storyboard BLOCKS on hook+cta+duration (fails: {b['blocking_fails']})")
    check(g["score"] > b["score"], f"good scores higher than bad ({g['score']} > {b['score']})")
    check(all(a in g["axes"] for a in AXES), "4 creative axes reported")
    check(g["axes"]["craft"] is not None and b["axes"]["craft"] is not None, "craft axis computed both ways")

    write_rubric()
    check(RUBRIC_PATH.exists(), "rubric manifest written")

    print("=" * 55)
    if fails == 0:
        print(f"{GREEN}{BOLD}  self-test PASS{RESET}\n")
    else:
        print(f"{RED}{BOLD}  self-test FAIL — {fails} check(s){RESET}\n")
    return 1 if fails else 0


def _latest_idea_id() -> str | None:
    """The idea behind the most recently assembled video (for the cockpit card)."""
    if not ASSEMBLED_DIR.exists():
        return None
    vids = sorted(ASSEMBLED_DIR.glob("idea_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    for v in vids:
        m = re.match(r"(idea_\d+)_", v.name)
        if m:
            return m.group(1)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Creative Quality Gate — score a produced marketing video.")
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    ps = sub.add_parser("score")
    ps.add_argument("idea_id", nargs="?", default=None)
    ps.add_argument("--latest", action="store_true", help="score the most recently assembled video")
    ps.add_argument("--critic", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.cmd == "score":
        idea_id = args.idea_id or (_latest_idea_id() if args.latest else None)
        if not idea_id:
            print("pass an idea_id or --latest (no assembled videos found)")
            return 1
        write_rubric()
        result = score_idea(idea_id, use_critic=args.critic)
        _print(result)
        return 0 if result["verdict"] != "BLOCK" else 1
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
