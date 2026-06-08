"""
Temp A/B driver: composite idea_005 (Hive Dashboard) two ways, scene clip is the
ONLY difference, so the final videos isolate Remotion-scene vs Pexels-scene.

NOTE: imageio_ffmpeg.get_ffmpeg_exe() HANGS in this environment, so we monkeypatch
the assembler to use the proven shim ffmpeg directly. Captions are skipped (they're
identical in A and B, so they don't affect a *background* comparison).

Run from repo root.  Disposable — delete after.
"""
import sys, pathlib, os
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

import tools.video_assembler as va

SHIM_DIR = ROOT / ".tmp/_ffmpeg_shim"
SHIM     = str(SHIM_DIR / "ffmpeg.exe")
os.environ["PATH"] = str(SHIM_DIR) + os.pathsep + os.environ.get("PATH", "")
va._ffmpeg_exe = lambda: SHIM            # bypass imageio_ffmpeg (hangs here)
va._ensure_ffmpeg_on_path = lambda: None # shim already on PATH

IDEA  = "idea_005"
VOICE = "james"
remotion_scene = ROOT / ".tmp/scene_clips/remotion_oee_demo.mp4"
pexels_scene   = ROOT / ".tmp/scene_clips/idea_005_pexels_combined.mp4"
outdir = ROOT / ".tmp/ab_compare"
outdir.mkdir(parents=True, exist_ok=True)

print("\n========== A: REMOTION SCENE ==========", flush=True)
a = va.assemble(
    idea_id=IDEA, voice_key=VOICE,
    scene_clip=remotion_scene,
    captions=False,
    output_path=outdir / "A_remotion_scene.mp4",
)

print("\n========== B: PEXELS SCENE ==========", flush=True)
b = va.assemble(
    idea_id=IDEA, voice_key=VOICE,
    scene_clip=pexels_scene,
    captions=False,
    output_path=outdir / "B_pexels_scene.mp4",
)

print("\nA:", a, flush=True)
print("B:", b, flush=True)
