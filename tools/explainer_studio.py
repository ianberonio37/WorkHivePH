#!/usr/bin/env python3
"""
explainer_studio.py — the FLAGSHIP-GRADE motion renderer for "WorkHive Explains".
=================================================================================
Ian's verdict on v1: "it's ugly." Right — v1 was a static, flat, product-less
slideshow. This module fixes the three things that killed it, still 100% pure
Python (Pillow + ffmpeg), ZERO new dependencies:

  1. PRODUCT AS HERO  — the real app screenshots (remotion_scenes/public/wh_*.png)
     composited inside a phone frame, on stage. Show the app, don't describe it.
  2. MOTION           — spring-in (ease-out-back) entrances, Ken Burns drift on the
     product, staggered reveals, a slow-drifting background glow.
  3. DEPTH            — soft drop shadows behind the phone + cards, a radial glow
     halo behind the hero, gradient-filled chips (not hollow flat outlines).

Shares brand tokens + font + fit helpers with explainer_render (imported lazily
to avoid a cycle). Per-frame scene rendering (not cached statics) so elements
actually animate.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from explainer_render import (
    NAVY_TOP, NAVY_BOT, ORANGE, ORANGE_LT, BLUE, CLOUD, STEEL,
    font, fit_font, _text_w, center_text, wrap_words,
)

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
SCREENS = ROOT / "remotion_scenes" / "public"


# ── easing ────────────────────────────────────────────────────────────────────

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - pow(1 - t, 3)


def ease_out_back(t: float, s: float = 1.55) -> float:
    """Springy overshoot (the flagship's signature entrance feel)."""
    t = clamp01(t) - 1
    return 1 + (s + 1) * t * t * t + s * t * t


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ── caches ────────────────────────────────────────────────────────────────────

_SCREEN_CACHE: dict[str, Image.Image] = {}
_BG_CACHE: dict[tuple, Image.Image] = {}
_SHADOW_CACHE: dict[tuple, Image.Image] = {}
_GLOW_CACHE: dict[tuple, Image.Image] = {}
_PHONE_CACHE: dict[tuple, Image.Image] = {}


def load_screen(name: str) -> Image.Image | None:
    if name in _SCREEN_CACHE:
        return _SCREEN_CACHE[name]
    p = SCREENS / (name if name.endswith(".png") else f"{name}.png")
    if not p.exists():
        return None
    im = Image.open(p).convert("RGB")
    _SCREEN_CACHE[name] = im
    return im


_LOGO: Image.Image | None | bool = None


def load_logo() -> Image.Image | None:
    """The real WorkHive brand mark (WORK orange + HIVE blue + honeycomb),
    transparent PNG. Used everywhere the brand appears (not typeset text)."""
    global _LOGO
    if _LOGO is None:
        p = SCREENS / "workhive-logo-tight.png"
        _LOGO = Image.open(p).convert("RGBA") if p.exists() else False
    return _LOGO or None


def paste_logo(canvas: Image.Image, cx: float, cy: float, target_w: float,
               appear: float = 1.0, glow: bool = False) -> tuple[float, float]:
    """Composite the real logo centered at (cx, cy), width target_w, with a springy
    entrance. Returns (top_y, bottom_y)."""
    logo = load_logo()
    if logo is None:
        return cy, cy
    ratio = logo.size[1] / logo.size[0]
    w, h = int(target_w), int(target_w * ratio)
    lg = logo.resize((max(1, w), max(1, h)), Image.LANCZOS)
    e = ease_out_back(appear)
    scale = lerp(0.8, 1.0, clamp01(e))
    if scale != 1.0:
        lg = lg.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        w, h = lg.size
    alpha = int(255 * ease_out_cubic(clamp01(appear / 0.6)))
    if alpha < 255:
        lg.putalpha(lg.split()[3].point(lambda v: v * alpha // 255))
    dy = (1 - ease_out_cubic(appear)) * h * 0.15
    top = cy + dy - h / 2
    if glow:
        g = _radial_glow(int(w * 0.62), ORANGE, 42)
        canvas.alpha_composite(g, (int(cx - g.size[0] / 2), int(cy + dy - g.size[1] / 2)))
    canvas.alpha_composite(lg, (int(cx - w / 2), int(top)))
    return top, top + h


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


# ── background : navy gradient + a SLOW-DRIFTING glow (cheap motion) ──────────

def _base_gradient(W: int, H: int) -> Image.Image:
    key = ("grad", W, H)
    if key in _BG_CACHE:
        return _BG_CACHE[key]
    bg = Image.new("RGB", (W, H))
    for y in range(H):
        t = y / H
        r = int(lerp(NAVY_TOP[0], NAVY_BOT[0], t))
        g = int(lerp(NAVY_TOP[1], NAVY_BOT[1], t))
        b = int(lerp(NAVY_TOP[2], NAVY_BOT[2], t))
        bg.paste(Image.new("RGB", (W, 1), (r, g, b)), (0, y))
    # static vignette baked in
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([-W * 0.25, H * 0.05, W * 1.25, H * 0.95], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(int(W * 0.2)))
    dark = Image.new("RGB", (W, H), (8, 12, 20))
    bg = Image.composite(bg, Image.blend(bg, dark, 0.5), mask)
    _BG_CACHE[key] = bg
    return bg


def _drift_orb(W: int, H: int, color: tuple, rad: int) -> Image.Image:
    """A blurred aurora orb on a 2W x 2H PADDED layer (ellipse centered at (W,H)),
    so when pasted at a drifting offset its soft edges stay off-screen and never
    leave a hard vertical seam (the v1 bug on dark scenes)."""
    key = ("orb2", W, H, color, rad)
    if key in _GLOW_CACHE:
        return _GLOW_CACHE[key]
    layer = Image.new("RGBA", (2 * W, 2 * H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([W - rad, H - rad, W + rad, H + rad], fill=(*color, 70))
    layer = layer.filter(ImageFilter.GaussianBlur(int(rad * 0.7)))
    _GLOW_CACHE[key] = layer
    return layer


def animated_bg(W: int, H: int, t: float) -> Image.Image:
    """Navy gradient with two aurora orbs that slowly drift (t in 0..1 over the
    whole video). The padded orbs paste centered at a moving target with no seam."""
    bg = _base_gradient(W, H).convert("RGBA")
    orb_o = _drift_orb(W, H, ORANGE, int(W * 0.42))
    orb_b = _drift_orb(W, H, BLUE, int(W * 0.5))
    tau = t * math.pi * 2
    # orb CENTER targets on the canvas (orb center sits at (W,H) in its layer)
    pox, poy = W * 0.24 + math.sin(tau) * W * 0.05, H * 0.16 + math.cos(tau) * H * 0.03
    pbx, pby = W * 0.76 + math.cos(tau + 1) * W * 0.05, H * 0.74 + math.sin(tau + 1) * H * 0.03
    bg.alpha_composite(orb_o, (int(pox - W), int(poy - H)))
    bg.alpha_composite(orb_b, (int(pbx - W), int(pby - H)))
    return bg


# ── depth : soft shadow + radial glow ────────────────────────────────────────

def _soft_shadow(size: tuple[int, int], radius: int, blur: int, alpha: int) -> Image.Image:
    key = ("sh", size, radius, blur, alpha)
    if key in _SHADOW_CACHE:
        return _SHADOW_CACHE[key]
    pad = blur * 2
    sh = Image.new("RGBA", (size[0] + pad * 2, size[1] + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad, pad + size[0], pad + size[1]],
                                         radius=radius, fill=(0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    _SHADOW_CACHE[key] = sh
    return sh


def _radial_glow(rad: int, color: tuple, alpha: int) -> Image.Image:
    key = ("gl", rad, color, alpha)
    if key in _GLOW_CACHE:
        return _GLOW_CACHE[key]
    g = Image.new("RGBA", (rad * 2, rad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([rad * 0.35, rad * 0.35, rad * 1.65, rad * 1.65], fill=(*color, alpha))
    g = g.filter(ImageFilter.GaussianBlur(int(rad * 0.35)))
    _GLOW_CACHE[key] = g
    return g


# ── the money shot : a real app screen in a phone frame ──────────────────────

def _compose_phone(screen: Image.Image, screen_w: int, kb: float,
                   callout: dict | None = None) -> Image.Image:
    """Return an RGBA phone (bezel + rounded screen) with a Ken-Burns zoom `kb`
    (0..1 -> 1.00..1.06 scale, slight downward pan). An optional `callout` draws a
    pulsing ring on a normalized region of the ORIGINAL screenshot; it is mapped
    through the same crop/zoom/pan so it tracks the Ken Burns exactly (P4: direct
    the eye to the element the narration names, e.g. the TX-001 96%-risk alert)."""
    # Trim the screenshots' sparse footer so the phone shows content, not empty navy.
    sw, sh0 = screen.size
    screen = screen.crop((0, 0, sw, int(sh0 * 0.84)))
    ratio = screen.size[1] / screen.size[0]
    screen_h = int(screen_w * ratio)
    bezel = max(6, int(screen_w * 0.035))
    corner = int(screen_w * 0.11)
    pw, ph = screen_w + bezel * 2, screen_h + bezel * 2

    # Ken Burns: zoom the SCREEN content (crop a moving window, resize back).
    zoom = 1.0 + 0.06 * clamp01(kb)
    zw, zh = int(screen.size[0] / zoom), int(screen.size[1] / zoom)
    ox = (screen.size[0] - zw) // 2
    oy = int((screen.size[1] - zh) * (0.15 + 0.7 * clamp01(kb)))  # slow pan down
    crop = screen.crop((ox, oy, ox + zw, oy + zh)).resize((screen_w, screen_h), Image.LANCZOS)
    scr = crop.convert("RGBA")
    scr.putalpha(_rounded_mask((screen_w, screen_h), corner - bezel))

    phone = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    body = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=corner,
                                           fill=(13, 20, 32, 255), outline=(60, 78, 104, 255), width=2)
    phone.alpha_composite(body)
    phone.alpha_composite(scr, (bezel, bezel))
    # subtle top screen glare
    glare = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(glare).polygon([(bezel, bezel), (pw - bezel, bezel),
                                   (pw - bezel, bezel + ph * 0.12), (bezel, bezel + ph * 0.22)],
                                  fill=(255, 255, 255, 16))
    phone.alpha_composite(glare)
    if callout:
        _draw_phone_callout(phone, callout, sw, sh0, ox, oy, zw, zh,
                            screen_w, screen_h, bezel)
    return phone


def _draw_phone_callout(phone: Image.Image, callout: dict, sw: int, sh0: int,
                        ox: int, oy: int, zw: int, zh: int,
                        screen_w: int, screen_h: int, bezel: int) -> None:
    """Draw a pulsing highlight ring around a normalized box of the ORIGINAL
    screenshot, mapped through the current crop/zoom/pan so it stays locked to the
    element as the Ken Burns moves. Ring only (the red card already reads '96%')."""
    box = callout.get("box") or [0.05, 0.24, 0.95, 0.34]
    appear = clamp01(callout.get("appear", 1.0))
    if appear <= 0:
        return
    accent = callout.get("accent_rgb", (247, 96, 66))       # alert red-orange
    phase = float(callout.get("phase", 1.0))

    def to_ph(nx: float, nyf: float) -> tuple[float, float]:
        px, py = nx * sw, nyf * sh0
        return bezel + (px - ox) / zw * screen_w, bezel + (py - oy) / zh * screen_h

    x0, y0 = to_ph(box[0], box[1])
    x1, y1 = to_ph(box[2], box[3])
    x0 = max(bezel, x0); y0 = max(bezel, y0)
    x1 = min(bezel + screen_w, x1); y1 = min(bezel + screen_h, y1)
    if x1 - x0 < 6 or y1 - y0 < 6:
        return
    pad = (x1 - x0) * 0.02
    bx0, by0, bx1, by1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    # spring-grow about the box center as it appears
    cxb, cyb = (bx0 + bx1) / 2, (by0 + by1) / 2
    s = lerp(0.88, 1.0, clamp01(ease_out_back(appear)))
    bx0, by0 = cxb + (bx0 - cxb) * s, cyb + (by0 - cyb) * s
    bx1, by1 = cxb + (bx1 - cxb) * s, cyb + (by1 - cyb) * s
    rad = max(6, int((by1 - by0) * 0.30))
    # gentle two-beat pulse on the ring/glow intensity
    pulse = 0.72 + 0.28 * (0.5 - 0.5 * math.cos(phase * math.pi * 4))
    a = int(255 * clamp01(appear / 0.45) * pulse)
    gw, gh = int(bx1 - bx0), int(by1 - by0)
    if gw > 2 and gh > 2:
        m = 22
        glow = Image.new("RGBA", (gw + m * 2, gh + m * 2), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle([m, m, m + gw, m + gh], radius=rad,
                                               outline=(*accent, a), width=11)
        glow = glow.filter(ImageFilter.GaussianBlur(10))
        phone.alpha_composite(glow, (int(bx0 - m), int(by0 - m)))
    ImageDraw.Draw(phone).rounded_rectangle([bx0, by0, bx1, by1], radius=rad,
                                            outline=(*accent, a),
                                            width=max(3, int((by1 - by0) * 0.055)))


def paste_phone(canvas: Image.Image, screen_name: str, cx: float, cy: float,
                screen_w: int, appear: float, kb: float,
                callout: dict | None = None) -> tuple[float, float]:
    """Composite a phone-framed app screen onto `canvas` (RGBA), with a springy
    slide-up entrance (`appear` 0..1) and a radial glow halo behind it. Returns
    the phone's (top_y, bottom_y) so callers can place labels without collisions."""
    screen = load_screen(screen_name)
    if screen is None:
        return cy, cy
    phone = _compose_phone(screen, screen_w, kb, callout=callout)
    pw, ph = phone.size

    e = ease_out_back(appear)
    scale = lerp(0.86, 1.0, clamp01(e))
    dy = (1 - ease_out_cubic(appear)) * (ph * 0.10)
    alpha = int(255 * ease_out_cubic(appear / 0.6))
    if scale != 1.0:
        phone = phone.resize((max(1, int(pw * scale)), max(1, int(ph * scale))), Image.LANCZOS)
        pw, ph = phone.size
    if alpha < 255:
        a = phone.split()[3].point(lambda v: v * alpha // 255)
        phone.putalpha(a)

    top = cy + dy - ph / 2
    # glow halo behind the phone (depth)
    glow = _radial_glow(int(pw * 0.85), ORANGE, 55)
    canvas.alpha_composite(glow, (int(cx - glow.size[0] / 2), int(cy + dy - glow.size[1] / 2)))
    # drop shadow behind the phone (depth)
    sh = _soft_shadow((pw, ph), int(pw * 0.11), int(pw * 0.06), 150)
    canvas.alpha_composite(sh, (int(cx - sh.size[0] / 2), int(top - int(pw * 0.06) * 2 + ph * 0.03)))
    # the phone
    canvas.alpha_composite(phone, (int(cx - pw / 2), int(top)))
    return top, top + ph


# ── label chip (gradient-filled, with depth) ─────────────────────────────────

def label_chip(canvas: Image.Image, text: str, cx: float, cy: float, U: int,
               appear: float = 1.0, accent: tuple = ORANGE) -> None:
    d = ImageDraw.Draw(canvas)
    f = font(int(U * 0.036), "bold")
    tw = _text_w(d, text, f)
    padx, h = U * 0.05, U * 0.075
    w = tw + padx * 2
    e = ease_out_cubic(appear)
    dy = (1 - e) * U * 0.05
    x0, y0 = cx - w / 2, cy - h / 2 + dy
    sh = _soft_shadow((int(w), int(h)), int(h / 2), int(U * 0.02), 120)
    canvas.alpha_composite(sh, (int(x0 - int(U * 0.04)), int(y0 - int(U * 0.04) + U * 0.01)))
    chip = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chip)
    cd.rounded_rectangle([0, 0, int(w) - 1, int(h) - 1], radius=int(h / 2),
                         fill=(27, 45, 69, 235), outline=(*accent, 255), width=3)
    cd.ellipse([h * 0.30, h * 0.5 - h * 0.09, h * 0.30 + h * 0.18, h * 0.5 + h * 0.09], fill=accent)
    canvas.alpha_composite(chip, (int(x0), int(y0)))
    d.text((x0 + padx + h * 0.34, y0 + h / 2 - f.size * 0.62), text, font=f, fill=CLOUD)


# ── proof: render one hero still (fast, no video) ────────────────────────────

def hero_scene(canvas: Image.Image, W: int, H: int, screen: str, headline: str,
               label: str, caption: str, appear: float = 1.0, kb: float = 0.35,
               cap_accent: str | None = None, callout: dict | None = None) -> None:
    """The reusable product-hero composition: logo, headline, phone hero (with
    glow+shadow), a label chip, and a caption. ASPECT-AWARE (P6): 9:16 stacks the
    phone centered with text above/below; 16:9 puts the phone LEFT and the text
    RIGHT (the portrait phone can't fit a wide frame's height centered); 1:1 uses a
    smaller centered phone. The `callout` ring rides inside the phone, so it tracks
    every aspect for free. The bottom kinetic caption (drawn by the render loop at
    y=0.9) stays clear because the phone sits higher in the wide/square layouts."""
    U = min(W, H)
    wide = W >= H * 1.2                      # 16:9
    square = (not wide) and (W >= H * 0.95)  # 1:1

    if wide:
        tx = W * 0.685                       # right-hand text column center
        tw = W * 0.40                        # its wrap width
        paste_logo(canvas, tx, H * 0.13, int(H * 0.20), appear=1.0)
        # phone LEFT, sized to the frame height, held high so the bottom caption is clear
        top, bottom = paste_phone(canvas, screen, W * 0.29, H * 0.44, int(H * 0.34),
                                  appear=appear, kb=kb, callout=callout)
        d = ImageDraw.Draw(canvas)
        if headline:
            hf = fit_font(d, headline, "black", tw, int(U * 0.085), int(U * 0.05))
            hl = wrap_words(d, headline.split(), hf, tw)
            hy = H * 0.30
            for ln in hl[:3]:
                center_text(d, tx, hy, " ".join(ln), hf, CLOUD)
                hy += hf.size * 1.14
        if label:
            label_chip(canvas, label, tx, H * 0.63, U, appear=appear)
        if caption:
            cf = fit_font(ImageDraw.Draw(canvas), caption, "black", tw, int(U * 0.07), int(U * 0.04))
            center_text(ImageDraw.Draw(canvas), tx, H * 0.78, caption, cf, CLOUD)
        return

    # portrait (9:16) or square (1:1): centered stack, phone smaller for 1:1
    cx = W / 2
    ph_cy = H * 0.50 if square else H * 0.52
    screen_w = int(H * 0.34) if square else int(W * 0.44)
    d = ImageDraw.Draw(canvas)
    paste_logo(canvas, cx, H * 0.075, int(U * 0.26), appear=1.0)
    d = ImageDraw.Draw(canvas)
    if headline:
        hf = fit_font(d, headline, "black", W * 0.9, int(U * 0.06), int(U * 0.036))
        hl = wrap_words(d, headline.split(), hf, W * 0.9)
        hy = H * (0.11 if square else 0.16)
        for ln in hl[:2]:
            center_text(d, cx, hy, " ".join(ln), hf, CLOUD)
            hy += hf.size * 1.08
    top, bottom = paste_phone(canvas, screen, cx, ph_cy, screen_w,
                              appear=appear, kb=kb, callout=callout)
    if label:
        label_chip(canvas, label, cx, bottom + U * 0.02, U, appear=appear)
    if caption:
        cf = fit_font(ImageDraw.Draw(canvas), caption, "black", W * 0.9, int(U * 0.05), int(U * 0.032))
        center_text(ImageDraw.Draw(canvas), cx, H * 0.90, caption, cf, CLOUD)


def proof_frame(W: int = 1080, H: int = 1920) -> Image.Image:
    canvas = animated_bg(W, H, 0.2)
    hero_scene(canvas, W, H, "wh_home_clean", "Your whole plant, one login",
               "Home Dashboard", "See everything at a glance.", appear=1.0, kb=0.4)
    return canvas.convert("RGB")


# ── kinetic caption (word-by-word, synced to the beat's word timings) ─────────

def _chunk(words: list[dict], n: int = 6) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or w["text"].strip().endswith((".", "?", "!", ":", ",")):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def draw_kinetic(canvas: Image.Image, chunks: list[list[dict]], local_ms: float,
                 W: int, H: int, y_frac: float = 0.9, size_frac: float = 0.052) -> None:
    """Word-by-word kinetic caption. Silent-first legibility (85% watch muted):
    every word carries a dark stroke so it reads at 4.5:1 over any background
    (CONTENT_VIDEO_BEST_PRACTICES §5). NOTE: the first positional arg after H is
    still y_frac; callers pass it positionally (e.g. 0.9)."""
    if not chunks:
        return
    active = chunks[0]
    for ch in chunks:
        if ch[0]["start_ms"] <= local_ms:
            active = ch
        else:
            break
    U = min(W, H)
    d = ImageDraw.Draw(canvas)
    toks = [w["text"] for w in active]
    f = fit_font(d, " ".join(toks), "black", W * 0.9, int(U * size_frac), int(U * max(0.03, size_frac * 0.62)))
    stroke = max(2, int(f.size * 0.065))          # dark outline for mute-first contrast
    lines = wrap_words(d, toks, f, W * 0.9)
    line_h = f.size * 1.14
    y = H * y_frac - (line_h * len(lines)) / 2
    idx = 0
    for ln in lines:
        x = W / 2 - _text_w(d, " ".join(ln), f) / 2
        for word in ln:
            wm = active[idx] if idx < len(active) else {"start_ms": 0, "end_ms": 0}
            idx += 1
            started = wm.get("start_ms", 0) <= local_ms
            speaking = wm.get("start_ms", 0) <= local_ms <= wm.get("end_ms", 1e12)
            col = (ORANGE if speaking else CLOUD) if started else (70, 84, 108)
            dy = 0
            if started:
                p = clamp01((local_ms - wm.get("start_ms", 0)) / 150.0)
                dy = (1 - ease_out_cubic(p)) * U * 0.012
            d.text((x, y + dy), word, font=f, fill=col,
                   stroke_width=stroke, stroke_fill=(6, 10, 18))
            x += _text_w(d, word + " ", f)
        y += line_h


# ── scenes (per-frame; local `t` is 0..1 progress within the beat) ────────────

def scene_intro(canvas: Image.Image, spec: dict, W: int, H: int, t: float) -> None:
    U = min(W, H)
    cx = W / 2
    d = ImageDraw.Draw(canvas)
    # the REAL WorkHive logo springs in as the centerpiece, with a glow halo
    appear = clamp01((t - 0.05) / 0.55)
    paste_logo(canvas, cx, H * 0.44, int(W * 0.72), appear=appear, glow=True)
    d = ImageDraw.Draw(canvas)
    # small EXPLAINS kicker under the mark
    a_kick = clamp01((t - 0.3) / 0.35)
    if a_kick > 0:
        kf = font(int(U * 0.036), "bold")
        col = tuple(int(lerp(NAVY_BOT[i], ORANGE[i], a_kick)) for i in range(3))
        center_text(d, cx, H * 0.585, "EXPLAINS", kf, col, spacing=int(U * 0.014))
    sub = str(spec.get("subtitle") or "Free Industrial Intelligence Tools")
    a_sub = clamp01((t - 0.42) / 0.4)
    if a_sub > 0:
        sf = fit_font(d, sub, "semi", W * 0.86, int(U * 0.05), int(U * 0.03))
        col = tuple(int(lerp(NAVY_BOT[i], STEEL[i], a_sub)) for i in range(3))
        center_text(d, cx, H * 0.66, sub, sf, col)


def _hexagon(cx: float, cy: float, r: float, rot: float = 0.0) -> list[tuple[float, float]]:
    return [(cx + r * math.cos(math.radians(60 * i - 90) + rot),
             cy + r * math.sin(math.radians(60 * i - 90) + rot)) for i in range(6)]


BRAND = ROOT / "brand_assets"
# Ian's REAL AI companions (james->hezekiah male, rosa->zaniah female; migration
# 20260520000026). Their portraits ARE the "AI people" for the video (Ian 2026-07-02:
# "I have my own AI Companion images, Hezekiah and Zaniah" — far better than a generic
# worker). ring = the brand glow around each avatar.
# Prefer Ian's UPDATED realistic portraits (hezekiah.png / zaniah.png) if present,
# else the original illustrated ones (James.png=hezekiah, Rosa.png=zaniah).
_PERSONAS = [(["hezekiah.png", "James.png"], ORANGE), (["zaniah.png", "Rosa.png"], BLUE)]
_COMPANION_ART: list | None = None


def _circle_avatar(path: Path, size: int = 512) -> Image.Image | None:
    """Crop a portrait to a face-centered circle (RGBA, transparent outside) — the
    app's companion-avatar look, so it drops cleanly onto the video's navy bg."""
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    W, H = im.size
    s = int(min(W, H * 0.9) * 0.9)                 # square crop, face is upper-centre
    cx, cy = W // 2, int(H * 0.42)
    im = im.crop((cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2)).resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([2, 2, size - 2, size - 2], fill=255)
    im.putalpha(mask)
    return im


def _companion_art():
    """Load Ian's companion portraits (brand_assets/James.png=Hezekiah, Rosa.png=Zaniah)
    as circular avatars once. Returns [(avatar, ring_color), ...] or None if absent."""
    global _COMPANION_ART
    if _COMPANION_ART is None:
        out = []
        for names, ring in _PERSONAS:
            for fname in names:                         # first existing file wins
                av = _circle_avatar(BRAND / fname)
                if av is not None:
                    out.append((av, ring)); break
        _COMPANION_ART = out
    return _COMPANION_ART or None


def _companion_art_draw(canvas: Image.Image, W: int, H: int, t: float, avatars: list,
                        appear: float, scale: float) -> None:
    """Composite Hezekiah + Zaniah as animated circular avatars: staggered spring-in,
    gentle bob (offset phase), and a pulsing brand glow ring around each. THE AI PEOPLE
    (Ian's real characters), animated by our engine. Lower area, clears the caption."""
    U = min(W, H)
    n = len(avatars)
    dia = int(U * (0.28 if W > H else 0.40) * scale)     # big: fill the frame
    gap = int(dia * 0.22)
    total = n * dia + (n - 1) * gap
    cyc = H * (0.58 if W > H else 0.60)                   # centered block with the caption
    x0 = W / 2 - total / 2 + dia / 2
    for i, (av, ring) in enumerate(avatars):
        ap = ease_out_back(clamp01((t - 0.03 - i * 0.05) / 0.4))   # near-together entrance
        if ap <= 0.02:
            continue
        aa = clamp01(ap)
        bob = math.sin(t * math.pi * 2.4 + i * 1.3) * U * 0.011
        d = int(dia * (0.86 + 0.14 * aa))
        cx = x0 + i * (dia + gap)
        cy = cyc + bob
        pulse = 0.5 + 0.5 * math.sin(t * math.pi * 3 + i)
        glow = _radial_glow(int(d * 0.78), ring, int(120 * aa * (0.55 + 0.45 * pulse)))
        canvas.alpha_composite(glow, (int(cx - glow.size[0] / 2), int(cy - glow.size[1] / 2)))
        im = av.resize((d, d), Image.LANCZOS)
        if aa < 1.0:
            im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * aa)))
        canvas.alpha_composite(im, (int(cx - d / 2), int(cy - d / 2)))
        ring_im = Image.new("RGBA", (d + 12, d + 12), (0, 0, 0, 0))
        ImageDraw.Draw(ring_im).ellipse([4, 4, d + 8, d + 8], outline=(*ring, int(230 * aa)),
                                        width=max(3, int(d * 0.03)))
        canvas.alpha_composite(ring_im, (int(cx - (d + 12) / 2), int(cy - (d + 12) / 2)))


def draw_companion(canvas: Image.Image, W: int, H: int, t: float,
                   *, y_frac: float = 0.74, scale: float = 1.0) -> None:
    """Layer an animated AI-companion + worker character onto a scene — a SUPPLEMENT
    to the loved product screenshots (Ian 2026-07-02: 'add AI people animating…for
    supplementing'), grounded in CONTENT_MESSAGING_RESEARCH.md §2. Prefers AI-rendered
    worker art (tools/gen_worker_art.py) when present; else draws the pure-Pillow
    geometric character (zero-key fallback). Both spring in + idle-bob."""
    U = min(W, H)
    if W > H:                       # landscape: shrink + lift so it clears the frame
        scale *= 0.72
        y_frac = min(y_frac, 0.7)
    appear = ease_out_back(clamp01((t - 0.05) / 0.45))
    if appear <= 0.02:
        return
    art = _companion_art()
    if art is not None:             # the AI-rendered worker (Ian's ask) takes priority
        _companion_art_draw(canvas, W, H, t, art, appear, scale)
        return
    a = int(255 * clamp01(appear))
    bob = math.sin(t * math.pi * 3.2) * U * 0.008
    cx = W * 0.5
    cy = H * y_frac + bob
    s = U * 0.115 * scale * (0.62 + 0.38 * clamp01(appear))

    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # ── worker (hero), left of centre ──
    wx = cx - s * 1.2
    hr = s * 0.6
    body_w, body_h = s * 1.9, s * 1.35
    d.rounded_rectangle([wx - body_w / 2, cy + hr * 0.4, wx + body_w / 2, cy + hr * 0.4 + body_h],
                        radius=int(s * 0.5), fill=(*STEEL, int(a * 0.92)))                     # shoulders
    d.ellipse([wx - hr, cy - hr * 1.05, wx + hr, cy + hr * 0.95], fill=(*CLOUD, a))           # head
    ewr = hr * 0.12                                                                            # face: eyes + smile
    for ex in (wx - hr * 0.33, wx + hr * 0.33):
        d.ellipse([ex - ewr, cy - hr * 0.4 - ewr, ex + ewr, cy - hr * 0.4 + ewr], fill=(*NAVY_BOT, a))
    d.arc([wx - hr * 0.4, cy - hr * 0.28, wx + hr * 0.4, cy + hr * 0.34], 20, 160,
          fill=(*NAVY_BOT, a), width=max(2, int(hr * 0.09)))
    # hard-hat: dome sits ON the crown, brim at the hairline (clears the face)
    d.pieslice([wx - hr * 1.15, cy - hr * 1.58, wx + hr * 1.15, cy - hr * 0.38], 180, 360,
               fill=(*ORANGE, a))                                                              # dome
    d.rounded_rectangle([wx - hr * 1.32, cy - hr * 1.04, wx + hr * 1.32, cy - hr * 0.84],
                        radius=int(hr * 0.1), fill=(*ORANGE, a))                               # brim
    d.rectangle([wx - hr * 0.12, cy - hr * 1.52, wx + hr * 0.12, cy - hr * 1.32], fill=(*ORANGE_LT, a))  # ridge

    # ── AI companion hive-avatar (guide), floating upper-right with its own bob ──
    abob = math.sin(t * math.pi * 4.0 + 1.0) * U * 0.011
    ax, ay = cx + s * 1.15, cy - s * 0.95 + abob
    ar = s * 0.9
    pulse = 0.5 + 0.5 * math.sin(t * math.pi * 5)                # thinking -> answer
    glow = _radial_glow(int(ar * 2.5), BLUE, int(90 * clamp01(appear) * (0.6 + 0.4 * pulse)))
    canvas.alpha_composite(glow, (int(ax - glow.size[0] / 2), int(ay - glow.size[1] / 2)))
    hexcol = tuple(int(lerp(BLUE[i], ORANGE[i], 0.12 + 0.16 * pulse)) for i in range(3))
    d.polygon(_hexagon(ax, ay, ar, rot=0.14 * math.sin(t * math.pi * 2)),
              fill=(*hexcol, a), outline=(*ORANGE_LT, a), width=max(2, int(s * 0.07)))
    er = ar * 0.17
    for ex in (ax - ar * 0.34, ax + ar * 0.34):
        d.ellipse([ex - er, ay - er * 1.3, ex + er, ay + er * 0.7], fill=(*CLOUD, a))          # eyes
    d.arc([ax - ar * 0.44, ay - ar * 0.05, ax + ar * 0.44, ay + ar * 0.52], 18, 162,
          fill=(*CLOUD, a), width=max(2, int(s * 0.06)))                                       # smile

    # ── bond thread worker <-> AI ('your own AI', §0 pillar 2) ──
    for i in range(6):
        tt = i / 5
        px = lerp(wx + hr * 0.75, ax - ar * 0.72, tt)
        py = lerp(cy - hr * 0.25, ay + ar * 0.55, tt) + math.sin(t * math.pi * 4 + i) * U * 0.004
        rr = s * 0.08 * (0.55 + 0.45 * math.sin(t * math.pi * 3 + i))
        d.ellipse([px - rr, py - rr, px + rr, py + rr],
                  fill=(*ORANGE_LT, int(a * (0.35 + 0.6 * tt))))

    canvas.alpha_composite(ov)


def scene_stakes(canvas: Image.Image, W: int, H: int, words: list[dict],
                 local_ms: float, t: float) -> None:
    """The rationale/background beats: BIG centered kinetic text (the pain, the
    stakes, the insight) on the brand background, with the logo up top and a soft
    accent glow. No product — this is the 'why', flagship kinetic-headline style."""
    U = min(W, H)
    paste_logo(canvas, W / 2, H * 0.11, int(W * 0.24), appear=clamp01(t / 0.18))
    # a soft central glow gives the text depth
    glow = _radial_glow(int(W * 0.6), ORANGE, 26)
    canvas.alpha_composite(glow, (int(W / 2 - glow.size[0] / 2), int(H * 0.5 - glow.size[1] / 2)))
    draw_kinetic(canvas, _chunk(words, 5), local_ms, W, H, y_frac=0.30, size_frac=0.09)
    # the animated AI companions (Hezekiah + Zaniah) — only on the product-less stakes
    # beats, so they never cover the loved screenshots. Raised caption + bigger avatars
    # fill the frame (Ian 2026-07-03: "whole space is not properly utilized").
    draw_companion(canvas, W, H, t)


def scene_hero(canvas: Image.Image, W: int, H: int, screen: str, headline: str,
               label: str, t: float, callout: dict | None = None) -> None:
    appear = clamp01(t / 0.32)
    co = None
    if callout:
        # keep the named element (top of the app) framed: gentle top-biased push,
        # not the default downward pan that scrolls the alert out of view.
        kb = 0.05 + 0.13 * ease_in_out(t)
        co = dict(callout)
        co["appear"] = clamp01((t - 0.28) / 0.32)   # ring lands after the phone settles
        co["phase"] = t
    else:
        kb = ease_in_out(t)   # Ken Burns across the whole beat
    hero_scene(canvas, W, H, screen, headline, label, caption="", appear=appear, kb=kb, callout=co)


def _montage_active(words: list[dict], tour: list[tuple], local_ms: float):
    """For a word-synced montage, return (active_index, starts_ms). Each tour entry
    (trigger, screen, label) is anchored to the first narration word that matches
    its trigger; the active screen is the last whose trigger word has been spoken.
    Falls back to even spacing when the trigger isn't found in the narration."""
    starts = []
    for k, (trig, _screen, _label) in enumerate(tour):
        found = None
        for w in words or []:
            wt = w["text"].strip().lower().strip(".,!?:;")
            if wt == trig or wt.startswith(trig):
                # anchor ~120ms BEFORE the word so the screen is fully up AS it's
                # spoken (the spring-in takes a beat); tightens narration<->visual sync.
                found = max(0.0, float(w.get("start_ms", 0)) - 120.0); break
        starts.append(found)
    # fill any missing anchors by even spacing across the spoken span
    span = (words[-1]["end_ms"] if words else 1000.0)
    for k in range(len(starts)):
        if starts[k] is None:
            starts[k] = span * (k / max(1, len(tour)))
    active = 0
    for k, s in enumerate(starts):
        if s <= local_ms:
            active = k
    return active, starts


def scene_montage(canvas: Image.Image, W: int, H: int, tour: list[tuple],
                  words: list[dict], local_ms: float, dur_ms: float) -> None:
    """Word-synced product montage: the phone shows each tool EXACTLY as the
    narration names it (Log it -> Logbook, Plan it -> PM, Track it -> Analytics),
    so the visual and the spoken words agree (fixes the even-clock desync). One
    label chip names the tool; the bottom kinetic caption is drawn by the caller
    on the same word clock, so they stay in step."""
    active, starts = _montage_active(words, tour, local_ms)
    _trig, screen, label = tour[active]
    start = starts[active]
    nxt = starts[active + 1] if active + 1 < len(starts) else dur_ms
    win = max(300.0, nxt - start)
    appear = clamp01((local_ms - start) / 200.0)   # quick spring-in so it lands on the word
    kb = ease_in_out(clamp01((local_ms - start) / win))
    # no top headline during the montage: the label chip + synced caption carry it
    hero_scene(canvas, W, H, screen, "", label, caption="", appear=appear, kb=kb)


def scene_end(canvas: Image.Image, spec: dict, W: int, H: int, t: float) -> None:
    U = min(W, H)
    cx = W / 2
    # the REAL logo, springing in
    paste_logo(canvas, cx, H * 0.28, int(W * 0.44), appear=clamp01(t / 0.5), glow=True)
    d = ImageDraw.Draw(canvas)
    e = ease_out_back(clamp01(t / 0.5))
    tag = str(spec.get("endTagline") or "Built for the plant floor.")
    tf = fit_font(d, tag, "black", W * 0.86, int(U * 0.082), int(U * 0.045))
    center_text(d, cx, H * 0.42, tag, tf, CLOUD)
    a_sub = clamp01((t - 0.3) / 0.4)
    if a_sub > 0:
        sub = str(spec.get("endSub") or "Free. Mobile-first. Philippines.")
        sf = fit_font(d, sub, "semi", W * 0.86, int(U * 0.05), int(U * 0.03))
        center_text(d, cx, H * 0.53, sub, sf, tuple(int(lerp(NAVY_BOT[i], STEEL[i], a_sub)) for i in range(3)))
    a_cta = clamp01((t - 0.5) / 0.4)
    if a_cta > 0:
        cta = str(spec.get("endCta") or "workhiveph.com")
        cf = fit_font(d, cta, "bold", W * 0.7, int(U * 0.05), int(U * 0.03))
        cw = _text_w(d, cta, cf) + U * 0.07
        cy = H * 0.63
        scale = lerp(0.85, 1.0, ease_out_back(a_cta))
        chip = Image.new("RGBA", (int(cw), int(U * 0.09)), (0, 0, 0, 0))
        ImageDraw.Draw(chip).rounded_rectangle([0, 0, int(cw) - 1, int(U * 0.09) - 1],
                                               radius=int(U * 0.045), fill=(*ORANGE, 255))
        cd = ImageDraw.Draw(chip)
        center_text(cd, cw / 2, U * 0.09 / 2 - cf.size * 0.62, cta, cf, (0x13, 0x24, 0x3a))
        chip = chip.resize((max(1, int(cw * scale)), max(1, int(U * 0.09 * scale))), Image.LANCZOS)
        canvas.alpha_composite(chip, (int(cx - chip.size[0] / 2), int(cy)))


# ── shot plan + full render ──────────────────────────────────────────────────

_TOUR = [
    ("wh_logbook_clean", "Digital Logbook", "Log repairs by voice or photo"),
    ("wh_pm_clean", "PM Scheduler", "Plan preventive maintenance"),
    ("wh_analytics_clean", "Analytics Engine", "Track OEE and MTBF"),
    ("wh_inventory_clean", "Spare Parts", "Never run out of parts"),
    ("wh_alerthub_clean", "Alert Hub", "Catch problems early"),
    ("wh_skillmatrix_clean", "Skill Matrix", "Grow your team"),
    ("wh_assistant_clean", "AI Work Assistant", "Ask anything"),
    ("wh_engdesign_clean", "Engineering Calcs", "Size equipment with standards"),
]

_HERO_BY_KIND = {
    "what_it_is": ("wh_home_clean", "Home Dashboard"),
    "value": ("wh_analytics_clean", "Analytics Engine"),
    "who": ("wh_logbook_clean", "Digital Logbook"),
    "tie_in": ("wh_home_clean", "Start free"),
}

# Word-synced 3-step tour (matches the V2 script's "Log it. Plan it. Track it."):
# each (trigger, screen, label) is anchored to the narration word that names it,
# so the phone shows the tool EXACTLY when James says it (P3 sync + P4 direction).
_TOUR_SYNC = [
    ("log", "wh_logbook_clean", "Digital Logbook"),
    ("preventive", "wh_pm_clean", "PM Scheduler"),
    ("spare", "wh_inventory_clean", "Spare Parts"),
]


def _shot_for(beat: dict):
    """Return (scene_type, arg_a, arg_b, headline). Driven by the beat's explicit
    `scene` hint when present (the value-first overview), else the old kind map."""
    headline = (beat.get("caption") or "").strip()
    scene = beat.get("scene")
    if scene == "stakes":
        return ("stakes", None, None, headline)
    if scene == "intro":
        return ("intro", None, None, headline)
    if scene == "montage":
        return ("montage", _TOUR, None, headline)
    if scene == "end":
        return ("end", None, None, headline)
    if scene == "product":
        return ("hero", beat.get("screen", "wh_home_clean"), beat.get("label", "WorkHive"), headline)
    # legacy kind-based fallback
    kind = beat.get("kind", "")
    if kind == "hook":
        return ("intro", None, None, headline)
    if kind == "tour":
        return ("montage", _TOUR, None, headline)
    screen, label = _HERO_BY_KIND.get(kind, ("wh_home_clean", "WorkHive"))
    return ("hero", screen, label, headline)


# Ian's pick (2026-07-02, by ear from the A/B): the lighter lofi bed over the
# heavy dramatic cue, matching the CONTENT_AUDIO recommendation for a clear
# product explainer. (The dramatic track stays available via --music.)
DEFAULT_MUSIC = ROOT / ".tmp" / "music" / "Moonwalk_Calm_Water_Lofi_Trip-hop.mp3"


def render_overview(spec: dict, audio_dir: str | Path, out_path: str | Path,
                    aspect: str = "9:16", fps: int = 24, music: str | Path | None = "default",
                    end_hold: float | None = None) -> Path:
    """Flagship-grade product-hero render of an overview spec, reusing the already
    synthesised James audio in audio_dir (manifest.json). A faded music bed is
    mixed low under the narration (music="default" uses the flagship track; None
    disables it). `end_hold` overrides the silent brand-card hold (shorter for the
    short/ad cuts so they land nearer their length targets)."""
    from explainer_render import ASPECTS, END_HOLD_S, _master_audio, _ffmpeg_exe
    hold = END_HOLD_S if end_hold is None else float(end_hold)
    audio_dir = Path(audio_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    W, H = ASPECTS.get(aspect, ASPECTS["9:16"])
    manifest = json.loads((audio_dir / "manifest.json").read_text(encoding="utf-8"))
    mbeats = {b["beat_index"]: b for b in manifest["beats"]}

    # timeline
    segs, t = [], 0.0
    for i, beat in enumerate(spec.get("beats", [])):
        mb = mbeats.get(i)
        dur = mb["duration_s"] if mb else 2.5
        words = mb["words"] if mb else []
        segs.append({"beat": beat, "start": t, "dur": dur, "words": words, "shot": _shot_for(beat)})
        t += dur
    end_start = t
    total = t + hold
    print(f"  [studio] {aspect} {W}x{H}@{fps} · {len(segs)} scenes · {total:.1f}s")

    frames_dir = audio_dir / "_frames_studio"
    frames_dir.mkdir(exist_ok=True)
    for old in frames_dir.glob("*.png"):
        old.unlink()

    nframes = max(1, int(round(total * fps)))
    si = 0
    for fi in range(nframes):
        gt = fi / fps
        bgt = gt / max(1.0, total)
        canvas = animated_bg(W, H, bgt)
        if gt >= end_start:
            scene_end(canvas, spec, W, H, 1.0)   # settled hold (the cta beat already animated it in)
        else:
            while si + 1 < len(segs) and gt >= segs[si + 1]["start"]:
                si += 1
            seg = segs[si]
            lt = (gt - seg["start"]) / max(0.5, seg["dur"])
            local_ms = (gt - seg["start"]) * 1000.0
            kind, a, b, headline = seg["shot"]
            if kind == "stakes":
                scene_stakes(canvas, W, H, seg["words"], local_ms, lt)  # big text IS the scene
            elif kind == "intro":
                scene_intro(canvas, spec, W, H, lt)
            elif kind == "montage":
                scene_montage(canvas, W, H, _TOUR_SYNC, seg["words"], local_ms, seg["dur"] * 1000.0)
                if seg["words"]:
                    draw_kinetic(canvas, _chunk(seg["words"]), local_ms, W, H, 0.9)
            elif kind == "end":
                scene_end(canvas, spec, W, H, lt)
                if seg["words"]:
                    draw_kinetic(canvas, _chunk(seg["words"]), local_ms, W, H, 0.9, size_frac=0.042)
            else:  # hero / product
                scene_hero(canvas, W, H, a, headline, b, lt, callout=seg["beat"].get("callout"))
                if seg["words"]:
                    draw_kinetic(canvas, _chunk(seg["words"]), local_ms, W, H, 0.9)
        canvas.convert("RGB").save(frames_dir / f"f{fi:05d}.png")
        if fi % 60 == 0:
            print(f"  [studio] frame {fi}/{nframes}")

    ff = _ffmpeg_exe()
    master = audio_dir / "master.m4a"
    have_audio = _master_audio(manifest, total, master, ff)
    silent = audio_dir / "_silent_studio.mp4"
    import subprocess
    r = subprocess.run([ff, "-y", "-framerate", str(fps), "-i", str(frames_dir / "f%05d.png"),
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "19",
                        "-vf", "format=yuv420p", str(silent)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("frames->mp4 failed:\n" + (r.stderr or "")[-600:])
    mus_path = DEFAULT_MUSIC if music == "default" else (Path(music) if music else None)
    if have_audio and mus_path and mus_path.exists():
        # SIDECHAIN-DUCK the music under James (voice triggers, music dips ~8-12 dB
        # only while he speaks, swells in the gaps), then NORMALIZE the whole mix to
        # the social target -14 LUFS / -1 dBTP. Research-backed (CONTENT_AUDIO_BEST_
        # PRACTICES.md); measured -22.6 -> -14.1 LUFS. Beats a static low volume.
        fout = max(0.5, total - 1.6)
        # SFX timecodes (CONTENT_AUDIO §7, tasteful = one signature moment each):
        # a short filtered WHOOSH as the hook text lands, and a soft low IMPACT on
        # the product reveal. Both ~-11 dB, folded into the mix before loudnorm.
        hook_ms = 150
        rev_s = next((s["start"] for s in segs if s["beat"].get("scene") == "product"), 0.6)
        imp_ms = int(rev_s * 1000)
        # VO POLISH (make James premium, not robotic; CONTENT_AUDIO §8, order =
        # corrective -> character -> space): HPF 90 (rumble), +3 dB @4 kHz presence,
        # gentle 3:1 comp to even TTS dynamics, a tiny room (aecho) for depth. The
        # MUSIC is carved -4 dB @3 kHz (CONTENT_AUDIO §5) so it stops masking the
        # speech consonants. Then sidechain-duck + SFX + single-pass loudnorm.
        # NOTE: single-pass loudnorm's dynamic true-peak limiter overshoots its TP
        # target by ~0.2-0.5 dB, so aim at -1.5 dBTP to reliably land UNDER the -1
        # dBTP social ceiling (measured -0.77 at TP=-1.0 -> off-target).
        fc = (f"[1:a]aformat=channel_layouts=stereo,"
              f"highpass=f=90,equalizer=f=4000:width_type=o:width=1:g=3,"
              f"acompressor=threshold=-18dB:ratio=3:attack=15:release=200,"
              f"aecho=0.8:0.85:12:0.08,asplit=2[narrA][narrK];"
              f"[2:a]aformat=channel_layouts=stereo,highpass=f=180,"
              f"equalizer=f=3000:width_type=o:width=1.5:g=-4,afade=t=in:d=1.2,"
              f"afade=t=out:st={fout:.2f}:d=1.6,atrim=0:{total:.2f},volume=0.55[musraw];"
              f"[musraw][narrK]sidechaincompress=threshold=0.04:ratio=9:attack=15:release=380:makeup=1[musduck];"
              f"[3:a]lowpass=f=170,afade=t=out:st=0.06:d=0.5,volume=0.30,"
              f"adelay={imp_ms}|{imp_ms}[imp];"
              f"[4:a]highpass=f=350,lowpass=f=6500,afade=t=in:d=0.16,afade=t=out:st=0.22:d=0.30,"
              f"volume=0.26,adelay={hook_ms}|{hook_ms}[wh];"
              f"[narrA][musduck][imp][wh]amix=inputs=4:normalize=0:dropout_transition=0,"
              f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[aout]")
        r = subprocess.run([ff, "-y", "-i", str(silent), "-i", str(master),
                            "-stream_loop", "-1", "-i", str(mus_path),
                            "-f", "lavfi", "-i", "sine=frequency=62:duration=0.6",
                            "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:a=0.4",
                            "-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_path)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("music mux failed:\n" + (r.stderr or "")[-600:])
        print(f"  [studio] mixed music bed: {mus_path.name}")
    elif have_audio:
        r = subprocess.run([ff, "-y", "-i", str(silent), "-i", str(master), "-map", "0:v",
                            "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("mux failed:\n" + (r.stderr or "")[-600:])
    else:
        out_path.write_bytes(silent.read_bytes())
    print(f"  [studio] OK -> {out_path} ({out_path.stat().st_size // 1024} KB)")
    return out_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--overview":
        from explainer_render import overview_spec
        aspect = sys.argv[2] if len(sys.argv) > 2 else "9:16"
        render_overview(overview_spec(), ".tmp/explainer_audio/workhive_overview",
                        ".tmp/explainer_out/workhive_overview_studio.mp4", aspect=aspect)
    else:
        out = ROOT / ".tmp" / "_studio_proof.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        proof_frame().save(out)
        print(f"proof -> {out}")
