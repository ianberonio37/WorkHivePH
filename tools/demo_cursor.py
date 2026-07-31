#!/usr/bin/env python3
"""
demo_cursor.py - a VISIBLE, gliding cursor for product-demo recordings.
=======================================================================
Studying Ian's eTax PH reference (`.tmp/video_ref/Video Marketing_study/`)
isolated why its 75 seconds of product walkthrough hold attention with no
voiceover at all: **the cursor is the narrator.** You watch a hand move to a
control, hesitate, click, and the UI answers. That is the story.

Our Playwright recordings had no cursor whatsoever. Playwright's `record_video`
captures the page, not the OS pointer, so every recording we ever made showed
UI mutating by itself - closer to a screenshot slideshow than a demo.

This module supplies the two missing halves:

  1. CURSOR_JS      - an injected pointer that tracks real mouse events, with a
                      click pulse and a press state. Injected via
                      add_init_script so it survives navigation.
  2. glide()/click_at()/type_into() - motion helpers. Playwright's native click
                      teleports the pointer; a teleporting cursor reads as a
                      glitch. These interpolate along an ease-in-out curve at
                      ~60fps so the movement looks hand-driven.

Usage inside an existing Playwright script:

    from demo_cursor import install_cursor, click_at, type_into, glide

    context.add_init_script(CURSOR_JS)      # or: install_cursor(context)
    ...
    click_at(page, "#save-btn")             # glides, pulses, then clicks
    type_into(page, "#title", "Bearing replaced", per_char_ms=45)

Self-test:
    python tools/demo_cursor.py --self-test
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

# The pointer is drawn in the page, so it must survive re-render and sit above
# every app layer. z-index is deliberately absurd; WorkHive modals reach ~10000.
CURSOR_JS = r"""
(() => {
  // NB: everything below is IDEMPOTENT and self-healing rather than
  // install-once. A one-shot guard looks correct and fails in practice: any
  // full-document replacement (set_content, an SPA rerender, a doc rewrite)
  // discards the pointer AND its listeners while the window-level "installed"
  // flag survives, so the guard then blocks the re-mount and the cursor is gone
  // for the rest of the recording. Cheap periodic re-assertion is what makes it
  // survive a real multi-page journey.
  const ensure = () => {
    if (!document.body) return;

    if (!document.getElementById('__wh_cursor_style')) {
    const style = document.createElement('style');
    style.id = '__wh_cursor_style';
    style.textContent = `
      #__wh_cursor {
        position: fixed; top: 0; left: 0; width: 22px; height: 22px;
        margin: -2px 0 0 -2px; pointer-events: none; z-index: 2147483647;
        transition: transform 90ms ease-out; will-change: transform;
      }
      #__wh_cursor svg { display:block; filter: drop-shadow(0 2px 3px rgba(0,0,0,.42)); }
      #__wh_cursor.__pressed { transform: scale(.82); }
      #__wh_ripple {
        position: fixed; pointer-events: none; z-index: 2147483646;
        width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%;
        background: rgba(247,162,27,.55); opacity: 0; will-change: transform, opacity;
      }
      @keyframes __wh_pulse {
        0%   { transform: scale(.4); opacity: .85; }
        100% { transform: scale(4.2); opacity: 0; }
      }
      #__wh_ripple.__go { animation: __wh_pulse 520ms ease-out forwards; }
    `;
    (document.head || document.documentElement).appendChild(style);
    }

    // A real arrow, not a dot - viewers read an arrow as "someone is doing this".
    if (!document.getElementById('__wh_cursor')) {
      const cur = document.createElement('div');
      cur.id = '__wh_cursor';
      cur.innerHTML =
        '<svg width="22" height="22" viewBox="0 0 22 22">' +
        '<path d="M2 1 L2 17 L6.2 13.1 L8.9 19.2 L11.7 18 L9 12 L14.6 12 Z" ' +
        'fill="#fff" stroke="#16202f" stroke-width="1.4" stroke-linejoin="round"/></svg>';
      document.body.appendChild(cur);
    }
    if (!document.getElementById('__wh_ripple')) {
      const rip = document.createElement('div');
      rip.id = '__wh_ripple';
      document.body.appendChild(rip);
    }

    // Position lives on window so it survives a body/document swap - otherwise
    // the pointer teleports back to centre every time the page rerenders.
    if (typeof window.__whX !== 'number') {
      window.__whX = window.innerWidth / 2;
      window.__whY = window.innerHeight / 2;
    }
    const draw = () => {
      const c = document.getElementById('__wh_cursor');
      if (c) c.style.transform = `translate(${window.__whX}px, ${window.__whY}px)`;
    };
    draw();

    // Listeners are attached to the DOCUMENT, so a document swap loses them too.
    // Track the attach on the document itself, not on window.
    if (!document.__whListeners) {
      document.__whListeners = true;
      document.addEventListener('mousemove', (e) => {
        window.__whX = e.clientX; window.__whY = e.clientY; draw();
      }, true);
      document.addEventListener('mousedown', () => {
        const c = document.getElementById('__wh_cursor');
        const rip = document.getElementById('__wh_ripple');
        if (c) c.classList.add('__pressed');
        if (rip) {
          rip.style.left = window.__whX + 'px';
          rip.style.top = window.__whY + 'px';
          rip.classList.remove('__go');
          void rip.offsetWidth;           // restart the animation
          rip.classList.add('__go');
        }
      }, true);
      document.addEventListener('mouseup', () => {
        const c = document.getElementById('__wh_cursor');
        if (c) c.classList.remove('__pressed');
      }, true);
    }

    // AUTHORITATIVE control path. The listeners above are a nice-to-have; they
    // proved unreliable across document swaps (a freshly-added listener received
    // mousemove while the injected one silently did not, leaving the pointer
    // parked at centre for a whole recording). Since Python already knows where
    // it is steering the mouse, it drives the drawn pointer explicitly and the
    // rendered position is correct BY CONSTRUCTION rather than by event luck.
    window.__whCursorAt = (nx, ny) => {
      window.__whX = nx; window.__whY = ny;
      const c = document.getElementById('__wh_cursor');
      if (c) c.style.transform = `translate(${nx}px, ${ny}px)`;
    };
    window.__whCursorPress = (down) => {
      const c = document.getElementById('__wh_cursor');
      if (!c) return;
      c.classList.toggle('__pressed', !!down);
      if (down) {
        const rip = document.getElementById('__wh_ripple');
        if (rip) {
          rip.style.left = window.__whX + 'px';
          rip.style.top = window.__whY + 'px';
          rip.classList.remove('__go');
          void rip.offsetWidth;
          rip.classList.add('__go');
        }
      }
    };
  };

  ensure();
  document.addEventListener('DOMContentLoaded', ensure);
  // Re-assert a few times a second. Covers every teardown path uniformly -
  // cheaper to reason about than enumerating which rerenders destroy what.
  if (!window.__whCursorTimer) window.__whCursorTimer = setInterval(ensure, 250);
})();
"""


def install_cursor(context) -> None:
    """Inject the pointer into every page this context opens, now and later."""
    context.add_init_script(CURSOR_JS)


def _ease(t: float) -> float:
    """ease-in-out cubic. Constant-velocity motion reads robotic; real hands
    accelerate away and decelerate into a target."""
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def glide(page, x: float, y: float, duration_ms: int = 520) -> None:
    """Move the pointer along a HUMAN path at ~60fps.

    Playwright's mouse.move(steps=N) is linear and as fast as the CPU allows -
    the pointer arrives in a couple of frames and the viewer sees a jump.
    Beyond wall-clock pacing, two things separate a hand from a robot (Ian,
    reviewing the first cut: "the cursor movement doesn't align how the users
    use it"):

      * ARC - a wrist pivots, so real moves bow sideways. The path gets a
        perpendicular sagitta proportional to distance (capped), side chosen
        deterministically from the endpoints so re-records are stable.
      * OVERSHOOT + SETTLE - on longer moves a hand passes the target by a few
        px and corrects. Straight-to-a-stop is the automation tell."""
    start = getattr(page, "_wh_cursor_pos", None)
    if start is None:
        vp = page.viewport_size or {"width": 1280, "height": 900}
        start = (vp["width"] / 2, vp["height"] / 2)
    dx, dy = x - start[0], y - start[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist < 1:
        page._wh_cursor_pos = (x, y)
        return
    # perpendicular unit vector; side flips deterministically with geometry
    nx, ny = -dy / dist, dx / dist
    side = 1 if (int(start[0] + x + start[1] + y) % 2 == 0) else -1
    bow = min(dist * 0.10, 42) * side
    # overshoot only on moves long enough for a wrist to build speed
    over = min(dist * 0.04, 9) if dist > 140 else 0

    def emit(px, py):
        page.mouse.move(px, py)
        # Drive the drawn pointer explicitly - see __whCursorAt. Failures are
        # swallowed because a missing helper (mid-navigation) must not abort a
        # recording; the real mouse still moved.
        try:
            page.evaluate("([x,y]) => window.__whCursorAt && window.__whCursorAt(x,y)",
                          [px, py])
        except Exception:
            pass

    tx = x + (dx / dist) * over
    ty = y + (dy / dist) * over
    frames = max(2, int(duration_ms / 16))
    for i in range(1, frames + 1):
        t = _ease(i / frames)
        px = start[0] + (tx - start[0]) * t + nx * bow * math.sin(math.pi * t)
        py = start[1] + (ty - start[1]) * t + ny * bow * math.sin(math.pi * t)
        emit(px, py)
        time.sleep(0.016)
    if over:
        for i in range(1, 6):                     # the correction: ~90ms settle
            t = i / 5
            emit(tx + (x - tx) * t, ty + (y - ty) * t)
            time.sleep(0.016)
    page._wh_cursor_pos = (x, y)


def park(page, frac_x: float = 0.93, frac_y: float = 0.58,
         duration_ms: int = 420) -> None:
    """Rest the pointer on right-side whitespace, near where a scroll wheel
    hand naturally sits.

    The first recordings parked the cursor DEAD CENTRE over the content during
    every reading dwell - on top of exactly what the viewer is trying to read.
    Real users move the pointer aside while reading and bring it back to act."""
    vp = page.viewport_size or {"width": 1280, "height": 900}
    glide(page, vp["width"] * frac_x, vp["height"] * frac_y, duration_ms)


def _center(page, selector: str, timeout: int = 15000):
    el = page.wait_for_selector(selector, state="visible", timeout=timeout)
    el.scroll_into_view_if_needed()
    page.wait_for_timeout(160)            # let smooth-scroll settle before aiming
    box = el.bounding_box()
    if not box:
        raise RuntimeError(f"no bounding box for {selector!r}")
    return el, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def click_at(page, selector: str, duration_ms: int = 520,
             settle_ms: int = 260, timeout: int = 15000):
    """Glide to an element, pause a beat, then click.

    The pause matters: a cursor that arrives and clicks in the same frame reads
    as automation. A ~260ms hesitation is what makes it read as a decision."""
    el, cx, cy = _center(page, selector, timeout)
    glide(page, cx, cy, duration_ms)
    page.wait_for_timeout(settle_ms)
    try:
        page.evaluate("() => window.__whCursorPress && window.__whCursorPress(true)")
    except Exception:
        pass
    page.mouse.click(cx, cy)
    try:
        page.evaluate("() => window.__whCursorPress && window.__whCursorPress(false)")
    except Exception:
        pass
    return el


def type_into(page, selector: str, text: str, per_char_ms: int = 45,
              duration_ms: int = 520, timeout: int = 15000):
    """Glide to a field, click it, then type at a human cadence.

    Instant value-setting is invisible on video - the viewer needs to watch the
    words appear to believe a person is doing it."""
    click_at(page, selector, duration_ms=duration_ms, timeout=timeout)
    page.wait_for_timeout(140)
    page.keyboard.type(text, delay=per_char_ms)


def dwell(page, ms: int) -> None:
    """Hold on a state so it can actually be read. The reference gives each
    product beat 15-20s; our old reel gave 2.87s per shot."""
    page.wait_for_timeout(ms)


# --------------------------------------------------------------------------

def self_test() -> int:
    """Drive a synthetic page and assert the cursor is REALLY on the recorded
    frames - not merely that the script was injected without error.

    An injected-but-invisible cursor is the exact failure this must catch: the
    whole point is that a viewer can see it, and 'no exception raised' does not
    establish that."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SELF-TEST SKIP: playwright not installed")
        return 0

    html = (
        "<!doctype html><meta charset=utf-8>"
        "<body style='margin:0;background:#fff;height:100vh'>"
        "<button id='b' style='position:absolute;left:600px;top:400px;"
        "width:180px;height:56px;font-size:18px'>Click me</button>"
        "<div id='out' style='position:absolute;left:40px;top:40px;font:16px sans-serif'></div>"
        "<script>document.getElementById('b').onclick=()=>"
        "document.getElementById('out').textContent='CLICKED';</script>"
    )
    fails = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        install_cursor(ctx)
        page = ctx.new_page()
        page.set_content(html)
        page.wait_for_timeout(300)

        if not page.query_selector("#__wh_cursor"):
            fails.append("cursor element was never injected")

        # It must be VISIBLE in pixels, not just present in the DOM.
        page.mouse.move(200, 200)
        page.wait_for_timeout(200)
        shot_before = page.screenshot()
        glide(page, 640, 300, duration_ms=200)
        page.wait_for_timeout(200)
        shot_after = page.screenshot()
        if shot_before == shot_after:
            fails.append("frames identical after moving the cursor - the pointer "
                         "is not being drawn into the captured pixels")

        click_at(page, "#b", duration_ms=200, settle_ms=80)
        page.wait_for_timeout(200)
        if (page.text_content("#out") or "").strip() != "CLICKED":
            fails.append("click_at glided but did not actually activate the target")

        box = page.query_selector("#__wh_cursor").bounding_box()
        tgt = page.query_selector("#b").bounding_box()
        if box:
            dx = abs(box["x"] - (tgt["x"] + tgt["width"] / 2))
            dy = abs(box["y"] - (tgt["y"] + tgt["height"] / 2))
            if dx > 24 or dy > 24:
                fails.append(f"cursor rendered at ({box['x']:.0f},{box['y']:.0f}) "
                             f"but clicked target centre "
                             f"({tgt['x']+tgt['width']/2:.0f},"
                             f"{tgt['y']+tgt['height']/2:.0f}) - drawn pointer "
                             f"does not match the real one")
        browser.close()

    if fails:
        print("SELF-TEST FAIL:")
        for f in fails:
            print("  - " + f)
        return 1
    print("SELF-TEST PASS - cursor injected, drawn into captured pixels, "
          "glides to and activates its target.")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    print(__doc__)
