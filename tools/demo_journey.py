#!/usr/bin/env python3
"""
demo_journey.py - record ONE end-to-end, cross-page WorkHive journey.
=====================================================================
Ian, 2026-07-30: "record the end to end journey of using a production feature
page and its cross-page connectivity so that you are like doing a demo for a
novice user."

That is deliberately NOT what `ui_recorder.py` does. Its DEMO_SEQUENCES each
open one page in isolation, so the footage can only ever say "here is a screen".
A novice does not need a screen; they need to see that what they typed HERE
shows up THERE. The connectivity IS the product story, and for WorkHive it is
literally the positioning - access your memory, build your own AI, save time.

So this records a single continuous session that carries one thread across five
pages:

  1. hive.html          the team's live board - where a novice lands
  2. logbook.html       CAPTURE: write down the fix that was just done
  3. asset-hub.html     CONNECT: that machine's history now carries it
  4. assistant.html     RECALL: ask your own AI - it answers from the logbook
  5. pm-scheduler.html  ACT: turn the lesson into a scheduled job

Pacing is copied from the measured reference (`.tmp/video_ref/Video Marketing_
study/`): 15-20s per product section and a visible, gliding cursor, because
that reference tells 75 seconds of story with no voiceover at all - the cursor
is the narrator. Our previous recordings had no cursor, so the UI appeared to
mutate by itself.

TWO GOTCHAS THIS ENCODES (both cost a debugging pass):
  * Feature pages gate on a real Supabase session AND an active hive. With the
    session alone, 5 of 6 pages bounce to index.html?signin=1.
  * The hive id must be injected via add_init_script, NOT left to survive in
    storage_state - the app's post-signin JS rewrites localStorage
    asynchronously and races the value away.

CLI:
    python tools/demo_journey.py                 # record it
    python tools/demo_journey.py --dry-run       # walk it, no video, print a report
    python tools/demo_journey.py --acts 1,2,4    # only some acts
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
for _p in (str(_HERE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ui_recorder as ur                                          # noqa: E402
from demo_cursor import (CURSOR_JS, click_at, dwell, glide,       # noqa: E402
                         park, type_into)

OUT_DIR = ROOT / ".tmp" / "demo_journey"
# 16:9 to match the reference format (it is a landing-page / YouTube asset).
VIEWPORT = {"width": 1280, "height": 720}

# Dwell budget, in ms. Named so the pacing is a decision, not scattered magic.
READ = 2600        # long enough to actually read a panel
BEAT = 1200        # a breath between actions
LAND = 3200        # after a page load: let the novice orient


def _log(msg: str) -> None:
    print(msg, flush=True)


def authed_context(browser, record_dir: Path | None):
    """An authed, hive-pinned context with the demo cursor installed.

    The hive goes in via add_init_script deliberately - see the module docstring;
    relying on storage_state loses it to a race and every page bounces."""
    username, display = ur._get_test_worker()
    hive = ur._get_worker_hive(display)
    if not hive:
        raise RuntimeError(f"no hive resolved for {display} - reseed before recording")

    # Sign-in is RACY, and the auth token alone does NOT predict success.
    # _authed_storage_state waits 400ms and captures, but the app keeps
    # populating localStorage after sign-in (wh_last_worker, wh_hives,
    # wh_hive_role). Capture before that lands and the state looks authenticated
    # while every feature page still bounces to index.html?signin=1. Measured
    # directly: complete states landed 4/4, partial ones bounced.
    #
    # Verifying this matters more than it looks - an unverified capture yields
    # 90 seconds of footage of the sign-in screen, and nothing reports it except
    # whoever eventually watches the video.
    needed = ("wh_last_worker", "wh_hives")
    state = None
    for attempt in range(1, 9):
        cand = ur._authed_storage_state(browser, username, display, hive, log=_log)
        keys = {i["name"] for o in (cand or {}).get("origins", [])
                for i in o.get("localStorage", [])}
        has_token = any(k.startswith("sb-") and "auth-token" in k for k in keys)
        missing = [k for k in needed if k not in keys]
        if has_token and not missing:
            _log(f"  auth verified, session complete (attempt {attempt})")
            state = cand
            break
        why = "no Supabase token" if not has_token else f"missing {missing}"
        _log(f"  [WARN] attempt {attempt}: {why} - retrying")
        # Back off before retrying. The server issues the token fine (auth logs
        # show 200s even on the attempts that "failed"); what varies is how long
        # the client takes to persist it - slower in headed mode, and slower
        # still when the edge runtime is authenticating concurrently. Hammering
        # immediately just reproduces the same race.
        # Capped backoff: wh_hives is the LAST key the app persists and on a
        # cold/loaded stack it can trail the token by >10s. Four attempts
        # (max 8s wait) was tuned on a warm stack and now under-waits; the
        # DB and auth are verifiably healthy when this fires.
        time.sleep(min(6.0, 1.5 * attempt))
    if state is None:
        raise RuntimeError(
            "could not capture a COMPLETE authed session after 8 attempts; "
            "recording now would just film the sign-in page")

    kwargs = {"viewport": VIEWPORT, "storage_state": state}
    if record_dir:
        kwargs["record_video_dir"] = str(record_dir)
        kwargs["record_video_size"] = VIEWPORT
    ctx = browser.new_context(**kwargs)
    ctx.add_init_script(
        f"localStorage.setItem('wh_active_hive_id','{hive}');"
        f"localStorage.setItem('wh_hive_id','{hive}');"
    )
    ctx.add_init_script(CURSOR_JS)
    return ctx, display, hive


# --------------------------------------------------------------------------
# tolerant interaction helpers
# --------------------------------------------------------------------------

class Report:
    """Records what the walk ACTUALLY did.

    A demo recorder that silently skips a step produces footage of nothing
    happening, and the skip is invisible until someone watches 90 seconds of
    video. Every hit and miss is logged so --dry-run can prove the journey
    before a frame is recorded."""

    def __init__(self):
        self.rows = []
        self.t0 = time.time()

    def add(self, act, action, target, ok, note="", xy=None, caption=None):
        # Wall-clock offset from the start of the recording. Without this the
        # edit has to eyeball its cut points from frame samples; with it, each
        # act's in/out are known numbers and the trim is exact.
        at = round(time.time() - self.t0, 2)
        row = {"at_s": at, "act": act, "action": action,
               "target": target, "ok": bool(ok), "note": note}
        # THE CAPTION is the narration track. A demo where things are clicked
        # with no on-screen explanation is the thing Ian called out; the edit
        # burns this as a lower-third at exactly this timestamp.
        if caption:
            row["caption"] = caption
        if xy:
            # viewport-fraction coords of the action - the camera in the edit
            # zooms toward THIS point at THIS timestamp. Measured, not staged.
            row["x"], row["y"] = round(xy[0], 4), round(xy[1], 4)
        self.rows.append(row)
        mark = "  ok " if ok else "  MISS"
        _log(f"{mark} {at:6.1f}s [{act}] {action} {target}"
             f"{(' - ' + note) if note else ''}")

    def acts(self):
        """First/last timestamp per act - the segment boundaries for the edit."""
        spans = {}
        for r in self.rows:
            s = spans.setdefault(r["act"], {"start": r["at_s"], "end": r["at_s"]})
            s["start"] = min(s["start"], r["at_s"])
            s["end"] = max(s["end"], r["at_s"])
        return spans

    @property
    def misses(self):
        return [r for r in self.rows if not r["ok"]]

    def summary(self):
        hit = sum(1 for r in self.rows if r["ok"])
        return f"{hit}/{len(self.rows)} steps landed"


def first_visible(page, selectors, timeout=4000):
    """Return the first selector that is actually visible, else None.

    Pages differ; a single hard-coded selector makes the whole journey brittle.
    Candidates are ordered most-specific first."""
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, state="visible", timeout=timeout)
            if el:
                return sel
        except Exception:
            continue
    return None



def _xy_of(page, selector):
    """Viewport-fraction centre of an element - the camera's zoom target."""
    try:
        el = page.query_selector(selector)
        box = el.bounding_box() if el else None
        vp = page.viewport_size
        if box and vp:
            return ((box["x"] + box["width"] / 2) / vp["width"],
                    (box["y"] + box["height"] / 2) / vp["height"])
    except Exception:
        pass
    return None


def try_click(page, rep, act, selectors, note="", timeout=4000, caption=None):
    sel = first_visible(page, selectors, timeout)
    if not sel:
        rep.add(act, "click", selectors[0], False, "no candidate visible")
        return False
    try:
        el = click_at(page, sel)
        xy = None
        try:
            box = el.bounding_box()
            vp = page.viewport_size
            if box and vp:
                xy = ((box["x"] + box["width"] / 2) / vp["width"],
                      (box["y"] + box["height"] / 2) / vp["height"])
        except Exception:
            pass
        rep.add(act, "click", sel, True, note, xy=xy, caption=caption)
        return True
    except Exception as e:
        rep.add(act, "click", sel, False, f"{type(e).__name__}")
        return False


def goto(page, rep, act, path, wait="domcontentloaded"):
    """domcontentloaded, not networkidle: shift-brain holds a live connection
    and never goes idle, which timed out the whole walk."""
    try:
        page.goto(f"{ur.WORKHIVE_URL}/workhive/{path}", wait_until=wait, timeout=30000)
        page.wait_for_timeout(LAND)
        landed = page.url.split("/")[-1]
        bounced = "index.html" in landed
        rep.add(act, "goto", path, not bounced,
                "BOUNCED to signin" if bounced else "")
        return not bounced
    except Exception as e:
        rep.add(act, "goto", path, False, f"{type(e).__name__}")
        return False


def scroll_read(page, dy=380, pause=READ):
    """Scroll a little and hold. Novices read; they do not skim."""
    page.mouse.wheel(0, dy)
    page.wait_for_timeout(pause)


# --------------------------------------------------------------------------
# the journey
# --------------------------------------------------------------------------

def act1_hive(page, rep):
    """Where a novice lands: the team's live board."""
    if not goto(page, rep, "1-hive", "hive.html"):
        return
    park(page)                      # read with the pointer OFF the content
    dwell(page, READ)
    scroll_read(page)
    scroll_read(page, 320)


def act2_logbook(page, rep):
    """CAPTURE - the fix that just happened gets written down."""
    if not goto(page, rep, "2-logbook", "logbook.html"):
        return
    park(page)
    dwell(page, READ)
    scroll_read(page, 300)

    # The logbook is not a list-plus-"New Entry" page; the entry wizard is
    # already ON the page. Step one is choosing the machine.
    if not try_click(page, rep, "2-logbook", ["#asset-picker-btn"],
                     note="which machine?",
                     caption="Start the entry: which machine?"):
        return
    page.wait_for_timeout(BEAT)

    # Search rather than scroll: it shows the picker actually working, and a
    # novice's real question is "is my machine in here?"
    if first_visible(page, ["#asset-picker-search"]):
        try:
            type_into(page, "#asset-picker-search", "pump", per_char_ms=110)
            rep.add("2-logbook", "type", "#asset-picker-search", True, "search for it",
                    xy=_xy_of(page, "#asset-picker-search"),
                    caption="Search your machine by name or code")
        except Exception as e:
            rep.add("2-logbook", "type", "#asset-picker-search", False, type(e).__name__)
    dwell(page, READ)

    # Pick a result. Real asset codes on screen are fine and in fact desirable -
    # this is the product being itself, the same way the reference shows a real
    # BIR form. The "no invented specifics" rule governs marketing COPY, not a
    # screen recording of live data.
    try_click(page, rep, "2-logbook", [
        "#asset-picker-modal button[data-asset-id]", "[data-asset-id]",
        "#asset-picker-results button",
    ], note="choose the machine", caption="Pick it from your own asset list")
    page.wait_for_timeout(BEAT)

    # :visible matters - there are two .btn-next in the DOM and the hidden one
    # is first in document order.
    try_click(page, rep, "2-logbook", [".btn-next:visible"],
              note="what happened?", caption="Next: what happened?")
    dwell(page, READ)

    # Type the lesson, but DO NOT submit. logbook addEntry is non-idempotent and
    # this runs against the shared local DB - a demo must not leave rows behind.
    # The real entry is a TWO-field story: the problem, then the action. The
    # old single-"textarea:visible" guess matched nothing and the journey
    # silently skipped the most important beat in the whole demo.
    for sel, text, cap in [
        ("#f-problem", "Drive belt worn and slipping under load.",
         "Say what went wrong, in plain words"),
        ("#f-action", "Replaced the belt and realigned the pulley.",
         "Say what you did to fix it"),
    ]:
        if first_visible(page, [sel]):
            try:
                type_into(page, sel, text, per_char_ms=42)
                rep.add("2-logbook", "type", sel, True, "not submitted",
                        xy=_xy_of(page, sel), caption=cap)
                dwell(page, READ)
            except Exception as e:
                rep.add("2-logbook", "type", sel, False, type(e).__name__)
        else:
            rep.add("2-logbook", "type", sel, False, "field not visible")

    # the knowledge field is what makes it a LESSON, not just a record
    if first_visible(page, ["#f-knowledge"]):
        try:
            type_into(page, "#f-knowledge",
                      "Check pulley alignment whenever a belt wears early.",
                      per_char_ms=40)
            rep.add("2-logbook", "type", "#f-knowledge", True, "not submitted",
                    xy=_xy_of(page, "#f-knowledge"),
                    caption="Add the lesson - this is what your AI remembers")
            dwell(page, READ)
        except Exception as e:
            rep.add("2-logbook", "type", "#f-knowledge", False, type(e).__name__)

    # The connectivity beat: the same page shows the whole team's entries.
    try_click(page, rep, "2-logbook", ["#btn-view-team"], note="the team's feed",
              caption="Every teammate's fixes, in one feed")
    dwell(page, READ)


def act3_asset(page, rep):
    """CONNECT - the machine's own record now carries that history."""
    if not goto(page, rep, "3-asset-hub", "asset-hub.html"):
        return
    park(page)
    dwell(page, READ)
    try_click(page, rep, "3-asset-hub", [
        ".asset-card", "[data-asset-id]", "tbody tr", ".card",
    ], note="open one machine's history")
    dwell(page, READ)
    scroll_read(page, 320)


def act4_assistant(page, rep):
    """RECALL - the payoff. Ask your own AI; it answers from what was captured."""
    if not goto(page, rep, "4-assistant", "assistant.html"):
        return
    park(page, frac_y=0.75)         # rest low, near the chat input
    dwell(page, BEAT)

    sel = first_visible(page, ["#chat-input", "textarea[placeholder*='ask' i]",
                               "textarea"])
    if not sel:
        rep.add("4-assistant", "type", "#chat-input", False, "no chat input")
        return
    try:
        type_into(page, sel, "What did we already fix on this line?", per_char_ms=58)
        rep.add("4-assistant", "type", sel, True, "a question a novice would ask",
                xy=_xy_of(page, sel))
    except Exception as e:
        rep.add("4-assistant", "type", sel, False, type(e).__name__)
        return

    dwell(page, BEAT)
    n_before = page.evaluate("() => document.querySelectorAll('#chat-messages > *').length")

    # #send-btn specifically: a generic has-text('Send') grabs the hidden
    # "Send feedback" widget that exists on every page and hangs the walk.
    if not try_click(page, rep, "4-assistant", ["#send-btn:visible"],
                     note="ask it"):
        try:
            page.evaluate("() => { if (typeof sendMessage === 'function') sendMessage(); }")
            rep.add("4-assistant", "send", "sendMessage()", True, "fallback")
        except Exception:
            return

    # Wait for the ANSWER ELEMENT, not for the page's character count.
    #
    # Two wrong oracles preceded this one, and the second is why this comment is
    # long. Body-text growth looked like a reasonable proxy and was not: after a
    # send, the page appends a disclaimer line ("AI-generated. Please
    # cross-check...") of roughly 88 characters within ~4 seconds. A growth
    # threshold fires on THAT, reports a confident "answered in 4s", and the
    # recording cuts away ~15s before the real answer ever renders - which is
    # exactly what shipped in the first take. The payoff beat of the whole demo
    # was missing while the step log said ok.
    #
    # Measured truth: #chat-messages children go 2 -> 4 on send (question +
    # placeholder) -> 5 at ~16-20s when the answer lands, and the answer carries
    # a thumbs feedback control that only a COMPLETED response has. Both
    # conditions together are the honest signal.
    answered, waited, answer_text = False, 0, ""
    while waited < 60000:
        page.wait_for_timeout(1500)
        waited += 1500
        try:
            n = page.evaluate("() => document.querySelectorAll('#chat-messages > *').length")
            done = page.evaluate(
                "() => (document.querySelector('#chat-messages')||{}).innerText"
                "      ? /\\uD83D\\uDC4D/.test(document.querySelector('#chat-messages').innerText)"
                "      : false")
        except Exception:
            continue
        if n > n_before and done:
            answered = True
            break
    if answered:
        try:
            answer_text = page.evaluate(
                "() => { const k=[...document.querySelectorAll('#chat-messages > *')];"
                "  for (let i=k.length-1;i>=0;i--) {"
                "    const t=(k[i].innerText||'').trim();"
                "    if (t.length > 40) return t.slice(0,160); } return ''; }") or ""
        except Exception:
            pass
    ans_xy = None
    if answered:
        # the ANSWER BUBBLE is the payoff - the one zoom that matters most
        try:
            ans_xy = page.evaluate(
                "() => { const k=[...document.querySelectorAll('#chat-messages > *')];"
                "  for (let i=k.length-1;i>=0;i--) {"
                "    const t=(k[i].innerText||'').trim();"
                "    if (t.length > 40) { const b=k[i].getBoundingClientRect();"
                "      return [(b.left+b.width/2)/innerWidth,(b.top+b.height/2)/innerHeight]; } }"
                "  return null; }")
        except Exception:
            pass
    rep.add("4-assistant", "answer", "AI response", answered,
            (f"landed in {waited/1000:.0f}s: {answer_text[:90]!r}" if answered
             else f"NO ANSWER after {waited/1000:.0f}s - the chain did not respond"),
            xy=tuple(ans_xy) if ans_xy else None)
    if answered:
        # Hold it. This is the beat the entire demo exists to deliver, and the
        # reference gives its equivalent moments 15-20s.
        dwell(page, 5200)
        scroll_read(page, 260)
        dwell(page, 2600)


def act5_pm(page, rep):
    """ACT - turn the lesson into a scheduled job, so it does not recur."""
    if not goto(page, rep, "5-pm", "pm-scheduler.html"):
        return
    park(page)
    dwell(page, READ)
    scroll_read(page, 340)


def act6_inventory(page, rep):
    """COMPLETE inventory journey: see the shortage -> filter to it -> open the
    part -> read its detail. The story is 'you know what you are out of'."""
    from demo_cursor import scroll as wh_scroll
    if not goto(page, rep, "6-inventory", "inventory.html"):
        return
    dwell(page, 1100)
    rep.add("6-inventory", "read", "page", True, caption="Spare-parts inventory - every part you stock")

    wh_scroll(page, 320, 900, rep, "6-inventory",
              caption="Low stock and out-of-stock, counted for you")
    dwell(page, 700)

    # filter down to the parts that actually need attention
    if try_click(page, rep, "6-inventory", ["#filter-status"],
                 caption="Filter to just what needs re-ordering"):
        dwell(page, 900)
        try:
            page.select_option("#filter-status", index=1)
            rep.add("6-inventory", "select", "#filter-status", True,
                    caption="Show only low and out-of-stock parts",
                    xy=_xy_of(page, "#filter-status"))
        except Exception as e:
            rep.add("6-inventory", "select", "#filter-status", False, str(e)[:60])
        dwell(page, 1200)

    # search a part by name - the everyday action
    if page.query_selector("#search-input"):
        try:
            type_into(page, "#search-input", "bearing", per_char_ms=110)
            rep.add("6-inventory", "type", "#search-input", True,
                    caption="Search a part by name",
                    xy=_xy_of(page, "#search-input"))
            dwell(page, 1300)
        except Exception as e:
            rep.add("6-inventory", "type", "#search-input", False, str(e)[:60])

    # open one part's detail
    for sel in ["#inv-list .part-row", "#inv-list > *:first-child",
                "[data-part-id]", ".part-card"]:
        if page.query_selector(sel):
            try_click(page, rep, "6-inventory", [sel],
                      caption="Open the part to see stock, location and history")
            dwell(page, 1800)
            break
    park(page)


def act7_pm(page, rep):
    """COMPLETE PM journey: the schedule -> pick an asset -> its task list ->
    tick a task done. The story is 'PMs stop slipping'."""
    from demo_cursor import scroll as wh_scroll
    if not goto(page, rep, "7-pm", "pm-scheduler.html"):
        return
    dwell(page, 1200)
    rep.add("7-pm", "read", "page", True, caption="PM scheduler - what is due, per machine")

    wh_scroll(page, 300, 850, rep, "7-pm",
              caption="Every asset with its PM status")
    dwell(page, 700)

    if page.query_selector("#asset-search"):
        try:
            type_into(page, "#asset-search", "pump", per_char_ms=115)
            rep.add("7-pm", "type", "#asset-search", True,
                    caption="Find the machine you are working on",
                    xy=_xy_of(page, "#asset-search"))
            dwell(page, 1300)
        except Exception as e:
            rep.add("7-pm", "type", "#asset-search", False, str(e)[:60])

    for sel in ["#asset-list > *:first-child", "#asset-list .asset-row",
                "[data-asset-id]"]:
        if page.query_selector(sel):
            try_click(page, rep, "7-pm", [sel],
                      caption="Open its PM checklist")
            dwell(page, 1800)
            break

    # the payoff: a task actually ticked off
    for sel in ["#det-tasks input[type=checkbox]", "#det-tasks .task-item",
                "#det-tasks > *:first-child"]:
        if page.query_selector(sel):
            try_click(page, rep, "7-pm", [sel],
                      caption="Tick a PM task as done - it logs itself")
            dwell(page, 1700)
            break
    park(page)


def act8_dayplanner(page, rep):
    """COMPLETE day-planner journey: the verdict -> today's load -> the
    calendar -> open a job. The story is 'you know what today looks like'."""
    from demo_cursor import scroll as wh_scroll
    if not goto(page, rep, "8-dayplanner", "dayplanner.html"):
        return
    dwell(page, 1300)
    rep.add("8-dayplanner", "read", "page", True, caption="Day planner - your whole day, decided")

    # the verdict card is the page's headline answer
    if page.query_selector("#dp-verdict"):
        rep.add("8-dayplanner", "read", "#dp-verdict", True,
                caption="Today's verdict: overdue, due, and this week",
                xy=_xy_of(page, "#dp-verdict"))
        dwell(page, 1600)

    wh_scroll(page, 360, 950, rep, "8-dayplanner",
              caption="Scroll to the day's schedule")
    dwell(page, 900)

    if page.query_selector("#calendar-wrap"):
        rep.add("8-dayplanner", "read", "#calendar-wrap", True,
                caption="Every job on a real calendar",
                xy=_xy_of(page, "#calendar-wrap"))
        dwell(page, 1500)

    for sel in ["#calendar-wrap .fc-event", "#calendar-wrap [data-event-id]",
                ".dp-job-row", "#dp-summary-details"]:
        if page.query_selector(sel):
            try_click(page, rep, "8-dayplanner", [sel],
                      caption="Open a job to see what it needs")
            dwell(page, 1800)
            break
    park(page)


ACTS = {1: act1_hive, 2: act2_logbook, 3: act3_asset, 4: act4_assistant,
        5: act5_pm, 6: act6_inventory, 7: act7_pm, 8: act8_dayplanner}


def run(acts=(1, 2, 3, 4, 5), dry_run=False, headed=False):
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_dir = None if dry_run else OUT_DIR / f"journey_{ts}"
    if video_dir:
        video_dir.mkdir(parents=True, exist_ok=True)

    rep = Report()
    started = time.time()
    with sync_playwright() as pw:
        # headed = Ian can WATCH it drive. Headless is the default because it
        # is faster and CI-safe, but a demo recorder nobody can see working is
        # hard to trust.
        browser = pw.chromium.launch(headless=not headed,
                                     args=['--window-size=1300,820'] if headed else [])
        ctx, display, hive = authed_context(browser, video_dir)
        page = ctx.new_page()
        # Reset the clock HERE: auth setup happens before the first frame is
        # captured, so timing from process start would offset every cut point.
        rep.t0 = time.time()
        _log(f"  worker={display}  hive={hive}")
        try:
            for n in acts:
                _log(f"\n=== ACT {n} ===")
                ACTS[n](page, rep)
        finally:
            page.close()
            ctx.close()
            browser.close()

    elapsed = time.time() - started
    _log(f"\n{rep.summary()}  in {elapsed:.0f}s")
    if rep.misses:
        _log(f"MISSED {len(rep.misses)}:")
        for m in rep.misses:
            _log(f"  [{m['act']}] {m['action']} {m['target']} - {m['note']}")

    out = {"steps": rep.rows, "elapsed_s": round(elapsed, 1), "acts": rep.acts()}
    _log("\nact spans (for the edit):")
    for act, span in sorted(out["acts"].items()):
        _log(f"  {act:<14} {span['start']:6.1f}s -> {span['end']:6.1f}s")
    if video_dir:
        webms = list(video_dir.glob("*.webm"))
        if webms:
            final = OUT_DIR / f"journey_{ts}.webm"
            shutil.move(str(webms[0]), final)
            out["video"] = str(final.relative_to(ROOT))
            _log(f"  video -> {out['video']}  ({final.stat().st_size/1e6:.1f} MB)")
        else:
            _log("  [WARN] no .webm produced")
        shutil.rmtree(video_dir, ignore_errors=True)
    (OUT_DIR / f"journey_{ts}.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Record the end-to-end WorkHive journey.")
    ap.add_argument("--dry-run", action="store_true",
                    help="walk it without recording; prove every step lands first")
    ap.add_argument("--acts", default="1,2,3,4,5")
    ap.add_argument("--headed", action="store_true",
                    help="show the browser so you can watch the journey run")
    a = ap.parse_args()
    acts = tuple(int(x) for x in a.acts.split(",") if x.strip())
    res = run(acts=acts, dry_run=a.dry_run, headed=a.headed)
    return 0 if not [s for s in res["steps"] if not s["ok"]] else 1


if __name__ == "__main__":
    sys.exit(main())
