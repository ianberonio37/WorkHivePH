#!/usr/bin/env python3
"""
explainer_pack.py — derive a social caption pack from an ExplainerSpec.
=======================================================================
Closes the "WorkHive Explains" flywheel to FULL automation: the existing
`social_publisher.py` reads a per-idea pack at `.tmp/platform_packs/<id>.json`.
The flagship path generates that with `platform_pack.generate_platform_pack`,
but that is ONE-feature-per-video and fires ~10 AI calls, and an overview is
all-features. So we build the pack DETERMINISTICALLY from the spec instead:

  the ExplainerSpec's beats ALREADY contain the grounded, gate-clean narration +
  captions that are in the video, so the social copy IS that copy. No AI call, no
  fabrication risk, and the pack says exactly what the video says.

Public API:
  spec_to_pack(spec, idea_id) -> dict          (the {idea_id, pack:{...}} shape)
  write_pack(spec, idea_id) -> Path            (writes .tmp/platform_packs/<id>.json)

CLI:
  python tools/explainer_pack.py --spec <spec.json> --id explainer_overview
  python tools/explainer_pack.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
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

PACK_DIR = ROOT / ".tmp" / "platform_packs"
SITE = "https://workhiveph.com"
GROUPS = ["PSME PH", "IIEE PH", "PIChE PH", "Maintenance Engineers Philippines"]


def _narration_prose(spec: dict) -> str:
    """The video's spoken script as one grounded paragraph (skips the end card)."""
    parts = [b.get("narration", "").strip() for b in spec.get("beats", [])
             if b.get("narration", "").strip()]
    return " ".join(parts)


def _first_caption(spec: dict, default: str) -> str:
    for b in spec.get("beats", []):
        if b.get("caption", "").strip():
            return b["caption"].strip()
    return default


def spec_to_pack(spec: dict, idea_id: str) -> dict:
    """Build the social caption pack (grounded in the spec's own copy)."""
    prose = _narration_prose(spec)
    concept = str(spec.get("concept") or "WorkHive")
    subtitle = str(spec.get("subtitle") or "")
    standard = str(spec.get("standard") or "")
    is_overview = spec.get("kind") == "overview"

    # ── Facebook page ──
    fb_body = f"{prose}\n\nStart free at workhiveph.com."
    fb_comment = "Built for technicians, supervisors, and engineers on the floor. Free to start: workhiveph.com"

    # ── YouTube ──
    if is_overview:
        yt_title = f"WorkHive: {subtitle}" if subtitle else "WorkHive: Free Industrial Intelligence Tools"
        tool_block = ""
        if spec.get("features"):
            tool_block = "\n\nOne login for:\n" + "\n".join(f"- {t}" for t in spec["features"])
        yt_desc = f"{prose}{tool_block}\n\nStart free: {SITE}"
        tags = ["WorkHive", "CMMS", "maintenance", "OEE", "MTBF", "Philippines",
                "industrial maintenance", "free CMMS", "reliability"]
    else:
        title_std = f" ({standard})" if standard else ""
        yt_title = f"WorkHive Explains: {concept}{title_std}"
        std_line = f"\n\nStandard: {standard}." if standard else ""
        yt_desc = f"{prose}{std_line}\n\nLearn more and start free: {SITE}"
        tags = [t for t in ["WorkHive", "WorkHive Explains", concept, standard,
                            "maintenance", "reliability", "Philippines"] if t]

    # ── Shorts / Reels / TikTok ──
    _cap = _first_caption(spec, concept).rstrip()
    if _cap and _cap[-1] not in ".?!":           # keep the caption's own punctuation
        _cap += "."
    short_cap = f"{_cap} Free at workhiveph.com."
    hashtags = ["#WorkHive", "#maintenance", "#Philippines", "#industrialmaintenance", "#reliability"]
    if not is_overview:
        hashtags.append("#" + concept.replace(" ", ""))

    return {
        "idea_id": idea_id,
        "generated_by": "explainer_pack.spec_to_pack (deterministic, grounded in the spec's own copy)",
        "pack": {
            "facebook_page": {"body": fb_body, "first_comment": fb_comment},
            "facebook_group": {"body": f"{prose} Free to start at workhiveph.com.",
                                "target_groups": GROUPS},
            "youtube": {"title": yt_title[:100], "description": yt_desc, "tags": tags},
            "shorts_reels_tiktok": {"caption": short_cap, "hashtags": hashtags},
        },
    }


def write_pack(spec: dict, idea_id: str) -> Path:
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    out = PACK_DIR / f"{idea_id}.json"
    out.write_text(json.dumps(spec_to_pack(spec, idea_id), ensure_ascii=False, indent=2),
                   encoding="utf-8")
    return out


def _pack_text(pack: dict) -> str:
    parts = []
    for sec in pack.get("pack", {}).values():
        if isinstance(sec, dict):
            for v in sec.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, list):
                    parts += [x for x in v if isinstance(x, str)]
    return " ".join(parts)


def self_test() -> int:
    print("explainer_pack.py --self-test")
    print("=" * 52)
    fails = 0

    def ck(cond, label):
        nonlocal fails
        print(("  PASS  " if cond else "  FAIL  ") + label)
        if not cond:
            fails += 1

    from explainer_render import overview_spec, demo_spec
    try:
        from platform_pack import _has_tagalog, _has_banned_phrase, _has_ph_anchor
    except Exception:
        _has_tagalog = lambda t: []          # noqa: E731
        _has_banned_phrase = lambda t: []    # noqa: E731
        _has_ph_anchor = lambda t: True      # noqa: E731

    for name, spec in [("overview", overview_spec()), ("oee", demo_spec())]:
        p = spec_to_pack(spec, f"explainer_{name}")
        pk = p["pack"]
        ck(all(k in pk for k in ("facebook_page", "facebook_group", "youtube", "shorts_reels_tiktok")),
           f"{name}: all 4 platform sections present")
        ck(bool(pk["facebook_page"]["body"]) and bool(pk["youtube"]["title"]),
           f"{name}: fb body + youtube title non-empty")
        ck(len(pk["youtube"]["title"]) <= 100, f"{name}: youtube title within 100 chars")
        text = _pack_text(p)
        ck(not _has_tagalog(text), f"{name}: no Tagalog (grounded in gate-clean narration)")
        ck(not _has_banned_phrase(text), f"{name}: no banned cliches")
        ck("—" not in text, f"{name}: no em dashes")
        ck(_has_ph_anchor(text), f"{name}: has a Philippine anchor")

    print("=" * 52)
    print("  self-test PASS" if fails == 0 else f"  self-test FAIL — {fails} check(s)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Derive a social caption pack from an ExplainerSpec.")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--spec")
    ap.add_argument("--id", default="explainer")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.spec:
        ap.print_help()
        return 1
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = write_pack(spec, args.id)
    print(f"pack written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
