"""
PROOF OF CONCEPT: build-our-own explainer renderer in PURE PYTHON.
Deps: Pillow + ffmpeg (imageio) ONLY -- both already installed. No Remotion,
no Node, no manim, no ML. Proves we can hold the beloved flagship brand look
(navy gradient + aurora orbs + orange accents + kinetic captions) ourselves.

Outputs: poc_title.png (a branded concept title card) + poc_clip.mp4 (a short
word-by-word kinetic caption clip stitched by ffmpeg).
"""
import math
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

OUT = Path(__file__).resolve().parent
W, H = 1080, 1920  # 9:16

# --- WorkHive brand tokens (from the flagship study) ---
NAVY_TOP = (0x13, 0x24, 0x3a)
NAVY_BOT = (0x23, 0x34, 0x4e)
ORANGE = (0xF7, 0xA2, 0x1B)
ORANGE_LT = (0xFD, 0xB9, 0x4A)
BLUE = (0x29, 0xB6, 0xD9)
CLOUD = (0xF4, 0xF6, 0xFA)
STEEL = (0x9F, 0xB0, 0xC3)


def font(size, weight="black"):
    """Heaviest available system sans (flagship fallback chain: Poppins->Segoe UI)."""
    cands = {
        "black": ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/ariblk.ttf",
                   "C:/Windows/Fonts/Poppins-Black.ttf"],
        "bold":  ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                   "C:/Windows/Fonts/Poppins-Bold.ttf"],
        "semi":  ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/segoeuib.ttf"],
        "reg":   ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"],
    }[weight]
    for c in cands:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def background():
    """Navy vertical gradient + blurred orange/blue aurora orbs + vignette."""
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):
        t = y / H
        r = int(NAVY_TOP[0] + (NAVY_BOT[0] - NAVY_TOP[0]) * t)
        g = int(NAVY_TOP[1] + (NAVY_BOT[1] - NAVY_TOP[1]) * t)
        b = int(NAVY_TOP[2] + (NAVY_BOT[2] - NAVY_TOP[2]) * t)
        for x in range(0, W, 1):
            px[x, y] = (r, g, b)
    # aurora orbs (blurred ellipses, additive-ish via alpha composite)
    orb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    od.ellipse([-220, -260, 560, 520], fill=(*ORANGE, 60))      # top-left orange
    od.ellipse([W - 520, H - 620, W + 240, H - 40], fill=(*BLUE, 48))  # bottom-right blue
    orb = orb.filter(ImageFilter.GaussianBlur(170))
    bg = Image.alpha_composite(bg.convert("RGBA"), orb)
    # vignette: darken edges with a blurred radial mask
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([-W * 0.25, H * 0.06, W * 1.25, H * 0.94], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGBA", (W, H), (8, 12, 20, 150))
    bg = Image.composite(bg, Image.alpha_composite(bg, dark), mask)
    return bg.convert("RGB")


def center_text(d, cx, y, text, fnt, fill, spacing=0):
    if spacing:
        widths = [d.textlength(ch, font=fnt) + spacing for ch in text]
        total = sum(widths) - spacing
        x = cx - total / 2
        for ch in text:
            d.text((x, y), ch, font=fnt, fill=fill)
            x += d.textlength(ch, font=fnt) + spacing
        return
    w = d.textlength(text, font=fnt)
    d.text((cx - w / 2, y), text, font=fnt, fill=fill)


def title_card():
    img = background()
    d = ImageDraw.Draw(img)
    cx = W / 2
    # kicker (letter-spaced, orange)
    center_text(d, cx, 560, "WORKHIVE EXPLAINS", font(34, "bold"), ORANGE, spacing=10)
    # accent rule
    d.rounded_rectangle([cx - 70, 626, cx + 70, 634], radius=4, fill=ORANGE)
    # big concept title
    center_text(d, cx, 700, "OEE", font(300, "black"), CLOUD)
    center_text(d, cx, 1040, "Overall Equipment", font(86, "black"), CLOUD)
    center_text(d, cx, 1140, "Effectiveness", font(86, "black"), CLOUD)
    # the formula tease, color-coded (the teach)
    fy = 1320
    fnt = font(64, "bold")
    parts = [("Availability", BLUE), ("  x  ", STEEL), ("Performance", ORANGE),
             ("  x  ", STEEL), ("Quality", BLUE)]
    total = sum(d.textlength(t, font=fnt) for t, _ in parts)
    x = cx - total / 2
    for t, col in parts:
        d.text((x, fy), t, font=fnt, fill=col)
        x += d.textlength(t, font=fnt)
    # subtitle
    center_text(d, cx, 1440, "The one number that tells you", font(40, "semi"), STEEL)
    center_text(d, cx, 1492, "how your plant is really doing.", font(40, "semi"), STEEL)
    # standard citation chip (authority)
    chip = "ISO 22400-2"
    cw = d.textlength(chip, font=font(30, "semi")) + 44
    d.rounded_rectangle([cx - cw / 2, 1610, cx + cw / 2, 1664], radius=27,
                        outline=STEEL, width=2)
    center_text(d, cx, 1622, chip, font(30, "semi"), STEEL)
    img.save(OUT / "poc_title.png")
    return img


def kinetic_clip(fps=30, n=42):
    """A short word-by-word ease-up caption over the brand bg -> mp4."""
    bg = background()
    words = ["This", "is", "built", "in", "pure", "Python."]
    fnt = font(96, "black")
    frames_dir = OUT / "_poc_frames"
    frames_dir.mkdir(exist_ok=True)
    cx, baseY = W / 2, 900
    for f in range(n):
        img = bg.copy()
        d = ImageDraw.Draw(img)
        # measure total width for centering
        gap = 26
        widths = [d.textlength(w, font=fnt) for w in words]
        total = sum(widths) + gap * (len(words) - 1)
        x = cx - total / 2
        for i, w in enumerate(words):
            # each word springs up with a per-word delay (ease-out cubic)
            local = (f - i * 4) / 12.0
            local = max(0.0, min(1.0, local))
            ease = 1 - pow(1 - local, 3)
            dy = (1 - ease) * 46
            col = ORANGE if w.endswith("Python.") else CLOUD
            # opacity via blending onto bg (draw on temp then composite)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.text((x, baseY + dy), w, font=fnt, fill=(*col, int(255 * ease)))
            img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
            d = ImageDraw.Draw(img)
            x += widths[i] + gap
        img.save(frames_dir / f"f{f:04d}.png")
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out = OUT / "poc_clip.mp4"
    subprocess.run([ff, "-y", "-framerate", str(fps), "-i", str(frames_dir / "f%04d.png"),
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20", str(out)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return out


if __name__ == "__main__":
    title_card()
    clip = kinetic_clip()
    print("OK")
    print("  still:", (OUT / "poc_title.png").stat().st_size, "bytes")
    print("  clip :", clip.stat().st_size, "bytes" if clip.exists() else "MISSING")
