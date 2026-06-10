"""
Render an ADAPTIVE, on-brand animated background with Remotion for a video idea.

The scene_director picks the best animated STYLE for the idea (dashboard /
kinetic / infographic / mindmap) and fills the content; this renders the matching
Remotion composition into video_assembler's scene_clip slot (1280x720), replacing
generic Pexels stock.

Called by the pipeline's scene stage when SCENE_SOURCE=remotion.

Windows note: npm's .cmd shims break on the `&` in the project path, so we invoke
the Remotion CLI entry directly with `node` and a RELATIVE path from remotion_scenes.

Usage:
    python tools/render_remotion_scene.py --idea idea_013
    python tools/render_remotion_scene.py --headline "Who's Qualified?" --subhead "WorkHive · Skill Matrix"
"""
import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path

ROOT          = Path(__file__).parent.parent
if str(ROOT) not in sys.path:          # so `from tools.X import Y` works standalone
    sys.path.insert(0, str(ROOT))
REMOTION_DIR  = ROOT / "remotion_scenes"
CLI_REL       = os.path.join("node_modules", "@remotion", "cli", "remotion-cli.js")
SCENES_DIR    = ROOT / ".tmp" / "scene_clips"
BACKLOG       = ROOT / ".tmp" / "video_ideas_backlog.json"

# scene-director style → Remotion composition id
STYLE_COMPOSITION = {
    "dashboard":   "WorkHiveMotionBG",
    "kinetic":     "WorkHiveKinetic",
    "infographic": "WorkHiveInfographic",
    "mindmap":     "WorkHiveMindmap",
}


def _node_exe() -> str:
    return shutil.which("node") or "node"


def render_scene(composition: str, props: dict, out_path: Path) -> Path:
    """Render a composition with props to out_path (1280x720 mp4). Raises on failure."""
    if not (REMOTION_DIR / CLI_REL).exists():
        raise RuntimeError(
            f"Remotion not installed at {REMOTION_DIR / CLI_REL}. Run `npm install` in remotion_scenes/."
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _node_exe(), CLI_REL, "render", composition,
        str(out_path.resolve()),
        f"--props={json.dumps(props)}",
        "--codec=h264", "--log=error",
    ]
    print(f"  Remotion: rendering [{composition}] -> {out_path.name}")
    result = subprocess.run(cmd, cwd=str(REMOTION_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Remotion render failed:\n" + (result.stderr or result.stdout or "")[-1400:])
    if not out_path.exists():
        raise RuntimeError("Remotion reported success but wrote no file")
    return out_path


def _props_for(spec: dict) -> dict:
    base = {"headline": spec["headline"], "subhead": spec["subhead"]}
    if spec["style"] == "kinetic":
        base["phrases"] = spec["phrases"]
    elif spec["style"] == "infographic":
        base["stats"] = spec["stats"]
    elif spec["style"] == "mindmap":
        base["nodes"] = spec["nodes"]
    return base


def render_branded_scene(idea: dict) -> Path:
    """Pipeline entry: art-direct + render a SINGLE adaptive scene for an idea.
    Kept for back-compat / fallback; the storyboard path is preferred."""
    from tools.scene_director import direct_scene
    spec = direct_scene(idea)
    comp = STYLE_COMPOSITION.get(spec["style"], "WorkHiveMotionBG")
    print(f"  Scene director -> style={spec['style']}  headline='{spec['headline']}'")
    out = SCENES_DIR / f"{idea['id']}_remotion.mp4"
    return render_scene(comp, _props_for(spec), out)


def _segment_props(seg: dict) -> dict:
    """Trim a storyboard segment to just what its style consumes (keeps the
    --props CLI argument small)."""
    p = {
        "style": seg["style"],
        "frames": int(seg["frames"]),
        "headline": seg["headline"],
        "subhead": seg["subhead"],
    }
    if seg["style"] == "kinetic":
        p["phrases"] = seg.get("phrases", [])
    elif seg["style"] == "infographic":
        p["stats"] = seg.get("stats", [])
    elif seg["style"] == "mindmap":
        p["nodes"] = seg.get("nodes", [])
    return p


def render_storyboard_scene(idea: dict, storyboard: dict = None,
                            narration_path: Path = None) -> Path:
    """Pipeline entry: render the FULL narration-driven sequence in one pass.

    Each beat plays its own animated style back-to-back (no looped single clip),
    and the total length is the sum of segment frames — which the storyboard sets
    to the narration's exact running time. Falls back to a single branded scene if
    the storyboard has no segments.
    """
    if storyboard is None:
        from tools.storyboard import build_storyboard
        storyboard = build_storyboard(idea, narration_path=narration_path)

    segments = storyboard.get("segments") or []
    if not segments:
        print("  [storyboard] no segments — falling back to single branded scene")
        return render_branded_scene(idea)

    props = {"segments": [_segment_props(s) for s in segments]}
    styles = "+".join(s["style"][:3] for s in segments)
    print(f"  Storyboard -> {len(segments)} beats [{styles}]  {storyboard.get('total_seconds')}s")
    out = SCENES_DIR / f"{idea['id']}_storyboard.mp4"
    return render_scene("WorkHiveStoryboard", props, out)


def _load_idea(idea_id: str) -> dict:
    data = json.loads(BACKLOG.read_text(encoding="utf-8"))
    idea = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        raise SystemExit(f"Idea '{idea_id}' not found in backlog")
    return idea


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Render an adaptive WorkHive Remotion scene")
    ap.add_argument("--idea", help="Idea ID (art-directs style + content from the backlog/script)")
    ap.add_argument("--storyboard", action="store_true",
                    help="With --idea: render the full narration-driven sequence (many beats/styles)")
    ap.add_argument("--voice", default="james", help="Voice key (locates the narration mp3 for timing)")
    ap.add_argument("--headline")
    ap.add_argument("--subhead", default="WorkHive")
    ap.add_argument("--style", choices=sorted(STYLE_COMPOSITION), help="Force a style (with --headline)")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.idea and args.storyboard:
        idea = _load_idea(args.idea)
        narr = ROOT / ".tmp/voice_files" / f"{args.idea}_{args.voice}.mp3"
        path = render_storyboard_scene(idea, narration_path=narr if narr.exists() else None)
    elif args.idea:
        idea = _load_idea(args.idea)
        path = render_branded_scene(idea)
    elif args.headline:
        comp = STYLE_COMPOSITION.get(args.style or "dashboard", "WorkHiveMotionBG")
        out = Path(args.out) if args.out else SCENES_DIR / "branded_scene.mp4"
        path = render_scene(comp, {"headline": args.headline, "subhead": args.subhead}, out)
    else:
        raise SystemExit("Provide --idea or --headline")

    print(f"OK: {path}  ({path.stat().st_size/1_000_000:.1f} MB)")
