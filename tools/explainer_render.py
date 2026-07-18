#!/usr/bin/env python3
"""
explainer_render.py — the "WorkHive Explains" educational video renderer.
=========================================================================
Pure-Python (Pillow + ffmpeg), ZERO new dependencies. Reimplements the beloved
flagship visual DNA ourselves (navy gradient + aurora orbs + orange accents +
kinetic word-by-word captions) so our educational videos are 100% WorkHive brand
with NO watermark and NO Nano-Banana background. Hardens the POC
(tools/explainer_poc.py): auto-fit text (the POC's one known overflow bug),
multi-aspect canvas, an `explainer_viz` chart library (OEE bars + formula), and
narration-synced kinetic captions driven by edge-tts word boundaries
(tools/explainer_voice.py) — NO Whisper.

Pipeline (roadmap CONTENT_CREATION_ROADMAP.md sec 8/9):
    ExplainerSpec (cmd_explainer) -> synth voice + word timings (explainer_voice)
    -> render frames (this) -> ffmpeg stitch + mux James narration -> .mp4

CLI:
    # full build: synth voice for the spec, then render the video
    python tools/explainer_render.py build --spec <spec.json> --out <out.mp4> [--aspect 9:16] [--fps 24]
    # render only (audio already synthesised into --audio dir)
    python tools/explainer_render.py render --spec <spec.json> --audio <dir> --out <out.mp4>
    # smoke test: render the built-in verified OEE spec end to end
    python tools/explainer_render.py --demo
    python tools/explainer_render.py --self-test   # fast, no network/ffmpeg needed
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# ── WorkHive brand tokens (from the flagship study; identical to the POC) ─────
NAVY_TOP = (0x13, 0x24, 0x3a)
NAVY_BOT = (0x23, 0x34, 0x4e)
ORANGE = (0xF7, 0xA2, 0x1B)
ORANGE_LT = (0xFD, 0xB9, 0x4A)
BLUE = (0x29, 0xB6, 0xD9)
CLOUD = (0xF4, 0xF6, 0xFA)
STEEL = (0x9F, 0xB0, 0xC3)

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}

# A brand font we own (OFL) dropped in assets/fonts/ is preferred; the POC's
# Segoe UI / Arial Black chain is the always-present fallback so a render never
# fails for lack of a font file.
_FONT_DIR = ROOT / "assets" / "fonts"
_FONT_CHAINS = {
    "black": [_FONT_DIR / "Poppins-Black.ttf", "C:/Windows/Fonts/seguibl.ttf",
              "C:/Windows/Fonts/ariblk.ttf"],
    "bold":  [_FONT_DIR / "Poppins-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf",
              "C:/Windows/Fonts/arialbd.ttf"],
    "semi":  [_FONT_DIR / "Poppins-SemiBold.ttf", "C:/Windows/Fonts/seguisb.ttf",
              "C:/Windows/Fonts/segoeuib.ttf"],
    "reg":   [_FONT_DIR / "Poppins-Regular.ttf", "C:/Windows/Fonts/segoeui.ttf",
              "C:/Windows/Fonts/arial.ttf"],
}
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(size: int, weight: str = "black") -> ImageFont.FreeTypeFont:
    size = max(8, int(size))
    key = (weight, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for cand in _FONT_CHAINS.get(weight, _FONT_CHAINS["reg"]):
        try:
            if os.path.exists(str(cand)):
                f = ImageFont.truetype(str(cand), size)
                _FONT_CACHE[key] = f
                return f
        except Exception:
            continue
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


# ── geometry / text helpers ───────────────────────────────────────────────────

def _text_w(d: ImageDraw.ImageDraw, s: str, f: ImageFont.FreeTypeFont) -> float:
    return d.textlength(s, font=f)


def fit_font(d: ImageDraw.ImageDraw, text: str, weight: str, max_w: float,
             start: int, min_size: int = 24, spacing: int = 0) -> ImageFont.FreeTypeFont:
    """Largest font (from `start` down to `min_size`) whose rendered `text` fits
    in `max_w`. This is the POC's ONE known fix: nothing overflows the frame."""
    size = start
    while size > min_size:
        f = font(size, weight)
        w = _text_w(d, text, f)
        if spacing:
            w += spacing * max(0, len(text) - 1)
        if w <= max_w:
            return f
        size -= 3
    return font(min_size, weight)


def center_text(d, cx, y, text, f, fill, spacing=0):
    if spacing:
        total = sum(_text_w(d, ch, f) + spacing for ch in text) - spacing
        x = cx - total / 2
        for ch in text:
            d.text((x, y), ch, font=f, fill=fill)
            x += _text_w(d, ch, f) + spacing
        return
    d.text((cx - _text_w(d, text, f) / 2, y), text, font=f, fill=fill)


def wrap_words(d, words: list[str], f, max_w: float) -> list[list[str]]:
    """Greedy word-wrap: returns lines (each a list of words) fitting max_w."""
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and _text_w(d, trial, f) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


# ── background (POC-proven; parameterised by canvas size) ─────────────────────

_BG_CACHE: dict[tuple[int, int], Image.Image] = {}


def background(W: int, H: int) -> Image.Image:
    """Navy vertical gradient + blurred orange/blue aurora orbs + vignette.
    Cached per canvas size (the gradient is the expensive part)."""
    if (W, H) in _BG_CACHE:
        return _BG_CACHE[(W, H)].copy()
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):
        t = y / H
        r = int(NAVY_TOP[0] + (NAVY_BOT[0] - NAVY_TOP[0]) * t)
        g = int(NAVY_TOP[1] + (NAVY_BOT[1] - NAVY_TOP[1]) * t)
        b = int(NAVY_TOP[2] + (NAVY_BOT[2] - NAVY_TOP[2]) * t)
        row = bytes((r, g, b)) * W
        bg.paste(Image.frombytes("RGB", (W, 1), row), (0, y))
    orb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    od.ellipse([-W * 0.2, -H * 0.14, W * 0.52, H * 0.27], fill=(*ORANGE, 60))
    od.ellipse([W * 0.48, H * 0.68, W * 1.22, H * 1.02], fill=(*BLUE, 48))
    orb = orb.filter(ImageFilter.GaussianBlur(int(W * 0.16)))
    bg = Image.alpha_composite(bg.convert("RGBA"), orb)
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([-W * 0.25, H * 0.06, W * 1.25, H * 0.94], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(int(W * 0.2)))
    dark = Image.new("RGBA", (W, H), (8, 12, 20, 150))
    bg = Image.composite(bg, Image.alpha_composite(bg, dark), mask)
    out = bg.convert("RGB")
    _BG_CACHE[(W, H)] = out
    return out.copy()


# ── explainer_viz : our own raster chart primitives (mirrors article_viz.py) ──

def viz_oee_formula(d: ImageDraw.ImageDraw, W: int, cx: float, y: float) -> None:
    """Color-coded 'Availability x Performance x Quality' formula tease,
    auto-fit to the frame width (the POC overflowed here)."""
    parts = [("Availability", BLUE), ("  x  ", STEEL), ("Performance", ORANGE),
             ("  x  ", STEEL), ("Quality", BLUE)]
    plain = "".join(t for t, _ in parts)
    f = fit_font(d, plain, "bold", W * 0.9, start=int(W * 0.062), min_size=int(W * 0.03))
    total = sum(_text_w(d, t, f) for t, _ in parts)
    x = cx - total / 2
    for t, col in parts:
        d.text((x, y), t, font=f, fill=col)
        x += _text_w(d, t, f)


def viz_feature_grid(d: ImageDraw.ImageDraw, W: int, box: tuple[int, int, int, int],
                     features: list[str], cols: int = 2) -> None:
    """A grid of rounded feature-name chips (the WorkHive tool tour). Used by the
    platform-overview template. Chip text auto-fits so long tool names never
    overflow the chip."""
    x0, y0, x1, y1 = box
    feats = [f for f in (features or []) if f][:8]
    if not feats:
        return
    rows = math.ceil(len(feats) / cols)
    gx, gy = (x1 - x0) * 0.05, (y1 - y0) * 0.09
    cw = ((x1 - x0) - gx * (cols - 1)) / cols
    ch = ((y1 - y0) - gy * (rows - 1)) / rows
    accents = [ORANGE, BLUE]
    for i, name in enumerate(feats):
        r, c = divmod(i, cols)
        cx0 = x0 + c * (cw + gx)
        cy0 = y0 + r * (ch + gy)
        d.rounded_rectangle([cx0, cy0, cx0 + cw, cy0 + ch], radius=int(ch * 0.26),
                            fill=(0x1b, 0x2d, 0x45), outline=accents[i % 2], width=3)
        # accent dot
        dot = ch * 0.18
        d.ellipse([cx0 + cw * 0.10, cy0 + ch / 2 - dot / 2,
                   cx0 + cw * 0.10 + dot, cy0 + ch / 2 + dot / 2], fill=accents[i % 2])
        f = fit_font(d, name, "bold", cw * 0.66, start=int(ch * 0.34), min_size=int(W * 0.022))
        d.text((cx0 + cw * 0.20, cy0 + ch / 2 - f.size * 0.6), name, font=f, fill=CLOUD)


def viz_oee_bars(d: ImageDraw.ImageDraw, W: int, box: tuple[int, int, int, int],
                 A: float, P: float, Q: float, OEE: float) -> None:
    """Three factor bars (A, P, Q) multiplying down to the OEE bar. Heights are
    proportional to value; the '=' and the OEE % teach that three high numbers
    still multiply to a lower one."""
    x0, y0, x1, y1 = box
    plot_h = (y1 - y0) * 0.72
    base_y = y1 - (y1 - y0) * 0.16
    bars = [("A", A, BLUE), ("P", P, ORANGE), ("Q", Q, BLUE), ("OEE", OEE, ORANGE_LT)]
    n = len(bars)
    gap = (x1 - x0) * 0.06
    bw = ((x1 - x0) - gap * (n - 1)) / n
    lab_f = font(int(W * 0.032), "bold")
    val_f = font(int(W * 0.030), "black")
    for i, (label, val, col) in enumerate(bars):
        bx = x0 + i * (bw + gap)
        h = plot_h * max(0.04, min(1.0, val))
        top = base_y - h
        # track
        d.rounded_rectangle([bx, base_y - plot_h, bx + bw, base_y],
                            radius=int(bw * 0.12), fill=(255, 255, 255, 0),
                            outline=(80, 96, 118), width=2)
        # bar
        d.rounded_rectangle([bx, top, bx + bw, base_y], radius=int(bw * 0.12), fill=col)
        # value on top
        center_text(d, bx + bw / 2, top - W * 0.045, f"{val * 100:.0f}%", val_f, CLOUD)
        # axis label
        center_text(d, bx + bw / 2, base_y + W * 0.02, label, lab_f,
                    ORANGE if label == "OEE" else STEEL)
        # multiply / equals glyph between bars
        if i < n - 1:
            glyph = "=" if label == "Q" else "x"
            gx = bx + bw + gap / 2
            center_text(d, gx, base_y - plot_h * 0.55, glyph, font(int(W * 0.04), "black"), STEEL)


# ── scene layers (each rendered ONCE, then copied per frame) ──────────────────

def _kicker(d, u, cx, y, spec):
    """Draw the orange letter-spaced series kicker + accent rule at top `y`.
    `u` is the sizing unit = min(W, H) so fonts stay sane on any aspect."""
    series = (spec.get("series") or "WorkHive Explains").upper()
    center_text(d, cx, y, series, font(int(u * 0.032), "bold"), ORANGE, spacing=int(u * 0.009))
    d.rounded_rectangle([cx - u * 0.065, y + u * 0.05, cx + u * 0.065, y + u * 0.058],
                        radius=4, fill=ORANGE)


def title_card(spec: dict, W: int, H: int) -> Image.Image:
    """Beat-0 concept title card. A CENTERED vertical stack (aspect-robust): the
    old fixed H-fractions overlapped in landscape because fonts scale with the
    short side U=min(W,H) while height is tight. The feature grid shows only in
    portrait (no room for it beside a big title in 16:9)."""
    img = background(W, H)
    d = ImageDraw.Draw(img)
    cx, U = W / 2, min(W, H)
    portrait = H >= W * 1.2

    title = str(spec.get("title") or spec.get("concept") or "OEE")
    tf = fit_font(d, title, "black", W * 0.9, start=int(U * 0.24), min_size=int(U * 0.08))
    sub = str(spec.get("subtitle") or "")
    sf = fit_font(d, sub, "black", W * 0.9, start=int(U * 0.072), min_size=int(U * 0.034)) if sub else None
    show_grid = bool(portrait and spec.get("kind") == "overview" and spec.get("features"))
    show_formula = bool(spec.get("formula") or spec.get("concept") == "OEE") and not show_grid
    std = str(spec.get("standard") or "")
    show_chip = bool(std and not show_grid)

    gap = U * 0.045
    heights = [U * 0.11, tf.size * 1.02]                    # kicker, title
    if sf: heights.append(sf.size * 1.25)                   # subtitle
    if show_grid: heights.append(H * 0.30)                  # feature grid
    elif show_formula: heights.append(U * 0.10)             # OEE formula
    if show_chip: heights.append(U * 0.07)                  # standard chip
    total = sum(heights) + gap * (len(heights) - 1)
    y = max(U * 0.06, (H - total) / 2)

    _kicker(d, U, cx, y, spec); y += heights[0] + gap
    center_text(d, cx, y, title, tf, CLOUD); y += tf.size * 1.02 + gap
    if sf:
        center_text(d, cx, y, sub, sf, CLOUD); y += sf.size * 1.25 + gap
    if show_grid:
        viz_feature_grid(d, U, (int(W * 0.10), int(y), int(W * 0.90), int(y + H * 0.30)),
                         spec.get("features"), cols=2); y += H * 0.30 + gap
    elif show_formula:
        viz_oee_formula(d, U, cx, y); y += U * 0.10 + gap
    if show_chip:
        cf = font(int(U * 0.028), "semi")
        cw = _text_w(d, std, cf) + U * 0.04
        d.rounded_rectangle([cx - cw / 2, y, cx + cw / 2, y + U * 0.05],
                            radius=int(U * 0.025), outline=STEEL, width=2)
        center_text(d, cx, y + U * 0.008, std, cf, STEEL)
    return img


def end_card(spec: dict, W: int, H: int) -> Image.Image:
    """Locked brand closer (flagship end-card DNA), centered + aspect-robust."""
    img = background(W, H)
    d = ImageDraw.Draw(img)
    cx, U = W / 2, min(W, H)
    tag = str(spec.get("endTagline") or "Built for the plant floor.")
    tf = fit_font(d, tag, "black", W * 0.86, start=int(U * 0.08), min_size=int(U * 0.042))
    sub = str(spec.get("endSub") or "Free. Mobile-first. Philippines.")
    sf = fit_font(d, sub, "semi", W * 0.86, start=int(U * 0.048), min_size=int(U * 0.03))
    cta = str(spec.get("endCta") or "workhiveph.com")
    cf = fit_font(d, cta, "bold", W * 0.7, start=int(U * 0.048), min_size=int(U * 0.03))

    gap = U * 0.05
    heights = [U * 0.11, tf.size * 1.05, sf.size * 1.25, U * 0.09]
    total = sum(heights) + gap * (len(heights) - 1)
    y = max(U * 0.08, (H - total) / 2)

    _kicker(d, U, cx, y, spec); y += heights[0] + gap
    center_text(d, cx, y, tag, tf, CLOUD); y += tf.size * 1.05 + gap
    center_text(d, cx, y, sub, sf, STEEL); y += sf.size * 1.25 + gap
    cw = _text_w(d, cta, cf) + U * 0.07
    d.rounded_rectangle([cx - cw / 2, y, cx + cw / 2, y + U * 0.08],
                        radius=int(U * 0.04), fill=ORANGE)
    center_text(d, cx, y + U * 0.018, cta, cf, (0x13, 0x24, 0x3a))
    return img


def beat_static(beat: dict, spec: dict, W: int, H: int) -> Image.Image:
    """The non-animating layer for a teach/rationale/worked/takeaway/tie-in beat:
    background + optional headline + optional viz. The kinetic caption is drawn
    per-frame ON TOP of a copy of this."""
    img = background(W, H)
    d = ImageDraw.Draw(img)
    cx, U = W / 2, min(W, H)
    kind = beat.get("kind", "")
    _kicker(d, U, cx, H * 0.08, spec)
    headline = str(beat.get("caption") or "")
    if headline:
        hf = fit_font(d, headline, "black", W * 0.88, start=int(U * 0.075), min_size=int(U * 0.04))
        lines = wrap_words(d, headline.split(), hf, W * 0.88)
        y = H * 0.15
        for ln in lines[:2]:
            center_text(d, cx, y, " ".join(ln), hf, CLOUD)
            y += hf.size * 1.12
    viz = beat.get("viz")
    we = spec.get("workedExample", {}) or {}
    if viz == "feature_grid":
        viz_feature_grid(d, U, (int(W * 0.08), int(H * 0.30), int(W * 0.92), int(H * 0.66)),
                         beat.get("features") or spec.get("features"), cols=2)
    elif viz == "oee_formula":
        viz_oee_formula(d, U, cx, H * 0.42)
    elif viz == "oee_bars":
        A = float(we.get("availability", 0.9)); P = float(we.get("performance", 0.95))
        Q = float(we.get("quality", 0.99)); OEE = float(we.get("oee", round(A * P * Q, 3)))
        viz_oee_bars(d, U, (int(W * 0.08), int(H * 0.30), int(W * 0.92), int(H * 0.58)), A, P, Q, OEE)
        ex = we.get("asset") or we.get("plant")
        if ex:
            center_text(d, cx, H * 0.60, str(ex), font(int(U * 0.03), "semi"), STEEL)
    elif kind == "takeaway":
        # a "Do this Monday" badge above the caption band
        badge = "DO THIS MONDAY"
        bf = font(int(U * 0.032), "bold")
        bw = _text_w(d, badge, bf) + U * 0.05
        by = H * 0.40
        d.rounded_rectangle([cx - bw / 2, by, cx + bw / 2, by + U * 0.055],
                            radius=int(U * 0.027), fill=ORANGE)
        center_text(d, cx, by + U * 0.01, badge, bf, (0x13, 0x24, 0x3a))
    return img


# ── kinetic caption (word-by-word, synced to edge-tts word boundaries) ────────

def _chunk_words(words: list[dict], max_per: int = 6) -> list[list[dict]]:
    """Group narration words into short mute-readable chunks (<= max_per words),
    breaking early on sentence-ending punctuation so phrases stay natural."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        ends_sentence = w["text"].strip().endswith((".", "?", "!", ":"))
        if len(cur) >= max_per or ends_sentence:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def draw_caption(base: Image.Image, chunks: list[list[dict]], local_ms: float,
                 W: int, H: int) -> Image.Image:
    """Draw the active caption chunk onto a copy of `base`, revealing words as
    James speaks them. Returns a new RGB image (base is never mutated)."""
    if not chunks:
        return base.copy()
    # active chunk = the last chunk whose first word has started
    active = chunks[0]
    for ch in chunks:
        if ch[0]["start_ms"] <= local_ms:
            active = ch
        else:
            break
    U = min(W, H)
    tokens = [w["text"] for w in active]
    line_text = " ".join(tokens)
    f = fit_font(ImageDraw.Draw(base), line_text, "black", W * 0.9,
                 start=int(U * 0.072), min_size=int(U * 0.044))
    d0 = ImageDraw.Draw(base)
    lines = wrap_words(d0, tokens, f, W * 0.9)
    line_h = f.size * 1.14
    total_h = line_h * len(lines)
    y = H * 0.80 - total_h / 2
    img = base.copy()
    d = ImageDraw.Draw(img)
    # rebuild per-word timing lookup for the active chunk
    tw = {w["text"]: w for w in active}
    seen: dict[str, int] = {}
    idx = 0
    for ln in lines:
        total_w = _text_w(d, " ".join(ln), f)
        x = W / 2 - total_w / 2
        for word in ln:
            # handle duplicate words within a chunk by positional order
            occ = seen.get(word, 0); seen[word] = occ + 1
            w_meta = active[idx] if idx < len(active) else tw.get(word, {"start_ms": 0})
            idx += 1
            started = w_meta.get("start_ms", 0) <= local_ms
            speaking = w_meta.get("start_ms", 0) <= local_ms <= w_meta.get("end_ms", 1e12)
            if started:
                col = ORANGE if speaking else CLOUD
                # subtle spring-up as it lands
                dt = max(0.0, min(1.0, (local_ms - w_meta.get("start_ms", 0)) / 160.0))
                ease = 1 - pow(1 - dt, 3)
                dy = (1 - ease) * (W * 0.012)
                d.text((x, y + dy), word, font=f, fill=col)
            else:
                d.text((x, y), word, font=f, fill=(64, 78, 100))  # ghost upcoming word
            x += _text_w(d, word + " ", f)
        y += line_h
    return img


# ── the render ────────────────────────────────────────────────────────────────

END_HOLD_S = 2.6  # silent hold on the brand end card


def _build_timeline(spec: dict, manifest: dict):
    """Return (segments, total_s). Each segment: dict with kind, start, dur,
    static-layer key, words. Beat-0 hook shows the title card."""
    W = H = 0  # canvas set later; timeline is size-agnostic
    segs = []
    t = 0.0
    beats = spec.get("beats", [])
    mbeats = {b["beat_index"]: b for b in manifest["beats"]}
    for i, beat in enumerate(beats):
        mb = mbeats.get(i)
        dur = mb["duration_s"] if mb else 2.0
        words = mb["words"] if mb else []
        segs.append({"kind": beat.get("kind", ""), "beat": beat,
                     "start": t, "dur": dur, "words": words, "idx": i})
        t += dur
    segs.append({"kind": "end", "beat": {"kind": "end"}, "start": t,
                 "dur": END_HOLD_S, "words": [], "idx": len(beats)})
    return segs, t + END_HOLD_S


def _master_audio(manifest: dict, total_s: float, out_audio: Path, ff: str) -> bool:
    """Concat all beat mp3s and pad with silence to total_s (covers the silent
    end card). Returns True on success."""
    mp3s = [b["mp3"] for b in manifest["beats"] if Path(b["mp3"]).exists()]
    if not mp3s:
        return False
    inputs = []
    for m in mp3s:
        inputs += ["-i", m]
    n = len(mp3s)
    concat = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[c];"
    # pad the concatenated narration out to the full video length
    filt = concat + f"[c]apad=whole_dur={total_s:.3f},aformat=sample_rates=44100:channel_layouts=stereo[a]"
    cmd = [ff, "-y", *inputs, "-filter_complex", filt, "-map", "[a]",
           "-c:a", "aac", "-b:a", "160k", str(out_audio)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("  [render] master-audio ffmpeg error:\n  " + (r.stderr or "")[-400:])
        return False
    return True


def render_from_spec(spec: dict, audio_dir: str | Path, out_path: str | Path,
                     aspect: str = "9:16", fps: int = 24) -> Path:
    """Render one ExplainerSpec + its synthesised audio into a branded mp4."""
    audio_dir = Path(audio_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    W, H = ASPECTS.get(aspect, ASPECTS["9:16"])
    manifest = json.loads((audio_dir / "manifest.json").read_text(encoding="utf-8"))

    segs, total_s = _build_timeline(spec, manifest)
    print(f"  [render] {aspect} {W}x{H} @ {fps}fps · {len(segs)} scenes · {total_s:.1f}s")

    # pre-render each scene's static layer ONCE
    statics: dict[int, Image.Image] = {}
    chunks_by_seg: dict[int, list] = {}
    for si, seg in enumerate(segs):
        beat = seg["beat"]
        if seg["kind"] == "end":
            statics[si] = end_card(spec, W, H)
        elif seg["idx"] == 0:
            statics[si] = title_card(spec, W, H)   # hook rides the title card
        else:
            statics[si] = beat_static(beat, spec, W, H)
        chunks_by_seg[si] = _chunk_words(seg["words"]) if seg["idx"] != 0 else []

    frames_dir = audio_dir / "_frames"
    frames_dir.mkdir(exist_ok=True)
    for old in frames_dir.glob("*.png"):
        old.unlink()

    nframes = max(1, int(round(total_s * fps)))
    seg_i = 0
    for fi in range(nframes):
        gt = fi / fps
        while seg_i + 1 < len(segs) and gt >= segs[seg_i + 1]["start"]:
            seg_i += 1
        seg = segs[seg_i]
        base = statics[seg_i]
        chunks = chunks_by_seg.get(seg_i)
        if chunks:
            local_ms = (gt - seg["start"]) * 1000.0
            frame = draw_caption(base, chunks, local_ms, W, H)
        else:
            frame = base  # static scene (title card / end card): no per-frame work
        frame.save(frames_dir / f"f{fi:05d}.png")
        if fi % 60 == 0:
            print(f"  [render] frame {fi}/{nframes}")

    ff = _ffmpeg_exe()
    master = audio_dir / "master.m4a"
    have_audio = _master_audio(manifest, total_s, master, ff)

    silent = audio_dir / "_silent.mp4"
    cmd_v = [ff, "-y", "-framerate", str(fps), "-i", str(frames_dir / "f%05d.png"),
             "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "19",
             "-vf", "format=yuv420p", str(silent)]
    r = subprocess.run(cmd_v, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("frame->mp4 ffmpeg failed:\n" + (r.stderr or "")[-600:])

    if have_audio:
        cmd_m = [ff, "-y", "-i", str(silent), "-i", str(master),
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                 "-shortest", str(out_path)]
        r = subprocess.run(cmd_m, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("mux ffmpeg failed:\n" + (r.stderr or "")[-600:])
    else:
        print("  [render] no narration audio — writing silent video")
        out_path.write_bytes(silent.read_bytes())

    print(f"  [render] OK -> {out_path}  ({out_path.stat().st_size // 1024} KB)")
    return out_path


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def build_from_spec(spec_path: str | Path, out_path: str | Path,
                    aspect: str = "9:16", fps: int = 24) -> Path:
    """Full pipeline: synth James narration + word timings for the spec, then
    render the video."""
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    import explainer_voice as ev
    audio_dir = Path(".tmp") / "explainer_audio" / spec_path.stem
    print(f"  [build] synthesising James narration for '{spec.get('concept','?')}'...")
    ev.synth_spec(spec, audio_dir)
    return render_from_spec(spec, audio_dir, out_path, aspect=aspect, fps=fps)


# ── built-in verified OEE spec (canonical pilot; also the demo/self-test) ─────

def demo_spec() -> dict:
    # A, P, Q chosen so the fact gate has a clean, teachable product:
    #   0.90 * 0.95 * 0.99 = 0.84645  ->  84.6% OEE (just under 85% World Class).
    A, P, Q = 0.90, 0.95, 0.99
    oee = round(A * P * Q, 3)
    return {
        "concept": "OEE",
        "title": "OEE",
        "subtitle": "Overall Equipment Effectiveness",
        "standard": "ISO 22400-2",
        "series": "WorkHive Explains",
        "formula": "Availability x Performance x Quality",
        "workedExample": {
            "plant": "a Laguna bottling line",
            "asset": "Filler CT-001, Laguna bottling line",
            "availability": A, "performance": P, "quality": Q, "oee": oee,
            "band": "World Class is 85%",
        },
        "beats": [
            {"kind": "hook",
             "narration": "Three of your best numbers can still hide a problem on the plant floor."},
            {"kind": "rationale",
             "caption": "Why one number wins",
             "narration": "A machine can look busy, run fast, and make good parts, and still quietly lose you a whole shift. One number catches all three at once."},
            {"kind": "teach", "viz": "oee_formula",
             "caption": "OEE is three factors",
             "narration": "OEE is Availability times Performance times Quality. Availability is uptime. Performance is speed. Quality is good parts."},
            {"kind": "worked", "viz": "oee_bars",
             "caption": "Watch them multiply down",
             "narration": "On a Laguna bottling line, availability is ninety percent, performance ninety five, quality ninety nine. Multiply them and OEE is only eighty five percent."},
            {"kind": "takeaway",
             "caption": "Fix your smallest factor first",
             "narration": "Your lowest factor drags the whole number down. Find it, fix that one first, and OEE climbs fastest."},
            {"kind": "tie_in",
             "caption": "See your live OEE free",
             "narration": "WorkHive shows your live OEE against the ISO world class benchmark, for free.",
             "learn": "/learn/oee/", "tool": "Analytics"},
        ],
        "endTagline": "Built for the plant floor.",
        "endSub": "Free. Mobile-first. Philippines.",
        "endCta": "workhiveph.com · start free",
    }


# The eight real WorkHive tools (grounded in the live platform / SCREEN_CATALOG).
# The overview names ONLY these — the gate rejects any invented tool.
WORKHIVE_TOOLS = [
    "Digital Logbook", "PM Scheduler", "Analytics Engine", "Spare Parts Inventory",
    "Alert Hub", "Skill Matrix", "AI Work Assistant", "Engineering Calculators",
]


def _overview_meta() -> dict:
    """Shared spec metadata for all three overview cuts (main / short / ad)."""
    return {
        "kind": "overview",
        "concept": "WorkHive",
        "title": "WorkHive",
        "subtitle": "Free Industrial Intelligence Tools",
        "series": "WorkHive",
        "features": WORKHIVE_TOOLS,
        "endTagline": "Built for the plant floor.",
        "endSub": "Free. Mobile-first. Philippines.",
        "endCta": "workhiveph.com · start free",
    }


def overview_spec() -> dict:
    """The WorkHive platform overview (Ian's pilot), VALUE-FIRST + V2-TRIMMED.
    Opens on the rationale + background (the 3 AM breakdown, plants running on
    paper, the insight that the machine warns you first) BEFORE the product, per
    the roadmap's value-first anatomy. V2 (research-grounded, CONTENT_V2_REFINEMENT_
    ROADMAP §P2): narration trimmed to ~95 words (lands <=60s at James's ~140 wpm,
    down from 74s/167w); a QUANTIFIED hook ("one breakdown just cost you a whole
    shift"); every sentence <=~10 words; the tour framed as a 3-step plan
    (Log it. Plan it. Track it.); worker-as-hero "you'll" voice. Grounded in the
    real tool set + the real on-screen asset (TX-001 96% risk, 9-day MTBF).
    Selected via a 4-lens draft/judge/synthesize panel (pas-hard spine)."""
    spec = _overview_meta()
    spec["beats"] = [
        # ── the "why" (value-first) — MEMORY frame, animated AI companion on-screen ──
        {"kind": "hook", "scene": "stakes", "caption": "You already solved this.",
         "narration": "You already solved this problem once. Can you remember how?"},
        {"kind": "background", "scene": "stakes", "caption": "Knowledge walks out the door.",
         "narration": "Every fix and every lesson lives in one person's head. When they leave, it is gone."},
        {"kind": "rationale", "scene": "stakes", "caption": "What if work remembered itself?",
         "narration": "What if your work remembered itself, so nothing is ever learned twice?"},
        # ── the product as the ANSWER (the loved screenshots) ──
        {"kind": "reveal", "scene": "product", "screen": "wh_home_clean",
         "label": "Your Memory", "caption": "WorkHive is your memory.",
         "narration": "WorkHive is your memory, built for Filipino industry. Log it once, find it forever."},
        {"kind": "tour", "scene": "montage", "caption": "Logbook. PMs. Parts.",
         "narration": "Your logbook, your preventive PMs, your spare parts, all searchable in seconds."},
        # ── build your own AI (the differentiator) — companion scene again ──
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah guide you.",
         "narration": "And your own AI companions, Hezekiah and Zaniah, guide you along the way."},
        {"kind": "payoff", "scene": "stakes", "caption": "The fix, and the plan.",
         "narration": "Hezekiah knows the technical fix. Zaniah knows the plan. Both learn from everything you log."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Start your free memory at workhiveph.com.",
         "learn": "/", "tool": ""},
    ]
    return spec


def overview_spec_short() -> dict:
    """A <=30s DISCOVERY cut (Reels/Shorts/TikTok) from the same assets + voice:
    hook -> product -> a tight 3-step tour -> CTA (~49 words, ~25s). Same grounding
    and gate-clean copy as the main cut, just fewer beats (CONTENT_V2 §P2)."""
    spec = _overview_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "You already solved this.",
         "narration": "You already solved this problem once. Can you remember how?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_home_clean",
         "label": "Your Memory", "caption": "WorkHive is your memory.",
         "narration": "WorkHive is your memory, built for Filipino industry. Log it once, find it forever."},
        {"kind": "tour", "scene": "montage", "caption": "Logbook. PMs. Parts.",
         "narration": "Your logbook, preventive PMs, and spare parts, all searchable in seconds."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Meet Hezekiah and Zaniah, your free AI companions. Start at workhiveph.com.",
         "learn": "/", "tool": ""},
    ]
    return spec


def overview_spec_ad() -> dict:
    """A ~15s paid-AD cut: one stake -> one product line -> CTA (~34 words, ~15s).
    Carries >=3 real tool keywords (oee, log, preventive) so it clears the same
    overview gate as the longer cuts (CONTENT_V2 §P2)."""
    spec = _overview_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "You solved this once.",
         "narration": "You solved this once. Can you remember how?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_home_clean",
         "label": "Your Memory", "caption": "WorkHive is your memory.",
         "narration": "WorkHive is your memory for Filipino plants. Log fixes, plan preventive PMs, find spare parts."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Meet Hezekiah and Zaniah, your free AI companions. Start at workhiveph.com.",
         "learn": "/", "tool": ""},
    ]
    return spec


def _asset_brain_meta() -> dict:
    """Shared meta for the Asset Brain 360 feature spot. kind='overview' so it
    clears the overview gate (says-what-it-is + >=3 real tools); features stay the
    real WORKHIVE_TOOLS so features_real passes."""
    spec = _overview_meta()
    spec["concept"] = "WorkHive Asset Brain 360"
    spec["subtitle"] = "Asset Brain 360"
    spec["endTagline"] = "Every machine, one memory."
    return spec


def asset_brain_spec() -> dict:
    """Feature spot for Asset Hub / Asset Brain 360 — the 39th /learn/ article's
    topic (2026-07-02). Value-first: the scattered-history pain, WorkHive as the
    answer, a tool-named tour (logbook + preventive PM + spare parts + a risk
    score that folded here from predictive.html), a PH anchor (Cabuyao pump
    P-204B), CTA to the new article + /asset-hub.html. Grounded in real asset-hub
    affordances: QR scan, one merged timeline, sister machines, per-asset AI Q+A,
    the per-asset predictive risk score. ~90 words -> ~55s at James's ~140 wpm."""
    spec = _asset_brain_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Every machine has a memory.",
         "narration": "Every machine has a memory. Can you read all of it?"},
        {"kind": "background", "scene": "stakes", "caption": "History scattered everywhere.",
         "narration": "That history is scattered across paper logs, phone photos, and people's heads."},
        {"kind": "rationale", "scene": "stakes", "caption": "One machine. One memory.",
         "narration": "Every fix, every part, every warning belongs in one place."},
        {"kind": "reveal", "scene": "product", "screen": "wh_assethub_clean",
         "label": "Asset Brain 360", "caption": "Scan the QR. See everything.",
         "callout": {"box": [0.03, 0.235, 0.955, 0.35]},
         "narration": "WorkHive gives every machine an Asset Brain. Scan its QR and see everything."},
        {"kind": "tour", "scene": "montage", "caption": "Logbook. PM. Parts. Risk.",
         "narration": "One timeline: every logbook entry, preventive PM, and spare part. A risk score alerts you early."},
        {"kind": "payoff", "scene": "stakes", "caption": "Ask Hezekiah or Zaniah.",
         "narration": "Ask Hezekiah or Zaniah anything. They answer from that machine's own history."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Give every machine a memory. Start free at workhiveph.com.",
         "learn": "/learn/asset-brain-360-one-machine-history-philippine-plant/", "tool": "/asset-hub.html"},
    ]
    return spec


def asset_brain_spec_short() -> dict:
    """A <=30s Reels/Shorts cut of the Asset Brain 360 spot: hook -> product ->
    tool-named tour -> CTA (~48 words). Same grounding + gate-clean copy."""
    spec = _asset_brain_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Every machine has a memory.",
         "narration": "Every machine has a memory. Can you read all of it?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_assethub_clean",
         "label": "Asset Brain 360", "caption": "Scan the QR. See its history.",
         "callout": {"box": [0.03, 0.235, 0.955, 0.35]},
         "narration": "WorkHive gives every Philippine plant machine an Asset Brain. Scan its QR, see its whole history."},
        {"kind": "tour", "scene": "montage", "caption": "Logbook. PM. Parts. Risk.",
         "narration": "One timeline: every logbook entry, preventive PM, spare part. A risk score alerts you early."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Give every machine a memory. Start free at workhiveph.com.",
         "learn": "/learn/asset-brain-360-one-machine-history-philippine-plant/", "tool": "/asset-hub.html"},
    ]
    return spec


def asset_brain_spec_ad() -> dict:
    """A ~15s paid-AD cut: one stake -> one product line naming >=3 real tools ->
    CTA (~32 words). Clears the same overview gate as the longer cuts."""
    spec = _asset_brain_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Every machine has a memory.",
         "narration": "Every machine has a memory. Can you read all of it?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_assethub_clean",
         "label": "Asset Brain 360", "caption": "Scan the QR. See its history.",
         "callout": {"box": [0.03, 0.235, 0.955, 0.35]},
         "narration": "WorkHive gives every Philippine plant machine an Asset Brain. Logbook, preventive PM, spare parts, risk."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Scan it, see everything, start free at workhiveph.com.",
         "learn": "/learn/asset-brain-360-one-machine-history-philippine-plant/", "tool": "/asset-hub.html"},
    ]
    return spec


# ── Wave-4 feature spots (2026-07-03): Shift Brain + Alert Hub ────────────────
# Both are "your AI works for you / save time" — the companions (Hezekiah/Zaniah)
# do the planning/watching. kind='overview' so they clear the overview gate.

def _shift_brain_meta() -> dict:
    spec = _overview_meta()
    spec["concept"] = "WorkHive Shift Brain"
    spec["subtitle"] = "Shift Brain"
    spec["endTagline"] = "Your shift, already planned."
    return spec


def shift_brain_spec() -> dict:
    """Shift Brain feature spot (autonomous shift planning) — the AI plans the shift."""
    spec = _shift_brain_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "What do we fix first?",
         "narration": "Every shift starts the same way. What do we fix first?"},
        {"kind": "background", "scene": "stakes", "caption": "Too much to plan by 6 AM.",
         "narration": "Risk, PMs, open work, and parts. Too much to plan before the shift."},
        {"kind": "reveal", "scene": "product", "screen": "wh_shiftbrain_clean",
         "label": "Shift Brain", "caption": "Your shift plans itself.",
         "narration": "With WorkHive, your shift plans itself, for Filipino plants."},
        {"kind": "tour", "scene": "montage", "caption": "Risk. PMs. Parts.",
         "narration": "It ranks failure risk, lists preventive PMs, stages spare parts, and clears the alerts."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah write the brief.",
         "narration": "Hezekiah and Zaniah write the brief. You approve it with one tap."},
        {"kind": "payoff", "scene": "stakes", "caption": "Fresh plan, every shift.",
         "narration": "A fresh plan at six, at two, and at ten. Skip the morning scramble."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Let your AI plan the shift. Start free at workhiveph.com.",
         "learn": "/learn/autonomous-shift-planning-philippine-plants/", "tool": "/shift-brain.html"},
    ]
    return spec


def shift_brain_spec_short() -> dict:
    spec = _shift_brain_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "What do we fix first?",
         "narration": "Every shift starts the same way. What do we fix first?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_shiftbrain_clean",
         "label": "Shift Brain", "caption": "Your shift plans itself.",
         "narration": "With WorkHive, your Filipino shift plans itself. It ranks risk, lists preventive PMs, stages spare parts, clears alerts."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah brief you.",
         "narration": "Hezekiah and Zaniah write the brief. You approve with one tap."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Let your AI plan the shift. Start free at workhiveph.com.",
         "learn": "/learn/autonomous-shift-planning-philippine-plants/", "tool": "/shift-brain.html"},
    ]
    return spec


def shift_brain_spec_ad() -> dict:
    spec = _shift_brain_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "What do we fix first?",
         "narration": "Every shift, what do we fix first?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_shiftbrain_clean",
         "label": "Shift Brain", "caption": "Your shift plans itself.",
         "narration": "With WorkHive, your Filipino shift plans itself. Preventive PMs, spare parts, alerts, all ranked."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Hezekiah and Zaniah brief your crew. Start free at workhiveph.com.",
         "learn": "/learn/autonomous-shift-planning-philippine-plants/", "tool": "/shift-brain.html"},
    ]
    return spec


def _alert_hub_meta() -> dict:
    spec = _overview_meta()
    spec["concept"] = "WorkHive Alert Hub"
    spec["subtitle"] = "Alert Hub"
    spec["endTagline"] = "One inbox for the whole plant."
    return spec


def alert_hub_spec() -> dict:
    """Alert Hub feature spot (unified inbox + 6 AM brief) — your AI watches the plant."""
    spec = _alert_hub_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Which alert actually matters?",
         "narration": "Alerts everywhere. Which one actually matters?"},
        {"kind": "background", "scene": "stakes", "caption": "Scattered across every screen.",
         "narration": "Risk, PMs, stock, patterns. Scattered across every screen."},
        {"kind": "reveal", "scene": "product", "screen": "wh_alerthub_clean",
         "label": "Alert Hub", "caption": "Every alert, one inbox.",
         "narration": "WorkHive puts every plant alert in one inbox, for Filipino supervisors."},
        {"kind": "tour", "scene": "montage", "caption": "Risk. PMs. Stock.",
         "narration": "Failure risk, preventive PMs, and low spare parts, one clear alert list."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah brief you.",
         "narration": "Every morning, Hezekiah and Zaniah brief you first."},
        {"kind": "payoff", "scene": "stakes", "caption": "One list. One tap.",
         "narration": "The six AM brief. One prioritized list, one tap. Your AI watches the plant for you."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Let your AI watch the plant. Start free at workhiveph.com.",
         "learn": "/learn/plant-alert-inbox-amc-daily-brief/", "tool": "/alert-hub.html"},
    ]
    return spec


def alert_hub_spec_short() -> dict:
    spec = _alert_hub_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Which alert actually matters?",
         "narration": "Alerts everywhere. Which one actually matters?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_alerthub_clean",
         "label": "Alert Hub", "caption": "Every alert, one inbox.",
         "narration": "WorkHive puts every plant alert in one inbox for Filipino supervisors. Risk, preventive PMs, spare parts, one alert list."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah brief you.",
         "narration": "Every morning, Hezekiah and Zaniah brief you first."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Let your AI watch the plant. Start free at workhiveph.com.",
         "learn": "/learn/plant-alert-inbox-amc-daily-brief/", "tool": "/alert-hub.html"},
    ]
    return spec


def alert_hub_spec_ad() -> dict:
    spec = _alert_hub_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Which alert actually matters?",
         "narration": "Alerts everywhere. Which one actually matters?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_alerthub_clean",
         "label": "Alert Hub", "caption": "Every alert, one inbox.",
         "narration": "WorkHive puts every Filipino plant alert in one inbox. Risk, preventive PMs, spare parts, one list."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Hezekiah and Zaniah brief you at six AM. Start free at workhiveph.com.",
         "learn": "/learn/plant-alert-inbox-amc-daily-brief/", "tool": "/alert-hub.html"},
    ]
    return spec


# ── Wave-5 feature spots (2026-07-03): the interconnected Analytics hub ───────

def _analytics_engine_meta() -> dict:
    spec = _overview_meta()
    spec["concept"] = "WorkHive Analytics"
    spec["subtitle"] = "Analytics Engine"
    spec["endTagline"] = "Entries in, decisions out."
    return spec


def analytics_engine_spec() -> dict:
    """Analytics Engine feature spot — your logbook becomes connected intelligence."""
    spec = _analytics_engine_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "What is your logbook telling you?",
         "narration": "Your logbook is full. What is it telling you?"},
        {"kind": "background", "scene": "stakes", "caption": "The patterns stay hidden.",
         "narration": "The entries pile up, but the patterns stay hidden."},
        {"kind": "reveal", "scene": "product", "screen": "wh_analytics_clean",
         "label": "Analytics Engine", "caption": "Your logbook becomes intelligence.",
         "narration": "With WorkHive, your logbook becomes live OEE and MTBF, for Filipino plants."},
        {"kind": "tour", "scene": "montage", "caption": "Connected, not scattered.",
         "narration": "Log it once, and see preventive PM compliance, spare parts, and OEE, all connected."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah read the trend.",
         "narration": "Hezekiah and Zaniah read the trend and tell you what to fix."},
        {"kind": "payoff", "scene": "stakes", "caption": "What happened, to what to do next.",
         "narration": "From what happened, to why, to what to do next."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Turn entries into decisions. Start free at workhiveph.com.",
         "learn": "/learn/four-phases-maintenance-analytics-philippine-plants/", "tool": "/analytics.html"},
    ]
    return spec


def analytics_engine_spec_short() -> dict:
    spec = _analytics_engine_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "What is your logbook telling you?",
         "narration": "Your logbook is full. What is it telling you?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_analytics_clean",
         "label": "Analytics Engine", "caption": "Your logbook becomes intelligence.",
         "narration": "With WorkHive, your Filipino logbook becomes live OEE, MTBF, preventive PM compliance, and spare-parts insight."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah tell you what to fix.",
         "narration": "Hezekiah and Zaniah tell you what to fix next."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Turn entries into decisions. Start free at workhiveph.com.",
         "learn": "/learn/four-phases-maintenance-analytics-philippine-plants/", "tool": "/analytics.html"},
    ]
    return spec


def analytics_engine_spec_ad() -> dict:
    spec = _analytics_engine_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "What is your logbook telling you?",
         "narration": "Your logbook is full. What is it telling you?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_analytics_clean",
         "label": "Analytics Engine", "caption": "Your logbook becomes intelligence.",
         "narration": "With WorkHive, your Filipino logbook becomes live OEE, MTBF, and preventive PM analytics. Spare parts too."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Turn entries into decisions. Start free at workhiveph.com.",
         "learn": "/learn/four-phases-maintenance-analytics-philippine-plants/", "tool": "/analytics.html"},
    ]
    return spec


def _analytics_report_meta() -> dict:
    spec = _overview_meta()
    spec["concept"] = "WorkHive Analytics Report"
    spec["subtitle"] = "Analytics Report"
    spec["endTagline"] = "The report that writes itself."
    return spec


def analytics_report_spec() -> dict:
    """Analytics Report feature spot — the signed, audit-ready deliverable."""
    spec = _analytics_report_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Management wants a report.",
         "narration": "Management wants a report. By Monday."},
        {"kind": "background", "scene": "stakes", "caption": "A weekend in a spreadsheet?",
         "narration": "You could lose the weekend to a spreadsheet."},
        {"kind": "reveal", "scene": "product", "screen": "wh_analyticsreport_clean",
         "label": "Analytics Report", "caption": "The report writes itself.",
         "narration": "With WorkHive, the report writes itself, for Filipino plants."},
        {"kind": "tour", "scene": "montage", "caption": "From entries to tiles.",
         "narration": "Your logbook becomes OEE, MTBF, preventive PM, and spare-parts tiles."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah draft the plan.",
         "narration": "Hezekiah and Zaniah draft the action plan. You sign it."},
        {"kind": "payoff", "scene": "stakes", "caption": "One click. One signed report.",
         "narration": "One click, one signed report, ready for ISO and DOLE."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Hand up a report that reads itself. Start free at workhiveph.com.",
         "learn": "/learn/print-ready-maintenance-analytics-report/", "tool": "/analytics-report.html"},
    ]
    return spec


def analytics_report_spec_short() -> dict:
    spec = _analytics_report_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Management wants a report.",
         "narration": "Management wants a report. By Monday."},
        {"kind": "reveal", "scene": "product", "screen": "wh_analyticsreport_clean",
         "label": "Analytics Report", "caption": "The report writes itself.",
         "narration": "With WorkHive, your Filipino logbook becomes a signed report: OEE, MTBF, preventive PM, and spare-parts tiles, one click."},
        {"kind": "build", "scene": "stakes", "caption": "Hezekiah and Zaniah draft the plan.",
         "narration": "Hezekiah and Zaniah draft the action plan."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Hand up a report that reads itself. Start free at workhiveph.com.",
         "learn": "/learn/print-ready-maintenance-analytics-report/", "tool": "/analytics-report.html"},
    ]
    return spec


def analytics_report_spec_ad() -> dict:
    spec = _analytics_report_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Management wants a report.",
         "narration": "Management wants a report. By Monday."},
        {"kind": "reveal", "scene": "product", "screen": "wh_analyticsreport_clean",
         "label": "Analytics Report", "caption": "The report writes itself.",
         "narration": "With WorkHive, your Filipino report writes itself. OEE, MTBF, preventive PM, spare parts, signed."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Hezekiah and Zaniah draft the plan. Start free at workhiveph.com.",
         "learn": "/learn/print-ready-maintenance-analytics-report/", "tool": "/analytics-report.html"},
    ]
    return spec


def _engdesign_meta() -> dict:
    """Shared meta for the Engineering Calculators feature spot. kind='overview' so
    it clears the overview gate; features stay the real WORKHIVE_TOOLS."""
    spec = _overview_meta()
    spec["concept"] = "WorkHive Engineering Calculators"
    spec["subtitle"] = "Engineering Design Calculators"
    spec["endTagline"] = "Design with confidence."
    return spec


def engdesign_spec() -> dict:
    """Feature spot for Engineering Design Calculators (engineering-design.html) +
    the /learn/ article free-engineering-calculators-philippine-plants. Grounded in
    the real page: 53 calculations across 6 disciplines (HVAC, Mechanical, Electrical,
    Plumbing, Fire Protection, Machine Design), each anchored to a named standard (PEC
    2017, ASHRAE, PSME, NFPA, ISO), a Calculation History that logs every run, and an
    in-app Guide. Screen = wh_engdesign_clean (the topic-aligned capture). ~90 words."""
    spec = _engdesign_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Sizing it on a guess?",
         "narration": "Sizing a pump or a breaker. Are you sure the number is right?"},
        {"kind": "background", "scene": "stakes", "caption": "Formulas scattered everywhere.",
         "narration": "The formulas live in old textbooks, random PDFs, and borrowed spreadsheets."},
        {"kind": "rationale", "scene": "stakes", "caption": "Every number needs a standard.",
         "narration": "Every design number should trace to a real code, not a guess."},
        {"kind": "reveal", "scene": "product", "screen": "wh_engdesign_clean",
         "label": "Engineering Calculators", "caption": "53 calculators. Six disciplines.",
         "callout": {"box": [0.03, 0.235, 0.955, 0.35]},
         "narration": "WorkHive gives you fifty three engineering calculators, across six disciplines."},
        {"kind": "tour", "scene": "montage", "caption": "HVAC to Fire. Cited standards.",
         "narration": "HVAC, mechanical, electrical, plumbing, fire, and machine design. Each answer cites its standard, PEC, ASHRAE, or NFPA."},
        {"kind": "payoff", "scene": "stakes", "caption": "Every run logged to history.",
         "narration": "Every calculation is logged to your history, so you can defend it later."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Design with confidence, free, for Philippine plants. Start at workhiveph.com.",
         "learn": "/learn/free-engineering-calculators-philippine-plants/", "tool": "/engineering-design.html"},
    ]
    return spec


def engdesign_spec_short() -> dict:
    """A <=30s Reels/Shorts cut of the Engineering Calculators spot."""
    spec = _engdesign_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Sizing it on a guess?",
         "narration": "Sizing a pump or a breaker. Are you sure the number is right?"},
        {"kind": "reveal", "scene": "product", "screen": "wh_engdesign_clean",
         "label": "Engineering Calculators", "caption": "53 calculators. Cited standards.",
         "narration": "WorkHive gives you fifty three engineering calculators. Each answer cites its standard, PEC, ASHRAE, or NFPA, and is logged to your history."},
        {"kind": "payoff", "scene": "stakes", "caption": "Six disciplines.",
         "narration": "Six disciplines, from HVAC to fire protection."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Design with confidence, free, for Philippine plants. Start at workhiveph.com.",
         "learn": "/learn/free-engineering-calculators-philippine-plants/", "tool": "/engineering-design.html"},
    ]
    return spec


def engdesign_spec_ad() -> dict:
    """A ~15s paid-AD cut of the Engineering Calculators spot."""
    spec = _engdesign_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Sure the number is right?",
         "narration": "Sizing it on a guess? Be sure."},
        {"kind": "reveal", "scene": "product", "screen": "wh_engdesign_clean",
         "label": "Engineering Calculators", "caption": "53 calculators. Cited standards.",
         "narration": "WorkHive gives you fifty three engineering calculators, six disciplines, each answer citing its standard and logged to history."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Design with confidence, free, for Philippine plants. Start at workhiveph.com.",
         "learn": "/learn/free-engineering-calculators-philippine-plants/", "tool": "/engineering-design.html"},
    ]
    return spec


def _resume_meta() -> dict:
    """Shared meta for the Resume / CV Builder feature spot. kind='overview' so it
    clears the overview gate; features stay the real WORKHIVE_TOOLS."""
    spec = _overview_meta()
    spec["concept"] = "WorkHive Resume Builder"
    spec["subtitle"] = "Resume / CV Builder"
    spec["endTagline"] = "Your work, on paper."
    return spec


def resume_spec() -> dict:
    """Feature spot for the Resume / CV Builder (resume.html) + the /learn/ articles
    resume-builder-for-filipino-industrial-workers and ofw-engineer-portable-portfolio.
    Grounded in the real page: Auto-fill from your WorkHive data (your logbook history
    + earned skill badges), ATS-plain templates, Preview and Export to PDF or Word,
    save multiple resumes, an AI polish pass. Screen = wh_resume_clean (the topic-
    aligned capture). Value-first, PH/OFW anchor. ~90 words, ~55s."""
    spec = _resume_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Years on the floor. Blank page.",
         "narration": "Years keeping the plant alive. Your resume is still a blank page."},
        {"kind": "background", "scene": "stakes", "caption": "Your best work is buried.",
         "narration": "Your best work is buried in logbooks and shift notes."},
        {"kind": "rationale", "scene": "stakes", "caption": "That history is your resume.",
         "narration": "That history is your resume. You just have to pull it out."},
        {"kind": "reveal", "scene": "product", "screen": "wh_resume_clean",
         "label": "Resume / CV Builder", "caption": "Auto-fill from your work.",
         "callout": {"box": [0.03, 0.42, 0.955, 0.56]},
         "narration": "With WorkHive, your resume builds itself from the work you already logged."},
        {"kind": "tour", "scene": "montage", "caption": "Logbook and skill badges.",
         "narration": "Auto-fill pulls your logbook history and your earned skill badges. Then export a clean ATS resume."},
        {"kind": "build", "scene": "stakes", "caption": "The assistant polishes it.",
         "narration": "A WorkHive assistant polishes every line into strong, plain English."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Free for Filipino workers and OFW engineers. Start at workhiveph.com.",
         "learn": "/learn/resume-builder-for-filipino-industrial-workers/", "tool": "/resume.html"},
    ]
    return spec


def resume_spec_short() -> dict:
    """A <=30s Reels/Shorts cut of the Resume / CV Builder spot."""
    spec = _resume_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Years on the floor. Blank page.",
         "narration": "Years keeping the plant alive. Your resume is still blank."},
        {"kind": "reveal", "scene": "product", "screen": "wh_resume_clean",
         "label": "Resume / CV Builder", "caption": "Auto-fill from your work.",
         "narration": "With WorkHive, your resume auto-fills from your logbook history and your skill badges. Then export a clean ATS resume."},
        {"kind": "build", "scene": "stakes", "caption": "The assistant polishes it.",
         "narration": "A WorkHive assistant polishes every line."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Free for Filipino workers and OFW engineers. Start at workhiveph.com.",
         "learn": "/learn/resume-builder-for-filipino-industrial-workers/", "tool": "/resume.html"},
    ]
    return spec


def resume_spec_ad() -> dict:
    """A ~15s paid-AD cut of the Resume / CV Builder spot."""
    spec = _resume_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Blank page?",
         "narration": "Years on the floor. Your resume is still blank."},
        {"kind": "reveal", "scene": "product", "screen": "wh_resume_clean",
         "label": "Resume / CV Builder", "caption": "Auto-fill from your work.",
         "narration": "With WorkHive, your resume auto-fills from your logbook and skill badges, and an assistant polishes every line."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Free for Filipino workers and OFW engineers. Start at workhiveph.com.",
         "learn": "/learn/resume-builder-for-filipino-industrial-workers/", "tool": "/resume.html"},
    ]
    return spec


def _companion_meta() -> dict:
    """Shared meta for the AI Companion capabilities spot. kind='overview' so it
    clears the overview gate; features stay the real WORKHIVE_TOOLS."""
    spec = _overview_meta()
    spec["concept"] = "WorkHive AI Companions"
    spec["subtitle"] = "Hezekiah and Zaniah"
    spec["endTagline"] = "Two experts, in your pocket."
    return spec


def companion_spec() -> dict:
    """Feature spot for the AI Companions (Hezekiah + Zaniah) and the /learn/ article
    workhive-ai-companion-complete-capabilities. Ian's brief: the companions have so
    much capability that users under-use it, and the copy must be SIMPLE, PRACTICAL,
    and JARGON-FREE for a worker watching + listening. Every capability is a plain
    benefit (no RAG/ASR/model words): answers from your own records and shows where it
    found them, never invents a number, talks in your language + reads back out loud,
    fills a work order by voice, reads a photo, pulls one machine's whole history,
    plans your shift, keeps you safe to PH rules. Grounded in .tmp/companion_research/
    companion.json. Screen = wh_assistant_clean (fresh capability-chip capture). ~95 words."""
    spec = _companion_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Two experts. One pocket.",
         "narration": "You have two AI experts in your pocket. Here is how they help you through a shift."},
        {"kind": "reveal", "scene": "product", "screen": "wh_assistant_clean",
         "label": "Ask anything", "caption": "Hezekiah fixes. Zaniah plans.",
         "callout": {"box": [0.06, 0.285, 0.92, 0.48]},
         "narration": "WorkHive gives you Hezekiah for the hands-on fix and Zaniah for the plan. Ask either one in plain words."},
        {"kind": "tour", "scene": "montage", "caption": "A machine goes down.",
         "narration": "A machine goes down. Ask what fixed it last time, and it pulls the answer straight from your own logbook and shows you where it found it."},
        {"kind": "build", "scene": "stakes", "caption": "Not sure how? Just ask.",
         "narration": "Not sure how to do the job? Ask for the steps, and it walks you through them in plain words."},
        {"kind": "payoff", "scene": "stakes", "caption": "What should I fix first?",
         "narration": "Too much on your plate? Ask what to fix first, and it ranks your alerts, your overdue preventive maintenance, and your low spare parts."},
        {"kind": "rationale", "scene": "stakes", "caption": "It will not make up a number.",
         "narration": "And it never makes up a number. If it does not know, it says so and points you to the right page."},
        {"kind": "build", "scene": "stakes", "caption": "Your own data. Free.",
         "narration": "Two experts, working from your own plant data, built for Filipino teams, and free."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Meet Hezekiah and Zaniah at workhiveph.com.",
         "learn": "/learn/workhive-ai-companion-complete-capabilities/", "tool": "/assistant.html"},
    ]
    return spec


def companion_spec_short() -> dict:
    """A <=30s Reels/Shorts cut of the AI Companion spot. Plain + practical."""
    spec = _companion_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Two experts. One pocket.",
         "narration": "You have two AI experts in your pocket. Here is how they help."},
        {"kind": "reveal", "scene": "product", "screen": "wh_assistant_clean",
         "label": "Ask anything", "caption": "A machine goes down? Ask.",
         "narration": "WorkHive gives you Hezekiah for the fix and Zaniah for the plan. A machine goes down? Ask what fixed it last time, and it answers from your own logbook. Overwhelmed? Ask what to fix first, and it ranks your alerts, preventive maintenance, and spare parts."},
        {"kind": "build", "scene": "stakes", "caption": "It will not make up a number.",
         "narration": "And it never makes up a number."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Meet Hezekiah and Zaniah, free for Filipino teams, at workhiveph.com.",
         "learn": "/learn/workhive-ai-companion-complete-capabilities/", "tool": "/assistant.html"},
    ]
    return spec


def companion_spec_ad() -> dict:
    """A ~15s paid-AD cut of the AI Companion spot. Plain + practical."""
    spec = _companion_meta()
    spec["beats"] = [
        {"kind": "hook", "scene": "stakes", "caption": "Two experts. One pocket.",
         "narration": "Two AI experts, in your pocket."},
        {"kind": "reveal", "scene": "product", "screen": "wh_assistant_clean",
         "label": "Ask anything", "caption": "Ask. Get a real answer.",
         "narration": "WorkHive gives you Hezekiah for the fix and Zaniah for the plan. Ask what fixed a machine last time, or what to fix first, and it answers from your own logbook, alerts, preventive maintenance, and spare parts. It never makes up a number."},
        {"kind": "cta", "scene": "end", "caption": "Start free: workhiveph.com",
         "narration": "Free for Filipino teams. Start at workhiveph.com.",
         "learn": "/learn/workhive-ai-companion-complete-capabilities/", "tool": "/assistant.html"},
    ]
    return spec


def _demo(aspect: str = "9:16", fps: int = 24, kind: str = "overview") -> int:
    spec = overview_spec() if kind == "overview" else demo_spec()
    stem = "workhive_overview" if kind == "overview" else "workhive_explains_oee"
    sp = Path(f".tmp/explainer_specs/{stem}.json")
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    out = Path(f".tmp/explainer_out/{stem}.mp4")
    build_from_spec(sp, out, aspect=aspect, fps=fps)
    print(f"\nDEMO video: {out}")
    return 0


# ── self-test (fast: no network, no ffmpeg — proves the render primitives) ────

def self_test() -> int:
    print("explainer_render.py --self-test")
    print("=" * 52)
    fails = 0

    def ck(cond, label):
        nonlocal fails
        print(("  PASS  " if cond else "  FAIL  ") + label)
        if not cond:
            fails += 1

    W, H = 400, 711  # small 9:16 canvas for speed
    spec = demo_spec()
    bg = background(W, H)
    ck(bg.size == (W, H) and bg.mode == "RGB", "background renders at canvas size")

    tc = title_card(spec, W, H)
    ck(tc.size == (W, H), "title card renders (auto-fit, no overflow crash)")

    # auto-fit must shrink a realistic line to fit (the POC's one overflow bug)
    d = ImageDraw.Draw(tc)
    realistic = "Overall Equipment Effectiveness"
    f1 = fit_font(d, realistic, "black", W * 0.9, start=int(W * 0.28), min_size=16)
    ck(_text_w(d, realistic, f1) <= W * 0.9 + 1 and f1.size < int(W * 0.28),
       "fit_font shrinks a realistic subtitle to fit within max width")
    # an impossible line must degrade gracefully to the floor, never crash/overflow-loop
    impossible = "Overall Equipment Effectiveness Is A Very Long Subtitle Indeed"
    f2 = fit_font(d, impossible, "black", W * 0.9, start=int(W * 0.28), min_size=16)
    ck(_text_w(d, impossible, f2) <= W * 0.9 + 1 or f2.size == 16,
       "fit_font degrades to the min-size floor when nothing fits")

    ec = end_card(spec, W, H)
    ck(ec.size == (W, H), "end card renders")

    beat = spec["beats"][3]  # the worked-example (oee_bars) beat
    bs = beat_static(beat, spec, W, H)
    ck(bs.size == (W, H), "worked-example beat + oee_bars viz renders")

    # overview template: title card feature grid + feature_grid beat
    ov = overview_spec()
    ot = title_card(ov, W, H)
    ck(ot.size == (W, H), "overview title card renders (feature grid, no ISO chip)")
    ob = beat_static(ov["beats"][2], ov, W, H)  # the feature_grid tour beat
    ck(ob.size == (W, H), "overview tour beat + feature_grid viz renders")

    words = [{"text": t, "start_ms": i * 200, "end_ms": i * 200 + 180}
             for i, t in enumerate("OEE is three factors multiplied together.".split())]
    chunks = _chunk_words(words)
    ck(len(chunks) >= 1 and all(len(c) <= 6 for c in chunks), "word chunking <= 6 words/chunk")
    mid = draw_caption(bs, chunks, 500.0, W, H)
    ck(mid.size == (W, H) and mid.mode == "RGB", "kinetic caption composits onto a scene")

    segs, total = _build_timeline(spec, {"beats": [
        {"beat_index": i, "order": i, "kind": b["kind"], "narration": b.get("narration", ""),
         "mp3": "x", "duration_s": 3.0, "words": words}
        for i, b in enumerate(spec["beats"])]})
    ck(len(segs) == len(spec["beats"]) + 1, "timeline appends the end card scene")
    ck(abs(total - (len(spec["beats"]) * 3.0 + END_HOLD_S)) < 0.01, "timeline total = sum(beats)+end hold")

    print("=" * 52)
    print("  self-test PASS" if fails == 0 else f"  self-test FAIL — {fails} check(s)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="WorkHive Explains educational video renderer.")
    ap.add_argument("--demo", action="store_true", help="render a built-in verified spec end to end")
    ap.add_argument("--kind", default="overview", choices=["overview", "oee"],
                    help="which built-in demo spec to render (default: the WorkHive overview)")
    ap.add_argument("--self-test", action="store_true", help="fast render-primitive checks (no network/ffmpeg)")
    ap.add_argument("--aspect", default="9:16", choices=list(ASPECTS.keys()))
    ap.add_argument("--fps", type=int, default=24)
    sub = ap.add_subparsers(dest="cmd")
    pb = sub.add_parser("build"); pb.add_argument("--spec", required=True); pb.add_argument("--out", required=True)
    pb.add_argument("--aspect", default="9:16", choices=list(ASPECTS.keys())); pb.add_argument("--fps", type=int, default=24)
    pr = sub.add_parser("render"); pr.add_argument("--spec", required=True); pr.add_argument("--audio", required=True)
    pr.add_argument("--out", required=True); pr.add_argument("--aspect", default="9:16", choices=list(ASPECTS.keys()))
    pr.add_argument("--fps", type=int, default=24)
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.demo:
        return _demo(aspect=args.aspect, fps=args.fps, kind=args.kind)
    if args.cmd == "build":
        build_from_spec(args.spec, args.out, aspect=args.aspect, fps=args.fps)
        return 0
    if args.cmd == "render":
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        render_from_spec(spec, args.audio, args.out, aspect=args.aspect, fps=args.fps)
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
