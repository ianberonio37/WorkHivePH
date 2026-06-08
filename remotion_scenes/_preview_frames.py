"""One-off: copy the rendered scene into .tmp/scene_clips and grab preview stills."""
import shutil
import subprocess
from pathlib import Path
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
src = Path(__file__).resolve().parent / "out" / "workhive-oee-scene.mp4"
scenes = ROOT / ".tmp" / "scene_clips"
scenes.mkdir(parents=True, exist_ok=True)
dst = scenes / "remotion_oee_demo.mp4"
shutil.copy2(src, dst)
print(f"copied -> {dst}  ({dst.stat().st_size/1_000_000:.1f} MB)")

ff = imageio_ffmpeg.get_ffmpeg_exe()
preview_dir = Path(__file__).resolve().parent / "out"
for sec in (1.5, 4.5, 8.0):
    out = preview_dir / f"frame_{str(sec).replace('.', '_')}s.png"
    subprocess.run([ff, "-y", "-ss", str(sec), "-i", str(src),
                    "-frames:v", "1", str(out)],
                   capture_output=True, text=True)
    print(f"frame @ {sec}s -> {out}")
