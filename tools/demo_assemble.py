#!/usr/bin/env python3
"""
demo_assemble.py - cut the raw journey into a WorkHive product demo.
====================================================================
Input : the raw end-to-end recording from demo_journey.py (+ its act spans)
Output: a branded ~90s 16:9 demo, and the 9:16 social cut-down.

STRUCTURE is ported from the measured reference study
(`.tmp/video_ref/Video Marketing_study/`), which resolved to one repeating
2-beat loop: a kinetic TITLE CARD, then a long REAL SCREEN RECORDING, three
times over, bookended by a logo sting and a held end card. That rhythm is what
lets it carry 97 seconds with no voiceover at all.

BRANDING is WorkHive's, not the reference's. Two deliberate departures:
  * The reference sets black type on near-white. WorkHive's product UI is dark
    navy, so white cards would strobe on every cut between card and footage.
    Cards are brand navy with orange/cyan type - same rhythm, no flash.
  * The real WorkHive logo (brand_assets/workhive-logo-tight.png) carries the
    sting and the end card.

THE EDIT'S ONE REAL DECISION: the raw recording contains ~40 seconds of the AI
chain thinking. That is honest but unwatchable, and the reference never shows
dead waiting. So act 4 is cut as TWO clips - the question being typed, then the
answer on screen - and the wait between them is dropped. Nothing is faked; a
cut is a cut.

CLI:
    python tools/demo_assemble.py --journey .tmp/demo_journey/journey_X.webm
    python tools/demo_assemble.py --journey ... --no-music
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
for _p in (str(_HERE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from video_reference_study import ffmpeg_exe, loudness, probe   # noqa: E402

OUT_DIR = ROOT / ".tmp" / "demo_build"
LOGO = ROOT / "brand_assets" / "workhive-logo-tight.png"
MUSIC = ROOT / ".tmp" / "music" / "Soundstortion_Dramat_Hidden_Feelings.mp3"

W, H, FPS = 1280, 720, 30

# WorkHive brand - taken from the PLATFORM's own CSS variables, not sampled by
# eye off the logo, so the cards are the same colours as the UI they cut to:
#   --bg: #0f1923 (35 uses) · --wh-orange: #F7A21B · --wh-text: #e8eef7
#   --accent: #38bdf8 · --surface: #162032
NAVY = (0x0F, 0x19, 0x23)
SURFACE = (0x16, 0x20, 0x32)
ORANGE = (0xF7, 0xA2, 0x1B)
CYAN = (0x38, 0xBD, 0xF8)
WHITE = (0xE8, 0xEE, 0xF7)

# The end card is LOCKED brand copy - a consistent closer on every video, and
# middot rather than an em dash. Do not let this drift per-video.
END_TAGLINE = "Built for the plant floor."
END_SUB = "Free. Mobile-first. Philippines."
END_CTA = "workhiveph.com \u00b7 start free"

# The hook: four beats, mirroring the reference's one-word-per-~0.9s cadence.
# Copy leads with the positioning spine (access your memory / build your own AI
# / save time) - NOT downtime or reliability - and stays generic: no invented
# place, no invented asset tag.
HOOK_WORDS = ["Every", "fix.", "Every", "lesson."]
HOOK_PAYOFF = "Kept."


def _font(size: int):
    from PIL import ImageFont
    for cand in (
        r"C:\Windows\Fonts\Poppins-Bold.ttf",
        r"C:\Windows\Fonts\seguibl.ttf",       # Segoe UI Black
        r"C:\Windows\Fonts\arialbd.ttf",
        str(ROOT / "test-data-seeder/venv/Lib/site-packages/matplotlib/mpl-data/"
                   "fonts/ttf/DejaVuSans-Bold.ttf"),
    ):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    from PIL import ImageFont as IF
    return IF.load_default()


def _balance(title: str, max_len: int = 18) -> list:
    """Break a title into visually balanced lines.

    Splitting on the FIRST space (the obvious approach) gives "Turn" over
    "it into a plan" - a one-word orphan above a long line, which reads as a
    mistake on screen. Choose the break point that makes the two lines closest
    in length instead."""
    if len(title) <= max_len:
        return [title]
    words = title.split()
    if len(words) < 2:
        return [title]
    best, best_delta = 1, None
    for i in range(1, len(words)):
        a = len(" ".join(words[:i]))
        b = len(" ".join(words[i:]))
        delta = abs(a - b)
        if best_delta is None or delta < best_delta:
            best, best_delta = i, delta
    return [" ".join(words[:best]), " ".join(words[best:])]


def _run(args, label=""):
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y"] + args
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({label}):\n{(r.stderr or '')[-700:]}")


# --------------------------------------------------------------------------
# cards
# --------------------------------------------------------------------------

def _card(text_lines, dest: Path, accent_idx=None, size=104, sub=None,
          logo_h=None):
    """One still card on brand navy. Kept deliberately plain: the motion comes
    from the cut and the fade, not from decoration."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)

    y_cursor = None
    if logo_h:
        logo = Image.open(LOGO).convert("RGBA")
        ratio = logo_h / logo.height
        logo = logo.resize((int(logo.width * ratio), logo_h), Image.LANCZOS)
        lx = (W - logo.width) // 2
        ly = int(H * 0.30) if text_lines else (H - logo.height) // 2
        im.paste(logo, (lx, ly), logo)
        y_cursor = ly + logo.height + 46

    if text_lines:
        f = _font(size)
        total = len(text_lines) * (size + 16)
        y = y_cursor if y_cursor is not None else (H - total) // 2
        for i, line in enumerate(text_lines):
            colour = ORANGE if (accent_idx is not None and i == accent_idx) else WHITE
            bbox = d.textbbox((0, 0), line, font=f)
            d.text(((W - (bbox[2] - bbox[0])) // 2, y), line, font=f, fill=colour)
            y += size + 16

    if sub:
        fs = _font(34)
        bbox = d.textbbox((0, 0), sub, font=fs)
        d.text(((W - (bbox[2] - bbox[0])) // 2, int(H * 0.78)), sub,
               font=fs, fill=CYAN)

    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest)
    return dest


def _card_clip(png: Path, dest: Path, dur: float, fade=0.28, fade_in=None):
    """Still -> clip with a gentle scale drift and fades. The slow push keeps a
    static card from reading as a freeze.

    fade_in is separable because the very FIRST card must not fade up from
    black: frame 0 is what every platform grabs as the thumbnail and what
    autoplay shows, and a black frame there reads as a broken video."""
    fi = fade if fade_in is None else fade_in
    zoom = f"scale={int(W*1.06)}:-2,zoompan=z='min(zoom+0.0006,1.06)':d={int(dur*FPS)}:" \
           f"s={W}x{H}:fps={FPS}"
    fade_chain = (f"fade=t=in:st=0:d={fi}," if fi > 0 else "")
    _run(["-loop", "1", "-i", str(png), "-t", f"{dur:.2f}",
          "-vf", f"{zoom},{fade_chain}"
                 f"fade=t=out:st={max(0, dur-fade):.2f}:d={fade},format=yuv420p",
          "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
          str(dest)], f"card {png.stem}")
    return dest


_STAGE_CACHE = {}


def _stage_assets(work: Path) -> dict:
    """Backdrop + rounded-corner alpha mask for the INSET product treatment.

    MEASURED from the reference (video_reverse_engineer.py, 14 product beats):
    content bbox w=0.87-0.93 of frame with ~2.8% side margins - the footage
    FLOATS on a backdrop; it is never full-bleed. My first build ran the
    recording edge-to-edge, and that single difference is much of why it read
    as flat next to the reference. Colours stay platform theme (surface behind
    footage), not the reference's pale blue - Ian: "you follow my platform
    theme"."""
    if _STAGE_CACHE:
        return _STAGE_CACHE
    from PIL import Image, ImageDraw, ImageFilter
    inset_w, inset_h = int(W * 0.90), int(H * 0.90)
    x0, y0 = (W - inset_w) // 2, (H - inset_h) // 2
    r = 18

    back = Image.new("RGB", (W, H), NAVY)
    # soft drop shadow under the floated footage
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.rounded_rectangle([x0 + 6, y0 + 12, x0 + inset_w + 6, y0 + inset_h + 12],
                        radius=r, fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    back.paste(Image.new("RGB", (W, H), (0, 0, 0)), (0, 0), sh)
    # a faint surface plate behind the video (visible at the rounded corners)
    d2 = ImageDraw.Draw(back)
    d2.rounded_rectangle([x0 - 2, y0 - 2, x0 + inset_w + 2, y0 + inset_h + 2],
                         radius=r + 2, fill=SURFACE)
    back_p = work / "_stage_back.png"
    back.save(back_p)

    mask = Image.new("L", (inset_w, inset_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inset_w, inset_h],
                                           radius=r, fill=255)
    mask_p = work / "_stage_mask.png"
    mask.save(mask_p)

    _STAGE_CACHE.update({"back": back_p, "mask": mask_p,
                         "w": inset_w, "h": inset_h, "x": x0, "y": y0})
    return _STAGE_CACHE


def _segment(src: Path, dest: Path, start: float, dur: float, fade=0.26,
             work: Path | None = None):
    """A slice of the real recording, treated the way the reference treats
    product footage: inset ~90%, rounded corners, drop shadow, floating on the
    brand backdrop."""
    st = _stage_assets(work or dest.parent)
    _run(["-ss", f"{start:.2f}", "-i", str(src),
          "-loop", "1", "-i", str(st["back"]),
          "-loop", "1", "-i", str(st["mask"]),
          "-t", f"{dur:.2f}",
          "-filter_complex",
          f"[0:v]scale={st['w']}:{st['h']}:force_original_aspect_ratio=increase,"
          f"crop={st['w']}:{st['h']}[vid];"
          f"[2:v]format=gray[m];[vid][m]alphamerge[rounded];"
          f"[1:v][rounded]overlay={st['x']}:{st['y']}:shortest=1,"
          f"fade=t=in:st=0:d={fade},"
          f"fade=t=out:st={max(0, dur-fade):.2f}:d={fade},format=yuv420p",
          "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
          "-an", str(dest)], f"segment @{start}")
    return dest


# --------------------------------------------------------------------------

def build(journey: Path, with_music=True) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = OUT_DIR / "parts"
    work.mkdir(exist_ok=True)
    meta = probe(journey)
    dur = meta.get("duration_s") or 0
    print(f"  source: {journey.name}  {dur:.1f}s  {meta.get('width')}x{meta.get('height')}")

    # Act spans come from the recorder's own log, so cut points are measured
    # rather than eyeballed off frame samples.
    spans = {}
    sidecar = journey.with_suffix(".json")
    if sidecar.exists():
        spans = json.loads(sidecar.read_text(encoding="utf-8")).get("acts", {})
        print(f"  act spans: { {k: (v['start'], v['end']) for k, v in spans.items()} }")

    def span(key, default_start, default_end):
        s = spans.get(key)
        return (s["start"], s["end"]) if s else (default_start, default_end)

    parts = []
    n = 0

    def add(clip):
        nonlocal n
        parts.append(clip)
        n += 1

    # 1. HOOK - one word per beat, then the payoff word in orange.
    # Type size is MEASURED, not styled: the reference's card glyph band is
    # 26.6% of frame height (video_reverse_engineer.py). On 720p that is a
    # ~190px band; my first build used 112-132px and the type read timid
    # against the reference's.
    hook_size = int(H * 0.26)
    for i, wdt in enumerate(HOOK_WORDS):
        png = _card([wdt], work / f"hook{i}.png", size=hook_size)
        add(_card_clip(png, work / f"p{n:02d}.mp4", 0.85, fade=0.14,
                       fade_in=0 if i == 0 else None))
    png = _card([HOOK_PAYOFF], work / "hookp.png", accent_idx=0,
                size=int(hook_size * 1.15))
    add(_card_clip(png, work / f"p{n:02d}.mp4", 1.5, fade=0.22))

    # 2. LOGO STING
    png = _card([], work / "logo.png", logo_h=250)
    add(_card_clip(png, work / f"p{n:02d}.mp4", 2.0, fade=0.3))

    # 3. TITLE -> FOOTAGE, repeated. Titles say the JOB, not the feature name.
    hive_s, _ = span("1-hive", 3.8, 16.0)
    lb_s, lb_e = span("2-logbook", 16.9, 61.5)
    ah_s, ah_e = span("3-asset-hub", 70.4, 76.8)
    ai_s, ai_e = span("4-assistant", 85.8, 133.0)
    pm_s, _ = span("5-pm", 147.0, dur)

    beats = [
        ("See the whole shift", None, hive_s + 1.5, 7.0),
        ("Log what you fixed", None, lb_s + 2.0, 24.0),
        ("Every machine remembers", None, ah_s + 0.6, 10.0),
        # Act 4 as TWO clips - question, then answer - dropping the ~40s wait.
        ("Ask your own AI", None, ai_s + 1.0, 9.0),
        (None, None, max(ai_s, ai_e - 2.0), 13.0),
        ("Turn it into a plan", None, pm_s + 1.0, 9.0),
    ]
    # Section titles at the measured scale: the reference's section cards run
    # 3.5-4.0s with type filling a quarter of the frame - a BEAT, not a blink.
    title_size = int(H * 0.155)
    for title, _sub, start, seg_dur in beats:
        if title:
            png = _card(_balance(title), work / f"t{n}.png", accent_idx=None,
                        size=title_size)
            add(_card_clip(png, work / f"p{n:02d}.mp4", 2.6))
        seg_dur = min(seg_dur, max(1.0, dur - start - 0.2))
        if seg_dur > 1.0:
            add(_segment(journey, work / f"p{n:02d}.mp4", start, seg_dur, work=work))

    # 4. END CARD - locked brand copy. The reference HOLDS its end card 10.4s
    # (measured); mine held 4.2s. A held end card is what lets a viewer act on
    # the CTA - and on loops it doubles as lead-in.
    png = _card([END_TAGLINE], work / "end.png", size=60, sub=END_CTA, logo_h=190)
    add(_card_clip(png, work / f"p{n:02d}.mp4", 9.0, fade=0.5))

    # concat
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    silent = OUT_DIR / "workhive_demo_16x9_silent.mp4"
    _run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)],
         "concat")

    final = OUT_DIR / "workhive_demo_16x9.mp4"
    if with_music and MUSIC.exists():
        d = probe(silent).get("duration_s") or 0
        _run(["-i", str(silent), "-stream_loop", "-1", "-i", str(MUSIC),
              "-filter_complex",
              f"[1:a]afade=t=in:d=1.0,afade=t=out:st={max(0.5, d-2.2):.2f}:d=2.0,"
              # -14 LUFS: the target the reference hits and every one of our
              # renders missed by 10-15 dB until this was fixed.
              f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]",
              "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
              "-b:a", "192k", "-shortest", str(final)], "music")
    else:
        final = silent

    # 9:16 social cut-down: the strongest ~20s, blurred-fill so nothing crops.
    reel = OUT_DIR / "workhive_demo_9x16.mp4"
    _run(["-i", str(final), "-t", "22",
          "-filter_complex",
          "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,gblur=sigma=20,eq=brightness=-0.14[bg];"
          "[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2",
          "-c:v", "libx264", "-preset", "medium", "-crf", "21",
          "-c:a", "aac", "-b:a", "192k", str(reel)], "9:16")

    out = {"demo_16x9": str(final.relative_to(ROOT)),
           "reel_9x16": str(reel.relative_to(ROOT)),
           "parts": len(parts)}
    for k in ("demo_16x9", "reel_9x16"):
        p = ROOT / out[k]
        m = probe(p)
        out[k + "_duration"] = m.get("duration_s")
        out[k + "_loudness"] = loudness(p).get("integrated_lufs")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble the WorkHive product demo.")
    ap.add_argument("--journey", required=True)
    ap.add_argument("--no-music", action="store_true")
    a = ap.parse_args()
    res = build(Path(a.journey), with_music=not a.no_music)
    print("\n" + "=" * 58)
    for k, v in res.items():
        print(f"  {k:<24} {v}")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    sys.exit(main())
