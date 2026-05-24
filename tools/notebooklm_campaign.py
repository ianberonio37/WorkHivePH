#!/usr/bin/env python3
"""
notebooklm_campaign.py — orchestrate NotebookLM long-form artifact generation
for a single WorkHive video idea.

Usage:
    python tools/notebooklm_campaign.py doctor
        Show whether the lib + session + outputs are in shape.

    python tools/notebooklm_campaign.py prepare <idea_id>
        Build the source bundle on disk (no NotebookLM calls).

    python tools/notebooklm_campaign.py run <idea_id> [--profile PROFILE] [--lang LANG] [--only KIND[,KIND..]]
        Full pipeline: prepare sources → create notebook → upload → generate
        every artifact in the chosen profile. Default profile: "marketing".
        Default language: en. Use --only to restrict to specific kinds.

    python tools/notebooklm_campaign.py run-one <idea_id> <kind> [--lang LANG]
        Generate just one artifact (audio|video|slides|infographic|mindmap|blog|briefing|study).

    python tools/notebooklm_campaign.py status <idea_id>
        Show which artifacts exist locally for this idea.

    python tools/notebooklm_campaign.py list
        List every idea that has a NotebookLM workspace on disk.

Profiles (collections of (kind, request) tuples):
    marketing  — audio (deep dive EN), audio (brief TL), video (cinematic
                 professional EN), blog post EN, infographic EN, mind map.
    sales      — slides + briefing doc + audio brief.
    enablement — study guide + flashcards-equivalent quiz + audio deep dive.
    minimal    — audio (brief EN) only — smoke-test.

Notes:
  * notebooklm-py uses undocumented Google APIs. Rate-limits and breakage are
    expected. Errors per-artifact are caught + reported, but the loop keeps
    going so a single failure doesn't tank the campaign.
  * Outputs land in .tmp/notebooklm/<idea_id>/artifacts/ — pick them up from
    there (or via the Flask dashboard once the routes are wired).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Iterable

# Windows consoles default to cp1252 and choke on the arrows / ellipses in
# status lines. Reconfigure stdout/stderr to UTF-8 with a tolerant error
# handler so a Unicode glyph in a log line never tanks the whole campaign.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

# ── Working-dir convention matches video_idea_generator.py ────────────────────

def _load_env():
    for p in [Path(".env"), Path("supabase/functions/.env")]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

# Make sure we can `from tools.X import Y` regardless of how this is invoked.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import notebooklm_client as nlm                # noqa: E402
from tools.notebooklm_brief_builder import (              # noqa: E402
    build_sources, find_idea, NOTEBOOKLM_ROOT,
)


# ── Profiles ──────────────────────────────────────────────────────────────────

def _req(**overrides) -> nlm.ArtifactRequest:
    """Construct an ArtifactRequest with overrides — keeps profiles readable."""
    return nlm.ArtifactRequest(**overrides)


def _marketing_profile(language: str) -> list[tuple[str, nlm.ArtifactRequest]]:
    """Full marketing campaign: podcast EN + brief TL + cinematic video +
    blog post + infographic + mind map."""
    base_instructions = (
        "Speak to Philippine industrial maintenance teams. Use plain simple "
        "English unless the language code is `tl` (Tagalog/Filipino). Anchor "
        "every claim in the uploaded sources. Lead with the pain point from "
        "the idea brief and resolve with the single WorkHive feature named in "
        "the brief. No hype words. End with: 'Try WorkHive free at "
        "workhiveph.com.'"
    )
    items: list[tuple[str, nlm.ArtifactRequest]] = [
        # 12-20min deep-dive podcast — voiced by James (PH English Male)
        # Routes through tools.tts_engine, not NotebookLM's fixed American hosts.
        ("audio", _req(
            kind="audio",
            audio_format="DEEP_DIVE",
            audio_length="LONG",
            language=language,
            voice_key="james",
            instructions=base_instructions,
        )),
        # 5-min companion podcast — Rosa (PH English Female), gives the brand a
        # second voice/personality without paying NotebookLM voice limitations.
        ("audio", _req(
            kind="audio",
            audio_format="DEEP_DIVE",
            audio_length="DEFAULT",
            language=language,
            voice_key="rosa",
            instructions=base_instructions
                + " Rephrase the same core message for a different listener pace.",
        )),
        # 60-90s PH English brief — James (en-PH male) for social feeds.
        # Earlier Taglish + Tagalog attempts produced mangled audio: Edge
        # TTS voices are locale-locked (en-PH James reads Tagalog letters
        # phonetically as English; fil-PH Angelo Filipinizes English jargon).
        # Clean PH English — business-radio style — is the only honest
        # output this stack can produce. Localisation is preserved via
        # accent, scenario (PH factory floor), and product context.
        ("audio", _req(
            kind="audio",
            audio_format="BRIEF",
            audio_length="SHORT",
            language="en",
            voice_key="james",
            instructions=(
                "Write a 60-90 second monologue podcast script in CLEAN "
                "PROFESSIONAL ENGLISH — Philippine business-radio register "
                "(think CNN Philippines, ABS-CBN News Channel, ANC). "
                "Rules: "
                "(1) NO Tagalog words anywhere. NO Taglish. The voice is "
                "en-PH and any Filipino word will be read letter-by-letter "
                "as English — sounds broken. "
                "(2) Audience is Philippine plant supervisors, maintenance "
                "engineers, and operations managers. Address them as 'your "
                "team', 'your technicians', 'your floor'. "
                "(3) Use Philippine industrial context naturally: factory "
                "floors, shift handovers, plant supervisors, technicians, "
                "spare parts stockrooms, work orders. Avoid US/UK idioms "
                "('a hot minute', 'across the pond', 'on the lot'). "
                "(4) Lead with the pain point from the idea brief, then "
                "resolve with the single WorkHive feature named in the "
                "brief. Confident, plain tone — no hype words ('amazing', "
                "'revolutionary', 'game-changing'). "
                "(5) End EXACTLY with: 'Try WorkHive free at workhiveph "
                "dot com.' (read the URL letter by letter — say "
                "'workhive p-h dot com', do not pronounce it as a word)."
            ),
        )),
        # 5-10min cinematic explainer (Veo) — LinkedIn / YouTube hero asset
        ("cinematic", _req(
            kind="cinematic",
            language=language,
            instructions=base_instructions
                + " Use real-feeling factory imagery; avoid cartoonish styles.",
        )),
        # Blog post — SEO landing copy
        ("blog", _req(
            kind="blog",
            report_format="BLOG_POST",
            language=language,
            instructions=(
                base_instructions
                + " Structure: hook, the cost of the pain, what WorkHive does "
                  "differently, a short customer-style example, CTA. 800-1200 "
                  "words. Include H2 sub-heads suitable for SEO."
            ),
        )),
        # Carousel-ready infographic
        ("infographic", _req(
            kind="infographic",
            language=language,
            instructions=base_instructions
                + " Vertical orientation. 5-7 numbered points max. Use WorkHive "
                  "orange (#F7A21B) sparingly for emphasis.",
        )),
        # Interactive feature explorer for the website / sales nav
        ("mindmap", _req(
            kind="mindmap",
            language=language,
            instructions=(
                "Root node = the WorkHive feature named in the idea brief. "
                "Children = pain points it solves, who benefits, how it "
                "connects to other WorkHive pillars, expected ROI signals."
            ),
        )),
    ]
    return items


def _sales_profile(language: str) -> list[tuple[str, nlm.ArtifactRequest]]:
    instr = "Audience is plant managers and procurement decision-makers. Lead with cost of inaction."
    return [
        ("slides", _req(kind="slides", language=language, instructions=instr)),
        ("briefing", _req(kind="briefing", report_format="BRIEFING_DOC", language=language, instructions=instr)),
        ("audio", _req(kind="audio", audio_format="BRIEF", audio_length="SHORT", language=language, instructions=instr)),
    ]


def _enablement_profile(language: str) -> list[tuple[str, nlm.ArtifactRequest]]:
    instr = "Audience is internal training. Walk through the feature step by step."
    return [
        ("study", _req(kind="study", report_format="STUDY_GUIDE", language=language, instructions=instr)),
        ("audio", _req(kind="audio", audio_format="DEEP_DIVE", audio_length="DEFAULT", language=language, instructions=instr)),
    ]


def _minimal_profile(language: str) -> list[tuple[str, nlm.ArtifactRequest]]:
    return [
        ("audio", _req(
            kind="audio",
            audio_format="BRIEF",
            audio_length="SHORT",
            language=language,
            instructions="Smoke test. Produce a 60-second brief grounded in the uploaded sources.",
        )),
    ]


PROFILES = {
    "marketing":  _marketing_profile,
    "sales":      _sales_profile,
    "enablement": _enablement_profile,
    "minimal":    _minimal_profile,
}


# ── Orchestration ─────────────────────────────────────────────────────────────

def _print(stage: str, msg: str) -> None:
    print(f"  [{stage}] {msg}")


def prepare(idea_id: str) -> list[Path]:
    """Build the source bundle on disk. Returns the paths."""
    idea  = find_idea(idea_id)
    title = f"{idea_id}: {idea.get('title', 'Untitled')}"
    _print("prepare", f"idea found — '{title}'")
    paths = build_sources(idea_id)
    for p in paths:
        _print("prepare", f"+ {p.name}  ({p.stat().st_size // 1024} KB)")
    _print("prepare", f"{len(paths)} sources ready in {paths[0].parent}")
    return paths


async def _run_full_async(idea_id: str, profile_name: str, language: str, only: list[str] | None) -> dict:
    idea  = find_idea(idea_id)
    title = f"{idea_id}: {idea.get('title', 'Untitled')}"

    # 1. Sources
    _print("sources", "building bundle…")
    source_paths = build_sources(idea_id)
    _print("sources", f"{len(source_paths)} files ready")

    # 2. Notebook
    _print("notebook", "ensuring notebook in NotebookLM…")
    notebook_id = await nlm.ensure_notebook(idea_id, title)
    _print("notebook", f"notebook_id={notebook_id}")

    # 3. Upload
    _print("upload", "syncing sources to notebook…")
    uploaded = await nlm.upload_sources(notebook_id, source_paths, wait=True)
    _print("upload", f"{uploaded} sources synced")

    # 4. Artifacts
    profile_fn = PROFILES.get(profile_name)
    if profile_fn is None:
        raise SystemExit(f"Unknown profile '{profile_name}'. Choose from: {sorted(PROFILES)}")
    items = profile_fn(language)
    if only:
        items = [(k, r) for (k, r) in items if k in only]
        if not items:
            raise SystemExit(f"--only {only} filtered out every artifact in profile {profile_name!r}")

    results: dict[str, dict] = {}
    for kind, req in items:
        label = f"{kind}:{req.language}:{getattr(req, 'audio_format', '')}{getattr(req, 'video_format', '')}{getattr(req, 'report_format', '')}".strip(":")
        _print("artifact", f"START  {label}")
        t0 = time.time()
        try:
            out_path = await nlm.generate(kind, idea_id, notebook_id, req)
            dt = round(time.time() - t0, 1)
            size_kb = out_path.stat().st_size // 1024 if out_path.exists() else 0
            _print("artifact", f"OK     {label}  → {out_path.name}  ({size_kb} KB, {dt}s)")
            results[label] = {"ok": True, "file": str(out_path), "size_kb": size_kb, "elapsed_s": dt}
        except Exception as exc:                       # noqa: BLE001
            dt = round(time.time() - t0, 1)
            _print("artifact", f"FAIL   {label}  ({dt}s)  → {type(exc).__name__}: {exc}")
            traceback.print_exc()
            results[label] = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "elapsed_s": dt}

    ok    = sum(1 for r in results.values() if r["ok"])
    total = len(results)
    _print("summary", f"{ok}/{total} artifacts produced for {idea_id}")
    return {"idea_id": idea_id, "notebook_id": notebook_id, "results": results}


def _run_full(idea_id: str, profile_name: str, language: str, only: list[str] | None) -> dict:
    """Synchronous façade used by the CLI + Flask thread worker."""
    return asyncio.run(_run_full_async(idea_id, profile_name, language, only))


async def _run_one_async(idea_id: str, kind: str, language: str) -> dict:
    idea  = find_idea(idea_id)
    title = f"{idea_id}: {idea.get('title', 'Untitled')}"

    source_paths = build_sources(idea_id)
    _print("sources", f"{len(source_paths)} files ready")

    notebook_id = await nlm.ensure_notebook(idea_id, title)
    _print("notebook", f"notebook_id={notebook_id}")

    uploaded = await nlm.upload_sources(notebook_id, source_paths, wait=True)
    _print("upload", f"{uploaded} sources synced")

    req = nlm.ArtifactRequest(kind=kind, language=language)
    if kind == "blog":
        req.report_format = "BLOG_POST"
    elif kind == "briefing":
        req.report_format = "BRIEFING_DOC"

    _print("artifact", f"generating {kind}…")
    out_path = await nlm.generate(kind, idea_id, notebook_id, req)
    _print("artifact", f"done → {out_path}")
    return {"idea_id": idea_id, "kind": kind, "file": str(out_path)}


def _run_one(idea_id: str, kind: str, language: str) -> dict:
    return asyncio.run(_run_one_async(idea_id, kind, language))


# ── Reporting commands ────────────────────────────────────────────────────────

def doctor() -> int:
    rep = nlm.availability_report()
    print("NotebookLM doctor")
    print("=================")
    for k, v in rep.items():
        print(f"  {k}: {v}")
    print()
    if not rep["library_installed"]:
        print("Next: run notebooklm_setup.bat to install the library.")
        return 1
    if not rep["session_file_ready"]:
        print("Next: run `notebooklm login`  (opens a browser — sign in to your Google/NotebookLM account)")
        print(f"      The session will be saved to: {rep['session_file_path']}")
        return 2
    print("All checks passed.")
    return 0


def status(idea_id: str) -> int:
    idx = nlm._load_index()
    entry = idx.get(idea_id)
    if not entry:
        print(f"No NotebookLM workspace yet for {idea_id}.")
        return 1
    print(f"Idea {idea_id} — {entry.get('title')}")
    print(f"  Notebook: {entry.get('notebook_id')}")
    arts = entry.get("artifacts", {})
    if not arts:
        print("  No artifacts generated yet.")
        return 0
    for kind, meta in arts.items():
        size_kb = meta.get("size_bytes", 0) // 1024
        print(f"  - {kind:32s}  {meta.get('file')}  ({size_kb} KB)")
    return 0


def list_ideas() -> int:
    idx = nlm._load_index()
    if not idx:
        print("No NotebookLM workspaces yet.")
        return 0
    for idea_id, entry in sorted(idx.items()):
        n_art = len(entry.get("artifacts", {}))
        print(f"  {idea_id:12s}  {n_art:>2d} artifacts  — {entry.get('title','')}")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_argparser() -> argparse.ArgumentParser:
    p   = argparse.ArgumentParser(prog="notebooklm_campaign")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="Diagnose library + session")

    p_prep = sub.add_parser("prepare", help="Build the source bundle for an idea (no NotebookLM calls)")
    p_prep.add_argument("idea_id")

    p_run = sub.add_parser("run", help="Full campaign: sources + notebook + all profile artifacts")
    p_run.add_argument("idea_id")
    p_run.add_argument("--profile", default="marketing", choices=sorted(PROFILES))
    p_run.add_argument("--lang",    default=os.getenv("NOTEBOOKLM_DEFAULT_LANGUAGE", "en"))
    p_run.add_argument("--only",    default="", help="Comma-separated artifact kinds to restrict to")

    p_one = sub.add_parser("run-one", help="Generate a single artifact")
    p_one.add_argument("idea_id")
    p_one.add_argument("kind", choices=["audio", "video", "cinematic", "slides", "infographic", "mindmap", "blog", "briefing", "study"])
    p_one.add_argument("--lang", default=os.getenv("NOTEBOOKLM_DEFAULT_LANGUAGE", "en"))

    p_status = sub.add_parser("status", help="Show artifacts for an idea")
    p_status.add_argument("idea_id")

    sub.add_parser("list", help="List every idea with a NotebookLM workspace")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "prepare":
        prepare(args.idea_id)
        return 0
    if args.cmd == "status":
        return status(args.idea_id)
    if args.cmd == "list":
        return list_ideas()
    if args.cmd == "run":
        only = [k.strip() for k in args.only.split(",") if k.strip()] or None
        result = _run_full(args.idea_id, args.profile, args.lang, only)
        # Persist a per-run report — handy for the dashboard polling endpoint.
        report = NOTEBOOKLM_ROOT / args.idea_id / "last_run.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        ok = sum(1 for r in result["results"].values() if r["ok"])
        return 0 if ok > 0 else 3
    if args.cmd == "run-one":
        result = _run_one(args.idea_id, args.kind, args.lang)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    return 99


if __name__ == "__main__":
    sys.exit(main())
