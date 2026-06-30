"""
storyboard.py — the narration-derived STORYBOARD that drives BOTH the animated
background AND the screen-recorded UI journey, so every video tracks what the
narration is actually saying instead of being two canned tracks glued together.

The production script (.tmp/video_scripts/idea_xxx.md) already contains the
journey, beat by beat: a Hook, a Problem Scene (several SHOTs), a Solution Reveal
(several SHOTs that NAME the features the narration walks through), and a CTA —
each beat carrying its own NARRATION line and a punchy TEXT OVERLAY. This module
parses those beats into an ordered list of timed segments and, for each beat,
decides:

  • style   — which Remotion animation plays in the background (rotated so no two
              adjacent beats share a style → the "combination" you actually see,
              never one clip looped)
  • ui      — which WorkHive page/feature the UI journey should be on for that
              beat (detected from the feature names the narration mentions)
  • seconds / frames — the beat's slice of the narration's running time, so the
              background sequence and the UI journey both line up with the audio

Public:
    build_storyboard(idea: dict, narration_path: Path | None = None) -> dict
        → {idea_id, total_seconds, fps, segments: [ {section, narration, overlay,
            seconds, frames, style, headline, subhead, phrases[], stats[], nodes[],
            ui: {feature, journey, action}} ]}

The same dict feeds:
    render_remotion_scene.render_storyboard_scene()  (background)
    ui_recorder.record_journey()                     (UI journey)
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Windows consoles default to cp1252 and choke on the · / — separators in the
# CLI summary; force UTF-8 with a tolerant handler so a print never crashes.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FPS = 30
STYLES = ["kinetic", "dashboard", "infographic", "mindmap"]

# ── Feature detection: narration phrase → WorkHive journey key ────────────────
# Keys match ui_recorder's JOURNEY_STEPS / DEMOS so the recorder can drive them.
# Order matters: earlier, more-specific patterns win.
FEATURE_KEYWORDS: list[tuple[str, str, str]] = [
    # (regex, journey_key, human feature label)
    (r"shift\s*handover|handover\s*report|next shift", "shift_handover", "Shift Handover Report"),
    (r"ai (maintenance )?assistant|ai insight|ask the ai|chatbot", "ai_assistant", "AI Maintenance Assistant"),
    (r"logbook|record (every )?(repair|failure|fix)|log (it|every)", "logbook", "Maintenance Logbook"),
    (r"pm (checklist|scheduler)|preventive maintenance|\bpm\b", "pm_checklist", "PM Checklist"),
    (r"inventory|stock|spare part|reorder", "inventory", "Inventory Management"),
    (r"predictive|failure risk|predict (a )?failure|risk score", "predictive", "Predictive Analytics"),
    (r"analytics|oee|downtime|mtbf|kpi", "analytics", "Analytics & OEE Dashboard"),
    (r"skill matrix|who'?s qualified|competenc|certif", "skill_matrix", "Skill Matrix"),
    (r"marketplace|buy|sell|listing", "marketplace", "Marketplace"),
    (r"community|forum|ask (the )?(network|community)", "community", "Community Forum"),
    (r"day ?planner|dilo|wilo|plan (the|your) day", "day_planner", "Day Planner"),
    (r"asset (hub|brain)|asset 360|iso 14224", "asset_brain", "Asset Brain"),
    (r"shift brain|shift plan", "shift_brain", "Shift Brain"),
    (r"achievement|badge|xp|level up|gamif", "achievements", "Achievements"),
    (r"alert hub|one inbox|alert center|notification", "alert_hub", "Alert Hub"),
    (r"ph industry|benchmark|industry average|philippine industry", "ph_intelligence", "PH Industry Intelligence"),
    (r"integration|sap|maximo|cmms|webhook|import", "integrations", "CMMS Integrations"),
    (r"project (manager|overhaul)|shutdown|capex", "project_manager", "Project Manager"),
    (r"audit log|compliance|regulator|traceab", "audit_log", "Audit Log & Compliance"),
    (r"dashboard|supervisor|whole plant|at a glance", "hive_dashboard", "Hive Dashboard"),
    (r"engineering (design|calc)|pump sizing|tdh|standard", "engineering_calc", "Engineering Design Calculator"),
    (r"resume|cv|curriculum vitae|ats|job applic|portfolio", "resume_builder", "Resume Builder"),
]

# Feature display name → journey key (for the idea's primary solution_feature).
FEATURE_NAME_TO_KEY = {
    "Maintenance Logbook": "logbook",
    "Shift Handover Report": "shift_handover",
    "AI Maintenance Assistant": "ai_assistant",
    "PM Checklist": "pm_checklist",
    "Inventory Management": "inventory",
    "Predictive Analytics": "predictive",
    "Analytics & OEE Dashboard": "analytics",
    "Skill Matrix": "skill_matrix",
    "Marketplace": "marketplace",
    "Community Forum": "community",
    "Day Planner": "day_planner",
    "Asset Brain": "asset_brain",
    "Shift Brain": "shift_brain",
    "Achievements": "achievements",
    "Alert Hub": "alert_hub",
    "PH Industry Intelligence": "ph_intelligence",
    "CMMS Integrations": "integrations",
    "Project Manager": "project_manager",
    "Audit Log & Compliance": "audit_log",
    "Hive Dashboard": "hive_dashboard",
    "Engineering Design Calculator": "engineering_calc",
    "Resume Builder": "resume_builder",
}

# Journey keys whose narrative is a "how it all connects" ecosystem story —
# these bias the background toward the mindmap style.
_ECOSYSTEM_KEYS = {"hive_dashboard", "asset_brain", "project_manager", "integrations", "shift_brain"}
_DATA_KEYS = {"analytics", "predictive", "ph_intelligence", "alert_hub"}


# ── Script parsing ────────────────────────────────────────────────────────────

_SECTION_HEADERS = [
    (re.compile(r"^#+\s*hook", re.I), "hook"),
    (re.compile(r"^#+\s*problem", re.I), "problem"),
    (re.compile(r"^#+\s*solution", re.I), "solution"),
    (re.compile(r"^#+\s*(cta|call to action)", re.I), "cta"),
]
# Any other `## ` heading (AI Video Generation Prompts, ElevenLabs Narration,
# Music Direction, 15-Second Cut, …) ends the beat region.
_ANY_H2 = re.compile(r"^#{1,3}\s+\S")
_RANGE = re.compile(r"\((\d+)\s*-\s*(\d+)\s*s\)")
_FIELD = re.compile(r"^\*\*([A-Z][A-Z /0-9]+?):\*\*\s*(.*)$")


def _unquote(s: str) -> str:
    return s.strip().strip('"').strip("'").strip()


def _section_of(header_line: str) -> str | None:
    for rx, name in _SECTION_HEADERS:
        if rx.match(header_line.strip()):
            return name
    return None


def parse_script_beats(script_text: str) -> list[dict]:
    """Walk the script line by line, emitting one beat per NARRATION line within
    the Hook / Problem / Solution / CTA sections. Each beat carries the most
    recent SHOT description, its narration, and its TEXT OVERLAY / CTA button."""
    beats: list[dict] = []
    cur_section: str | None = None
    section_range: dict[str, tuple[int, int]] = {}
    cur_shot = ""

    for raw in script_text.splitlines():
        line = raw.rstrip()
        if _ANY_H2.match(line):
            sect = _section_of(line)
            cur_section = sect
            cur_shot = ""
            if sect:
                m = _RANGE.search(line)
                if m:
                    section_range[sect] = (int(m.group(1)), int(m.group(2)))
            continue
        if cur_section is None:
            continue
        fm = _FIELD.match(line.strip())
        if not fm:
            continue
        key, val = fm.group(1).strip().upper(), _unquote(fm.group(2))
        if key.startswith("SHOT"):
            cur_shot = val
        elif key == "NARRATION":
            if val:
                beats.append({
                    "section": cur_section, "shot": cur_shot,
                    "narration": val, "overlay": "",
                })
        elif key in ("TEXT OVERLAY", "CTA BUTTON TEXT", "TEXT", "OVERLAY"):
            if beats and beats[-1]["section"] == cur_section and not beats[-1]["overlay"]:
                beats[-1]["overlay"] = val

    return beats, section_range


# ── Per-beat enrichment ───────────────────────────────────────────────────────

def _detect_feature(beat: dict) -> tuple[str | None, str | None]:
    """Return (journey_key, human_label) for the feature this beat references,
    scanning shot + narration + overlay. None if the beat names no feature."""
    hay = " ".join((beat.get("shot", ""), beat.get("narration", ""), beat.get("overlay", ""))).lower()
    for rx, key, label in FEATURE_KEYWORDS:
        if re.search(rx, hay):
            return key, label
    return None, None


def _short_phrases(beat: dict) -> list[str]:
    """2–4 punchy phrases (≤4 words) for the kinetic style, led by the overlay."""
    out: list[str] = []
    if beat.get("overlay"):
        out.append(beat["overlay"][:42])
    # chunk the narration into short clauses
    clauses = re.split(r"[.,!?]\s*", beat.get("narration", ""))
    for c in clauses:
        words = c.strip().split()
        if 1 <= len(words) <= 5:
            out.append(" ".join(words)[:42])
        if len(out) >= 4:
            break
    seen, uniq = set(), []
    for p in out:
        k = p.lower()
        if p and k not in seen:
            seen.add(k); uniq.append(p)
    return uniq[:4] or [beat.get("narration", "WorkHive")[:42]]


def _beat_stats(beat: dict) -> list[dict]:
    """Pull illustrative stat cards. Prefer real numbers in the copy; else defaults."""
    hay = " ".join((beat.get("narration", ""), beat.get("overlay", "")))
    nums = re.findall(r"(\d+(?:\.\d+)?\s*(?:%|x|/\d+|hrs?|min|days?))", hay, re.I)
    if nums:
        stats = []
        for n in nums[:3]:
            stats.append({"value": re.sub(r"\s+", "", n)[:8], "label": "from your plant", "dir": "up"})
        return stats
    return [
        {"value": "100%", "label": "Free to start", "dir": "up"},
        {"value": "24/7", "label": "Always on", "dir": "flat"},
        {"value": "1", "label": "Place for it all", "dir": "up"},
    ]


def _beat_nodes(primary_label: str, beat: dict) -> list[str]:
    key, label = _detect_feature(beat)
    hub = (label or primary_label or "WorkHive").split("(")[0].strip()
    sibs = ["Logbook", "PM", "Inventory", "Alerts", "Analytics"]
    nodes = [hub] + [s for s in sibs if s.lower() not in hub.lower()]
    return nodes[:5]


def _base_style(beat: dict) -> str:
    sect = beat["section"]
    key, _ = _detect_feature(beat)
    if sect == "hook":
        return "kinetic"
    if sect == "cta":
        return "kinetic"
    if sect == "problem":
        # alternate story / cost-of-pain numbers
        return "infographic" if re.search(r"\d", beat.get("narration", "") + beat.get("overlay", "")) else "kinetic"
    # solution — pick by what the named feature is about
    if key in _DATA_KEYS:
        return "dashboard"
    if key in _ECOSYSTEM_KEYS:
        return "mindmap"
    if re.search(r"\d+\s*%|\bnumbers?\b|compare|benchmark", (beat.get("narration", "") + beat.get("overlay", "")).lower()):
        return "infographic"
    return "dashboard"


def _enforce_variety(styles: list[str]) -> list[str]:
    """No two adjacent beats share a style → the visible 'combination'."""
    out = list(styles)
    for i in range(1, len(out)):
        if out[i] == out[i - 1]:
            cyc = STYLES.index(out[i - 1])
            for step in range(1, len(STYLES)):
                cand = STYLES[(cyc + step) % len(STYLES)]
                if cand != out[i - 1] and (i + 1 >= len(out) or cand != out[i + 1]):
                    out[i] = cand
                    break
    return out


# ── Duration distribution ─────────────────────────────────────────────────────

def _narration_seconds(narration_path: Path | None) -> float | None:
    if not narration_path:
        return None
    try:
        from tools.video_assembler import get_duration
        d = get_duration(Path(narration_path))
        return d if d and d > 1 else None
    except Exception:
        return None


def _distribute_durations(beats: list[dict], total: float) -> list[float]:
    """Split `total` seconds across beats, weighted by narration word count,
    with a floor so even a 2-word overlay stays readable."""
    weights = [max(2, len((b.get("narration") or b.get("overlay") or "x").split())) for b in beats]
    wsum = sum(weights) or 1
    MIN = 2.0
    secs = [max(MIN, total * w / wsum) for w in weights]
    # rescale so the floor doesn't push the sum past `total`
    s = sum(secs)
    if s > 0:
        secs = [x * total / s for x in secs]
    return secs


# ── Public builder ────────────────────────────────────────────────────────────

def build_storyboard(idea: dict, narration_path: Path | None = None,
                     script_text: str | None = None) -> dict:
    primary_label = (idea.get("solution_feature") or "WorkHive").strip()
    primary_key = FEATURE_NAME_TO_KEY.get(primary_label)

    if script_text is None:
        sf = idea.get("script_file")
        script_text = ""
        if sf and Path(sf).exists():
            script_text = Path(sf).read_text(encoding="utf-8")

    beats, section_range = parse_script_beats(script_text or "")

    # Fallback: no parseable script → one beat per the primary feature.
    if not beats:
        beats = [{"section": "solution", "shot": "", "overlay": primary_label,
                  "narration": idea.get("hook") or idea.get("title") or primary_label}]

    # total runtime: prefer the real narration audio; else the script's last
    # time-range end; else 60s.
    total = _narration_seconds(narration_path)
    if total is None:
        ends = [rng[1] for rng in section_range.values()]
        total = float(max(ends)) if ends else 60.0

    secs = _distribute_durations(beats, total)

    # styles with adjacency variety enforced
    styles = _enforce_variety([_base_style(b) for b in beats])

    segments: list[dict] = []
    frame_acc = 0
    target_frames = round(total * FPS)
    for i, (beat, sec, style) in enumerate(zip(beats, secs, styles)):
        frames = max(FPS, round(sec * FPS))  # ≥1s of frames
        key, label = _detect_feature(beat)
        # hook/problem/cta beats that name no feature: hold on the primary feature
        if not key:
            key, label = primary_key, primary_label
        action = "demo" if (beat["section"] == "solution" and key == primary_key and i == _first_solution_idx(beats)) else "visit"
        # ≤7 words (kinetic-readable on a muted feed), never ending mid-clause.
        headline = _clamp_headline(beat.get("overlay") or beat.get("narration") or primary_label)
        # Feature name only — the scene already shows the WorkHive wordmark
        # (was "WorkHive · X": the brand appeared 4× in one frame).
        subhead = (label or primary_label)[:42]
        segments.append({
            "i": i,
            "section": beat["section"],
            "narration": beat["narration"],
            "overlay": beat.get("overlay", ""),
            "seconds": round(sec, 2),
            "frames": frames,
            "style": style,
            "headline": headline,
            "subhead": subhead,
            "phrases": _short_phrases(beat),
            "stats": _beat_stats(beat),
            "nodes": _beat_nodes(primary_label, beat),
            "ui": {"feature": label or primary_label, "journey": key, "action": action},
        })
        frame_acc += frames

    # nudge the last segment so total frames matches the narration exactly
    if segments and target_frames > 0:
        drift = target_frames - frame_acc
        segments[-1]["frames"] = max(FPS, segments[-1]["frames"] + drift)

    # ABCD enforcement (Creative Quality Gate): ≤3s pattern-interrupt hook with
    # 2+ shots in the first 5s, and a guaranteed branded CTA end card. Operates
    # on frames only — the narration audio remains the master clock.
    segments = _enforce_abcd(segments, primary_label)

    return {
        "idea_id": idea.get("id"),
        "title": idea.get("title"),
        "primary_feature": primary_label,
        "primary_journey": primary_key,
        "fps": FPS,
        "total_seconds": round(total, 2),
        "total_frames": sum(s["frames"] for s in segments),
        "segments": segments,
    }


def _first_solution_idx(beats: list[dict]) -> int:
    for i, b in enumerate(beats):
        if b["section"] == "solution":
            return i
    return -1


# ── ABCD enforcement (research-backed structure, measured by the gate) ─────────
# Google ABCD: 2+ shots in the first 5s, brand early, a clear Direct/CTA close.
# 3-second-hook research: viewers who survive 3s are 65% likelier to reach 10s.

_HOOK_PUNCH_S = 2.7      # the pattern-interrupt punch length
_CTA_CARD_S = 3.0        # the branded end card length


_PUNCH_TRAILING_STOP = {"and", "or", "the", "a", "an", "to", "of", "for", "with", "but", "your", "in", "on"}


def _clamp_headline(text: str, max_words: int = 7) -> str:
    """≤max_words, trailing connectives trimmed (Creative Gate kinetic_length)."""
    words = (text or "WorkHive").strip().split()[:max_words]
    while words and words[-1].lower().strip(".,!?") in _PUNCH_TRAILING_STOP:
        words.pop()
    return " ".join(words)[:60].strip() or "WorkHive"


def _punch_line(seg: dict) -> str:
    """A tight ≤5-word cut of the hook line for the 3-second punch. Trailing
    connectives are trimmed so the punch never ends mid-clause ("…time and")."""
    src = (seg.get("overlay") or seg.get("headline") or "WorkHive").strip()
    words = src.split()[:5]
    while words and words[-1].lower().strip(".,!?") in _PUNCH_TRAILING_STOP:
        words.pop()
    return " ".join(words)[:42].strip() or "WorkHive"


def _other_style(avoid: set) -> str:
    for s in STYLES:
        if s not in avoid:
            return s
    return STYLES[0]


def _enforce_abcd(segments: list[dict], primary_label: str) -> list[dict]:
    """Post-process the beat list so EVERY video meets the ABCD floor:

    1. HOOK: if the opening hook beat runs past ~3.5s, split it into a ≤3s
       pattern-interrupt punch (tight line, different style) + the remainder —
       giving 2+ shots inside the first 5 seconds.
    2. CTA: if the script produced no CTA beat, carve the last ~3s into a
       branded end card (Direct) — never ship without a close.
    Frame totals are preserved exactly (narration = master clock)."""
    if not segments:
        return segments

    out = list(segments)

    # 1 — hook split
    first = out[0]
    if first.get("section") == "hook" and first["frames"] > round(3.5 * FPS):
        punch_frames = round(_HOOK_PUNCH_S * FPS)
        rest_frames = first["frames"] - punch_frames
        if rest_frames >= FPS:
            rest_style = _other_style({first["style"], out[1]["style"] if len(out) > 1 else ""})
            punch = dict(first)
            punch.update({
                "frames": punch_frames, "seconds": round(punch_frames / FPS, 2),
                "headline": _punch_line(first),
                "phrases": [_punch_line(first)],
            })
            rest = dict(first)
            rest.update({
                "frames": rest_frames, "seconds": round(rest_frames / FPS, 2),
                "style": rest_style,
            })
            out[0:1] = [punch, rest]

    # 2 — guaranteed CTA end card
    if not any(s.get("section") == "cta" for s in out):
        last = out[-1]
        cta_frames = round(_CTA_CARD_S * FPS)
        if last["frames"] >= cta_frames + FPS:
            last["frames"] -= cta_frames
            last["seconds"] = round(last["frames"] / FPS, 2)
        else:
            cta_frames = last["frames"]
            out.pop()
        out.append({
            "i": -1, "section": "cta",
            "narration": last.get("narration", ""),
            "overlay": "Free at workhiveph.com",
            "seconds": round(cta_frames / FPS, 2), "frames": cta_frames,
            "style": "kinetic",
            "headline": "Free at workhiveph.com",
            "subhead": primary_label[:42],
            "phrases": ["Free forever", "workhiveph.com"],
            "stats": [{"value": "100%", "label": "Free to start", "dir": "up"}],
            "nodes": [primary_label],
            "ui": dict(last.get("ui", {"feature": primary_label, "journey": None, "action": "visit"})),
        })

    for i, s in enumerate(out):
        s["i"] = i
    return out


# ── Drift guard ───────────────────────────────────────────────────────────────

def self_test() -> int:
    """Catalog drift guard for the feature-detection maps.

    The narration regexes and the Shift-Handover-vs-Logbook label distinction are
    CURATED on purpose (the catalog collapses 'shift_handover' into the Logbook
    feature — handover has no standalone page — so the maps legitimately carry a
    finer label than the catalog; a naive derive would lose it). What MUST stay
    catalog-true are the JOURNEY KEYS: each one drives ui_recorder to a real route,
    so a feature renamed/removed upstream must not leave a stale key here. This
    asserts every key still resolves via platform_catalog.build_journey_index() —
    turning the maps from a silent drift surface into a gated one.
    """
    import platform_catalog as pc
    fails = 0

    def ck(cond: bool, msg: str):
        nonlocal fails
        print(("  \033[92mPASS\033[0m  " if cond else "  \033[91mFAIL\033[0m  ") + msg)
        if not cond:
            fails += 1

    print("\n\033[1mstoryboard.py --self-test (catalog drift guard)\033[0m")
    print("=" * 55)
    valid = set(pc.build_journey_index())
    kw_bad = sorted({key for _, key, _ in FEATURE_KEYWORDS if key not in valid})
    ck(not kw_bad, f"all {len(FEATURE_KEYWORDS)} FEATURE_KEYWORDS journey keys resolve to the live catalog"
       + (f" — STALE: {kw_bad}" if kw_bad else ""))
    n2k_bad = sorted({v for v in FEATURE_NAME_TO_KEY.values() if v not in valid})
    ck(not n2k_bad, f"all {len(FEATURE_NAME_TO_KEY)} FEATURE_NAME_TO_KEY journey keys resolve to the live catalog"
       + (f" — STALE: {n2k_bad}" if n2k_bad else ""))
    print("=" * 55)
    print("\033[92m  self-test PASS\033[0m\n" if not fails else f"\033[91m  self-test FAIL — {fails} check(s)\033[0m\n")
    return 1 if fails else 0


# ── CLI (verification) ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Build a narration storyboard for an idea")
    ap.add_argument("idea_id", nargs="?", help="Idea ID (defaults to the last in the backlog)")
    ap.add_argument("--voice", default="james")
    ap.add_argument("--brief", action="store_true", help="Print a one-line-per-beat summary")
    ap.add_argument("--self-test", action="store_true",
                    help="Catalog drift guard: every journey key still resolves to a live catalog route")
    args = ap.parse_args()

    if args.self_test:
        raise SystemExit(self_test())

    backlog = json.loads((_ROOT / ".tmp/video_ideas_backlog.json").read_text(encoding="utf-8"))
    idea = next((i for i in backlog["ideas"] if i["id"] == args.idea_id), backlog["ideas"][-1])
    narr = _ROOT / ".tmp/voice_files" / f"{idea['id']}_{args.voice}.mp3"
    sb = build_storyboard(idea, narration_path=narr if narr.exists() else None)

    if args.brief:
        print(f"\n{sb['idea_id']} · {sb['title']}  ·  {sb['total_seconds']}s / {sb['total_frames']}f "
              f"· primary={sb['primary_journey']}")
        for s in sb["segments"]:
            print(f"  [{s['section']:<8}] {s['seconds']:>5.1f}s  {s['style']:<11} "
                  f"ui={s['ui']['journey'] or '-':<14} | {s['headline']}")
    else:
        print(json.dumps(sb, indent=2, ensure_ascii=False))
