"""bank_lx_walk.py - judge and bank the LAYER-UX browser rows (LXP / LXC) one MCP batch walked (tools/lx_walk.js).

The walk measures; this file judges, row by row, from the readings of THAT row's own page, persona and BOTH
viewports - and banks a row only through tools/record_mcp_walk.py, which refuses an LX receipt without its layer, its
persona and steps at phone-390 AND desktop-1280. A row whose reading does not hold is written as a RED receipt
(--unproven, with what was found) and its registry row goes to `walked`, open, carrying the finding - an open row asks
to be walked again; a falsely-closed one does not.

THE VERDICTS (each viewport must hold; the row holds only when both do):
  CA  at least 4 of the crew's own words on the page AND no developer word leaking (undefined, NaN, a raw uuid ...).
      For assistive-tech the text is what the accessibility tree exposes, not what the eye sees.
  C   figures read from dated domain rows must name their PERIOD and their CLOCK; a page showing fewer than five
      figures, or none from a domain read, owes no window (n/a, recorded as such).
  D   a provenance line the person can reach that says BOTH where the data came from AND when it last changed; for
      assistive-tech it must also be ANNOUNCED (role=status / aria-live). Postgres witness: the newest write in the
      first table the page read, for this person's hive.
  LB  the largest rendered list is small (<=100) or visibly bounded (pagination, load more, "showing N of M"), the DOM
      under 10,000 nodes, no single long task over 1.5 s.
  CI  no uncaught exception, no console error, no 400/404/5xx and no failed request among the page's own calls - the
      regressions a person meets right now (the walk's own stubs and held writes are excluded by construction).
  L   the page's writes leave a trail: the source-level trail check (tools/prove_w4_layer_trail.py) for this page,
      plus the trail rows in postgres for this person's hive naming who did what and when; a page offering this person
      no write and holding no write path owes none (n/a).
  AV  a model answer the walk made confidently WRONG, if the page showed it, sits in a card that says it is a machine's
      (a source, a confidence, an "AI" label, a caveat); machine output already on the page, likewise; a page with no
      model or pipeline output owes none (n/a).
  A   with the data reads refused, the page names the failure or offers a retry - never a blank and never a fake
      "nothing here"; with them 8 s late, it shows it is working. A page that read no data owes none (n/a).

  python tools/bank_lx_walk.py LXB1759912345678 [--apply]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
import registry_io as _rio  # noqa: E402 - the registry UNION: a cube (CX) row lives in trajectory_registry_cx.json
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB = "supabase_db_workhive"
GATES = {"CA": ["w4-layer-ca"], "C": ["w4-layer-clock", "clock-and-trail"],
         "LB": ["w4-layer-loadbearing", "growth-honesty"], "AV": ["w4-layer-model-honesty", "ai-render-provenance"],
         "CI": ["w4-layer-regression", "release-safety"], "L": ["w4-layer-trail", "audit-trail-coverage"],
         "A": ["w4-layer-availability", "cc_failure_injection"], "D": ["w4-layer-provenance", "source-chip-truth"],
         "RL": ["consumption-bound"],
         # the gate the LXP F rows already name: it re-reads the render contract and reddens on a revert
         "F": ["render-contract"],
         # the contract layers' U rows (2026-10-28): the layer's own W4 gate beside the prover of the behaviour the page
         # speaks about - the refusal, the session-ending prompt, the offline banner
         "S": ["w4-layer-entitlement", "tenant-refusal"], "AU": ["w4-layer-session", "lxp-au-session-identity"],
         "H": ["w4-layer-headers", "offline-resilience"]}
# the instrument the LEDGER asks of each layer's lens (live_walk_manifest._mcp_for), written into the receipt
INSTRUMENT = {"CA": "playwright-mcp", "LB": "playwright-mcp", "AV": "playwright-mcp", "CI": "playwright-mcp",
              "F": "playwright-mcp",
              # U on S and AU: the page read in the browser, the cast and its hive resolved in postgres; U on H is the
              # page alone (the served headers closed on F)
              "S": "playwright-mcp + postgres-mcp", "AU": "playwright-mcp + postgres-mcp", "H": "playwright-mcp",
              "C": "playwright-mcp + postgres-mcp", "L": "playwright-mcp + postgres-mcp",
              "A": "playwright-mcp + postgres-mcp", "D": "playwright-mcp + postgres-mcp",
              "RL": "playwright-mcp + postgres-mcp"}
# RL: reads whose size is the hive's size or the person's, never a table that grows with use - a membership list, a
# profile, the hive record. Unbounded is how they are meant to be read; the same set the C lens treats as identity.
RL_BOUNDED_BY_NATURE = {"v_hives_truth", "hives", "hive_members", "worker_profiles", "v_worker_truth",
                        "v_hive_members_truth", "marketplace_platform_admins"}
NOISE_RES = re.compile(r"Failed to load resource: the server responded with a status of (401|403|406|409|416)")


def psql(sql: str) -> list[str]:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return [ln for ln in (r.stdout or "").strip().splitlines() if ln.strip()]


# ★THE SHARED CHROME READS TOO, AND ITS READS ARE NOT THE PAGE'S (2026-10-08). The nav hub counts community posts and
# replies for its badge, the companion launcher reads its follow-up queue, and the identity helpers read the person's
# membership - on EVERY page. Counted as the page's reads, they made a locked ai-quality page "show 12 figures from 6
# domain reads". The set is DERIVED from the chrome scripts' own source, so a new chrome read is excluded the day it
# lands rather than the day someone notices.
CHROME_SCRIPTS = ("nav-hub.js", "companion-launcher.js", "offline-banner.js", "connectivity-widget.js",
                  "session-timeout.js", "device-fingerprint.js", "wh-feedback-fab.js", "browser-floor.js",
                  "offline-queue.js")
_CHROME: set = set()


def chrome_tables() -> set:
    if not _CHROME:
        for f in CHROME_SCRIPTS:
            p = ROOT / f
            if p.exists():
                src = p.read_text(encoding="utf-8", errors="replace")
                # a READ only: device-fingerprint INSERTS into hive_audit_log, and audit-log.html's own read of that
                # table must not be excluded because a chrome script writes to it
                _CHROME.update(re.findall(r"""\.from\(\s*['"`]([a-z0-9_]+)['"`]\s*\)\s*\.select\(""", src))
                _CHROME.update("rpc/" + x for x in re.findall(r"""\.rpc\(\s*['"`]([a-z0-9_]+)['"`]""", src))
        _CHROME.update({"analytics_events", "hive_members", "v_worker_truth", "worker_profiles"})
    return _CHROME


_PAGE_TABLES: dict = {}


def page_tables(page: str) -> set:
    """What the page's OWN source reads (the page and its same-basename script) - a chrome table the page itself also
    reads (community.html reads v_community_posts_truth for its feed) is the page's read too."""
    if page not in _PAGE_TABLES:
        src = ""
        for f in (ROOT / page, ROOT / (page[:-5] + ".js")):
            if f.exists():
                src += f.read_text(encoding="utf-8", errors="replace")
        _PAGE_TABLES[page] = set(re.findall(r"""\.from\(\s*['"`]([a-z0-9_]+)['"`]""", src)) | \
            {"rpc/" + x for x in re.findall(r"""\.rpc\(\s*['"`]([a-z0-9_]+)['"`]""", src)}
    return _PAGE_TABLES[page]


def own_reads(v: dict, page: str) -> list[str]:
    """The domain reads the row's own page made - its healthy-load calls minus the shared chrome's (unless the page's
    own source reads that relation too)."""
    ch, mine = chrome_tables(), page_tables(page)
    return [r for r in healthy_reads(v, page) if not r.startswith("fn:") and (r not in ch or r in mine)]


def healthy_reads(v: dict, page: str) -> list[str]:
    """The calls the row's OWN page made on its healthy load - never a hop on the route (every event is tagged)."""
    return sorted({x["u"].replace("/rest/v1/", "").replace("/functions/v1/", "fn:") for x in v.get("reads") or []
                   if x.get("mode") == "healthy" and x.get("pg") == page and x.get("st", 0) < 400
                   and x["u"] not in ("/rest/v1/analytics_events",) and not x["u"].startswith("/functions/v1/login")})


def judge(layer: str, persona: str, v: dict, page: str, ctx: dict) -> tuple[str, str]:
    """('ok'|'n/a'|'FAIL'|'UNPROVEN', one sentence) for ONE viewport's reading."""
    h = v.get("healthy") or {}
    # a visitor is the one persona read SIGNED OUT (lx_walk.body.js): a session at the reading means the page signed them
    # in, or the walk carried one over - either way it is not the visitor's page
    if persona == "anon":
        if not h:
            return "UNPROVEN", "the page was not read at this viewport - " + "; ".join(v.get("problems") or [])[:160]
        if h.get("session"):
            return "UNPROVEN", "a session was present at the reading, so this is not a signed-out visitor's page"
    elif not h or not h.get("session"):
        return "UNPROVEN", "not signed in at this viewport - " + "; ".join(v.get("problems") or [])[:160]
    if h.get("chars", 0) < 120 and layer not in ("A",):
        return "UNPROVEN", f"the page rendered {h.get('chars')} characters - nothing to read"
    vw = h.get("vw")
    if layer == "CA":
        ca = h.get("ca") or {}
        txt = f"{ca.get('crewCount')} crew word(s) ({', '.join((ca.get('crew') or [])[:8])})"
        if ca.get("jargon"):
            return "FAIL", txt + f", and developer words leak into the page: {', '.join(ca['jargon'])}"
        # ★A ONE-SENTENCE STATE CANNOT CARRY FOUR CREW WORDS (2026-10-28, project-report as a hive with no projects:
        # "No projects in this hive yet. Create one in the Project Manager and its report will build here."). The density
        # rule is for a page with content; an empty, choice or refusal state under 600 characters is judged on what it
        # must never do - leak a developer's words - and passes when it does not.
        if (ca.get("crewCount") or 0) < 4 and (h.get("chars") or 0) < 600:
            return "ok", (txt + f" on a {h.get('chars')}-character state screen (empty, choice or refusal) - too short to "
                          "owe four crew words, and no developer word leaks")
        if (ca.get("crewCount") or 0) < 4:
            return "FAIL", txt + " - fewer than four of the crew's own words"
        return "ok", txt + ", no developer word leaking" + (" (the accessibility-tree text)" if persona == "assistive-tech" else "")
    if layer == "C":
        c = h.get("c") or {}
        # ★A REGISTRY READ DATES NOTHING (2026-10-09, engineering-design: 16 catalog figures and one read of v_hives_truth).
        # Who is this, which hive, what role - those reads decide the page, they are not records over time, so figures
        # next to them owe no window. A page's figures owe one when it reads dated domain records.
        REGISTRY = {"v_hives_truth", "hives", "hive_members", "worker_profiles", "v_worker_truth", "v_hive_members_truth"}
        reads = [r for r in own_reads(v, page) if r.split("?")[0] not in REGISTRY]
        if (c.get("figures") or 0) < 5 or not reads:
            return "n/a", (f"{c.get('figures')} figure(s) and {len(reads)} domain read(s) - no dated figures, so no window "
                           "is owed")
        if c.get("period") and c.get("clock"):
            return "ok", f"{c['figures']} figures from {len(reads)} domain read(s) name their period (\"{c['period']}\") and clock (\"{c['clock']}\")"
        # ★A ROLLING WINDOW ENDING NOW CARRIES ITS OWN CLOCK (2026-10-08, analytics: "last 90 days (rolling, ending now)").
        # 90 x 24 hours back from this moment has no hour boundary for a timezone to move, so "ending now" IS its reference.
        # A CALENDAR window does have one - "today" and "this week" begin at a midnight that is somewhere - so a page that
        # also names a calendar window still owes its timezone.
        if c.get("rolling") and not c.get("calendar"):
            return "ok", (f"{c['figures']} figures from {len(reads)} domain read(s) state a rolling window anchored at now "
                          f"(\"{c['rolling']}\") - its reference point is its clock, with no calendar boundary for a timezone to move")
        miss = [x for x, ok in (("no period", c.get("period")), ("no clock (timezone)", c.get("clock"))) if not ok]
        return "FAIL", f"{c['figures']} figures from {len(reads)} domain read(s) ({', '.join(reads[:3])}) state {' and '.join(miss)}" + (f" - the period it does name: \"{c['period']}\"" if c.get("period") else "")
    if layer == "D":
        d = h.get("d") or {}
        reads = own_reads(v, page)
        if not reads:
            return "n/a", "the page read no domain data - there is no provenance to show"
        # ★A GATE SHOWS NO DATA, SO IT HAS NOTHING TO ATTRIBUTE (2026-10-09, audit-log as a worker: 288 chars, 0 figures).
        # The page READ to decide the gate (who is this, which hive, what role) and showed none of it - provenance is owed
        # for data a person is shown, and here they are shown a door, not a figure or a list.
        shown_n = ((h.get("lb") or {}).get("maxList") or {}).get("n") or 0
        if not ((h.get("c") or {}).get("figures") or 0) and shown_n <= 1:
            return "n/a", (f"the page shows this person no data (0 figures, largest list {shown_n}) - its reads only decided what "
                           "to show them, so there is nothing to attribute")
        base = (f"{d.get('reachable')} reachable provenance line(s), {d.get('announced')} announced; source "
                f"{d.get('saysSource')}, recency {d.get('saysRecency')}: {' | '.join((d.get('samples') or [])[:2])[:200]}")
        need_announce = persona == "assistive-tech"
        ok = (d.get("reachable") or 0) >= 1 and d.get("saysSource") and d.get("saysRecency") and (not need_announce or (d.get("announced") or 0) >= 1)
        if ok:
            return "ok", base + (f". {ctx.get('dWitness')}" if ctx.get("dWitness") else "")
        why = []
        if not d.get("reachable"):
            why.append("no provenance line reaches the person" + (f" ({d.get('hiddenButRendered')} rendered inside aria-hidden)" if d.get("hiddenButRendered") else ""))
        if d.get("reachable") and not d.get("saysSource"):
            why.append("it never says WHERE the data came from")
        if d.get("reachable") and not d.get("saysRecency"):
            why.append("it never says WHEN it last changed")
        if need_announce and d.get("reachable") and not d.get("announced"):
            why.append("nothing announces it to a screen reader")
        return "FAIL", base + " - " + "; ".join(why)
    if layer == "LB":
        lb = h.get("lb") or {}
        ml = lb.get("maxList") or {}
        n = ml.get("n") or 0
        lt = lb.get("longTasks") or {}
        txt = (f"largest rendered list {n} item(s) ({ml.get('tag', '-')}{('#' + ml['id']) if ml.get('id') else ''}), "
               f"{'visibly bounded' if lb.get('bounded') else 'no visible bound'}, {lb.get('nodes')} DOM nodes, "
               f"{lt.get('count')} long task(s) totalling {lt.get('total')} ms (longest {lt.get('max')} ms), "
               f"DOMContentLoaded {lb.get('dcl')} ms")
        bad = []
        if n > 100 and not lb.get("bounded"):
            bad.append(f"renders {n} items with nothing saying the list is bounded - as the data grows the page grows with it")
        if (lb.get("nodes") or 0) > 10000:
            bad.append("over 10,000 DOM nodes")
        if (lt.get("max") or 0) > 1500:
            bad.append(f"a single long task of {lt.get('max')} ms freezes the page")
        return ("FAIL", txt + " - " + "; ".join(bad)) if bad else ("ok", txt)
    if layer == "RL":
        # "bound what this page can consume, and say so when it has" - read off the network, not the source: every
        # list read the page made on its own load, the limit it asked for and the rows that came back
        reads = [x for x in v.get("rl") or [] if x.get("pg") == page]
        says = (h.get("rl") or {}).get("says")
        # a limit of 1 is a lookup (the person's own record, the newest row), not a list someone could take for a total
        lists = [x for x in reads if not x.get("single") and not (x.get("lim") is not None and x["lim"] <= 1)]
        bound = [x for x in lists if x.get("lim")]
        unbound = [x for x in lists if not x.get("lim") and (x.get("got") or 0) > 1
                   and x.get("t") not in RL_BOUNDED_BY_NATURE and not str(x.get("t")).startswith("rpc/")]
        binding = [x for x in bound if x.get("got") is not None and x["got"] >= x["lim"]]
        wit = ctx.get("rlPg") or []
        pgtxt = "; ".join(f"postgres: the largest hive holds {big} row(s) of {tb} against this page's cap of {lim}"
                          for tb, lim, big in wit if big is not None)
        if not reads:
            return "n/a", f"the page made no data read on its own load at {vw}px, so it consumes nothing a cap could bound"
        if unbound:
            return "FAIL", ("reads " + ", ".join(f"{x['t']} ({x['got']} rows)" for x in unbound[:4])
                            + " with no bound - each grows with the hive, and the page fetches all of it")
        # a folded part of the page that holds the capped list AND its slice sentence shows no total at all (the walker's
        # rl.folded: the sentence, and how many list rows the same unrendered part holds) - dayplanner's PM rail on a phone
        folded = (h.get("rl") or {}).get("folded") or {}
        if (binding and not says and folded.get("says") and folded.get("opener")
                and (folded.get("rows") or 0) >= max(x["lim"] for x in binding)):
            return "ok", (f"{len(reads)} read(s) on the page's own load; {', '.join(x['t'] for x in binding[:3])} came back "
                          f"at its cap, and the list sits folded at {vw}px ({folded.get('at')}, {folded.get('rows')} rows, "
                          f"opened by \"{folded['opener']}\") with its own slice sentence (\"{folded['says']}\") - nothing on "
                          f"screen shows the cap as a total, and opening it says what it is a slice of")
        if binding and not says:
            return "FAIL", ("a cap shown as a total: " + ", ".join(f"{x['t']} came back FULL at its cap of {x['lim']}" for x in binding[:4])
                            + " and nothing on the page says the list is a slice")
        head = (f"{len(reads)} read(s) on the page's own load, {len(bound)} of them capped lists"
                + (f", {len(binding)} at the cap and said (\"{says}\")" if binding
                   else (", none at its cap for this person" + (f" (largest: {max(bound, key=lambda x: x.get('got') or 0)['got']} of "
                                                              f"{max(bound, key=lambda x: x.get('got') or 0)['lim']})" if bound else ""))))
        # what the page asks a FUNCTION for is bounded where it is computed (the function is its own subject); say
        # that it was asked for, so "no capped list" is never read as "consumes nothing"
        fns = sorted({str(x.get("u", "")).split("/functions/v1/")[-1] for x in v.get("reads") or []
                      if x.get("mode") == "healthy" and x.get("pg") == page and "/functions/v1/" in str(x.get("u", ""))})
        fntxt = (f"; it also asked {', '.join(fns[:4])} for computed results, bounded where they are computed" if fns else
                 "; nothing larger is loaded until the person asks for it")
        # the largest-hive figure is a WITNESS, not a verdict: a read filtered by seller or by person is not a hive's slice
        return "ok", head + fntxt + (("; " + pgtxt) if pgtxt else "")
    if layer == "CI":
        errs = [e["msg"] for e in v.get("pageErrors") or [] if e.get("mode") == "healthy" and e.get("pg") == page]
        cons = [e["msg"] for e in v.get("console") or [] if e.get("mode") == "healthy" and e.get("pg") == page and not NOISE_RES.search(e["msg"])
                and "the walk refused" not in e["msg"]]
        http = [f"{x['st']} {x['m']} {x['u']}" for x in v.get("http") or [] if x.get("mode") == "healthy" and x.get("pg") == page
                and ((x.get("st") in (400, 404)) or (x.get("st") or 0) >= 500
                     or (x.get("st") == 0 and "ERR_ABORTED" not in str(x.get("fail")) and "aborted" not in str(x.get("fail")).lower()))]
        # ★a RETURNER's refused refresh is the walk's own premise, not a broken call (2026-10-09, LXP1862). The walk plants
        # a 21-day-old session whose refresh token is the literal "expired"; the server's 400 on grant_type=refresh_token
        # IS the correct refusal, and Chrome logs it as one "Failed to load resource ... 400" line no page code can
        # silence. It only lands on a row whose page is the wall itself (index.html - every other returner row's page
        # loads after sign-in). Excused only when the wall then showed, one console line per excused call, and named.
        refused = ""
        if persona == "returner" and (v.get("returner") or {}).get("wallShown"):
            seeded = [c for c in http if c.startswith("400 POST /auth/v1/token?grant_type=refresh_token")]
            if seeded:
                http = [c for c in http if c not in seeded]
                for _ in seeded:
                    hit = next((c for c in cons if "status of 400" in c), None)
                    if hit is not None:
                        cons.remove(hit)
                refused = (f"; the walk's planted 21-day-old session was refused by the server ({len(seeded)} x 400 on "
                           f"grant_type=refresh_token) and the sign-in wall showed - the returner's expected handshake")
        txt = f"{len(errs)} uncaught exception(s), {len(cons)} console error(s), {len(http)} broken call(s)"
        if errs or cons or http:
            return "FAIL", txt + ": " + "; ".join((errs + cons + http)[:4])[:300]
        return "ok", (txt + f" on the page's own load at {vw}px" + refused + f"; {ctx.get('ciWitness', '')}").rstrip("; ")
    if layer == "L":
        writes = (h.get("l") or {}).get("writes") or []
        src = ctx.get("trailSrc") or ("?", "")
        trail = ctx.get("trailPg") or ""
        if not writes:
            # ★"NO WRITE ON THE FIRST SCREEN" IS NOT "THIS PAGE WRITES NOTHING" (2026-10-28). The visible-control reading
            # closed 268 production rows as n/a - logbook's Save Entry sits behind its wizard's first step, alert-hub's
            # triage controls are led by a symbol - so whether who-did-what is recorded hung on where the write was drawn.
            # The page's writes are read from its source (prove_w4_layer_trail.check_page): writes that reach the trail are
            # the F answer; writes that do not are a FAIL; only a page whose source writes nothing is n/a.
            if src[0] == "BAD":
                return "FAIL", f"no write on this person's first screen, and the page's own writes do not reach the trail: {src[1]}"
            if src[0] == "ok":
                return "ok", (f"no write on this person's first screen at this width; the page's own writes (behind its flow) "
                              f"reach the trail - {src[1][:160]}")
            return "n/a", (f"offers this person no write at this width, and the page's source writes nothing that would "
                           f"leave a trail ({src[1][:120]})")
        # a control that LOOKS like a write on a page whose source stores nothing a colleague could read (analytics-report's
        # "Generate Report" compiles a document in the browser) leaves no act for a trail to name
        if src[0] == "n/a" and not ctx.get("noHive"):
            return "n/a", f"offers {', '.join(writes[:5])}, but the page stores nothing a trail would owe ({src[1][:140]})"
        # ★A PERSON WITH NO HIVE HAS NO TRAIL ROW TO FIND BEFORE THEIR FIRST ACT (2026-10-28). The postgres witness counts
        # rows naming them, which is zero for anybody who has not yet created or joined a hive - true of every first
        # visit, so it failed the honest case for ever. Their trail is judged where it is decided: the page they were
        # actually shown (community sends them to hive.html's Create / Join) must write its acts to the trail.
        if ctx.get("noHive"):
            s2 = ctx.get("trailSrcShown") or src
            if s2[0] == "BAD":
                return "FAIL", f"offers {', '.join(writes[:5])} on {ctx.get('shownPage')}; {s2[1]}"
            return "ok", (f"offers {', '.join(writes[:5])} on {ctx.get('shownPage')}; this person holds no hive, so no trail "
                          f"row can name them before their first act - the write path reaches the trail ({s2[1][:160]})")
        if src[0] == "BAD":
            return "FAIL", f"offers {', '.join(writes[:5]) or 'no visible write'}; {src[1]}"
        if not ctx.get("trailOk"):
            return "FAIL", f"offers {', '.join(writes[:5]) or 'no visible write'}; the source reaches the trail ({src[1][:120]}) but {trail}"
        return "ok", f"offers {', '.join(writes[:5]) or 'no visible write at this width'}; {src[1][:160]}; {trail}"
    if layer == "AV":
        av = (v.get("av") or {}).get("av") or {}
        calls = (v.get("av") or {}).get("modelCalls") or 0
        hav = h.get("av") or {}
        if av.get("markShown"):
            if av.get("markHonest"):
                return "ok", f"the model's confidently WRONG answer was shown inside a card that marks it as a machine's: \"{(av.get('markCard') or '')[:160]}\""
            return "FAIL", f"the model's confidently WRONG answer was shown as bare fact - its card carries no source, confidence, AI label or caveat: \"{(av.get('markCard') or '')[:160]}\""
        if hav.get("modelCard"):
            leaf = hav.get("modelLeaf") or hav["modelCard"][:80]
            if hav.get("modelCardHonest"):
                return "ok", f"{calls} model call(s) on load (answered by the stub, not rendered); the pipeline output \"{leaf}\" sits in a card that marks it: \"{hav['modelCard'][:140]}\""
            # a PIPELINE count (an anomaly tally, a risk score) is answerable for at page level: the page names where its
            # figures came from (a reachable source line) or how they are computed (an openable method disclosure)
            d = h.get("d") or {}
            if (d.get("reachable") and d.get("saysSource")) or d.get("method"):
                return "ok", (f"the pipeline output \"{leaf}\" is attributable on the page: "
                              + ("a reachable source line says where it came from" if d.get("reachable") and d.get("saysSource") else "")
                              + (" and " if (d.get("reachable") and d.get("saysSource")) and d.get("method") else "")
                              + (f"{d.get('method')} openable 'how this is computed' disclosure(s)" if d.get("method") else ""))
            return "FAIL", f"the pipeline output \"{leaf}\" sits in a card with no honesty mark and the page names no source or method for it: \"{hav['modelCard'][:140]}\""
        if calls == 0:
            return "n/a", "no model call and no machine output on this page for this person - no pipeline that could be wrong"
        # it called a model/pipeline on load and did not render that answer: if it shows FIGURES, they come from a pipeline,
        # and the page owes the reader where they came from (a reachable source line, or an openable method)
        d = h.get("d") or {}
        if ((h.get("c") or {}).get("figures") or 0) >= 5:
            if (d.get("reachable") and d.get("saysSource")) or d.get("method"):
                return "ok", (f"{calls} pipeline call(s) on load (answered by the stub - their answers are not rendered on "
                              f"arrival); the figures the page shows are attributable: "
                              + "; ".join((d.get("samples") or [])[:1])[:160])
            return "FAIL", (f"{calls} pipeline call(s) on load, and the {(h.get('c') or {}).get('figures')} figures the page "
                            "shows name no source and no method - a wrong pipeline would read as fact")
        return "n/a", f"{calls} model call(s) on load, none of whose answers this page renders on arrival, and no figures shown"
    if layer == "A":
        reads = own_reads(v, page) + [r for r in healthy_reads(v, page) if r.startswith("fn:")]
        if not reads:
            return "n/a", "the page read nothing from a service - nothing behind it can be slow or down"
        dn = (v.get("down") or {}).get("a") or {}
        sl = v.get("slow") or {}
        down_ok = bool(dn.get("saysFailure")) and not dn.get("blank")
        early = sl.get("early") or {}
        late = sl.get("late") or {}
        painted = (early.get("chars") or 0) >= 0.9 * (sl.get("healthyChars") or 0)   # it did not wait for the data at all
        recovered = (late.get("chars") or 0) >= max(200, 0.6 * (sl.get("healthyChars") or 0))
        slow_ok = (bool(early.get("busy") or early.get("loadingWords")) or painted) and (recovered or bool(late.get("busy")))
        txt = (f"reads refused: says \"{dn.get('saysFailure')}\", retry {dn.get('retry') or 'none'}, fake-empty "
               f"{dn.get('fakeEmpty')}, blank {dn.get('blank')}; reads 8 s late: working sign {bool(early.get('busy') or early.get('loadingWords'))}{' (its content was already painted at 2.5 s)' if painted else ''}, "
               f"content {late.get('chars')} of {sl.get('healthyChars')} chars at 18 s" + ("" if recovered else (" and still visibly working" if late.get("busy") else " and no longer working")))
        if down_ok and slow_ok:
            return "ok", txt
        why = ([] if down_ok else ["with its reads refused it never says the read failed" + (" (a standing refresh control is not an answer)" if dn.get("retry") else "")]) + \
              ([] if slow_ok else ["with its reads late it shows no working sign, or never recovers"])
        return "FAIL", txt + " - " + "; ".join(why)
    if layer == "F":
        # ★THE RENDER CONTRACT, READ BY THE WALK ITSELF (2026-10-28) - the checks the LXP F rows were judged on by hand
        # (2026-10-06): nothing reaches past the viewport outside a scroll container, no target under 24px (WCAG 2.5.8,
        # the inline-link exception honoured), every control named, one exposed h1, a main landmark, a skip link that
        # lands, no duplicate id, nothing left busy once the page settled, and a way off the page.
        f = h.get("f")
        if not f:
            return "UNPROVEN", "this walk took no render-contract reading - re-walk with the current lx_walk.body.js"
        bad = []
        if f.get("overflow"):
            bad.append(f"content reaches past the {f.get('vw')}px viewport outside any scroll container ({'; '.join(f['overflow'][:2])})")
        if f.get("smallCount"):
            bad.append(f"{f['smallCount']} target(s) under 24px ({'; '.join(f['small'][:3])})")
        if f.get("unnamedCount"):
            bad.append(f"{f['unnamedCount']} control(s) with no accessible name ({', '.join(f['unnamed'][:4])})")
        if f.get("h1") != 1:
            bad.append(f"{f.get('h1')} exposed h1 (one names the page)")
        if not f.get("main"):
            bad.append("no main landmark")
        if f.get("skip") and not f.get("skipTarget"):
            bad.append(f"a skip link to {f['skip']}, which does not exist")
        if f.get("dupIds"):
            bad.append(f"duplicate id(s) {', '.join(f['dupIds'][:4])}")
        if f.get("stuck"):
            bad.append(f"{f['stuck']} still busy after the page settled")
        if not f.get("escape"):
            bad.append("no way off the page - no back, home or close control, no link elsewhere, no nav hub")
        txt = (f"render contract at {f.get('vw')}px: {f.get('controls')} control(s), h1 \"{f.get('h1Text')}\", "
               f"escape via {', '.join((f.get('escape') or [])[:2]) or 'nothing'}")
        if bad:
            return "FAIL", txt + " - " + "; ".join(bad)
        return "ok", (txt + " - nothing past the viewport, no target under 24px, every control named, one h1, a main "
                      "landmark" + (", a skip link that lands" if f.get("skip") else "") + ", no duplicate id, nothing stuck")
    # ★THE CONTRACT LAYERS' U PILLAR (2026-10-28). Only these rows of S, AU and H are walked (lx_walk_args.U_ONLY_LAYERS);
    # their F and I pillars close on the library provers. Each judge reads what the PERSON is told, never the database.
    if layer == "S":
        u = h.get("u")
        if u is None:
            return "UNPROVEN", "this walk took no reading of what the page says about whose rows it shows"
        said = ([f"names the hive \"{u['hiveNamed']}\""] if u.get("hiveNamed") else []) + \
               ([f"says \"{u['yours']}\""] if u.get("yours") else []) + \
               ([f"says what it withholds (\"{u['refusal']}\")"] if u.get("refusal") else []) + \
               ([f"says its rows are published (\"{u['publicSaid']}\")"] if u.get("publicSaid") else [])
        if said:
            return "ok", "the person can tell whose rows these are: the page " + " and ".join(said[:2])
        return "FAIL", ("nothing on the page says whose rows it shows - no hive named, no \"your ...\" - or that anything "
                        "was withheld")
    if layer == "AU":
        if persona == "anon":
            return "n/a", "a visitor holds no session, so there is none to end"
        idle = v.get("idle")
        if idle is None:
            return "UNPROVEN", "this walk did not induce the idle path"
        if not idle.get("prompt"):
            return "FAIL", ("with the session about to end (the platform's own idle path, shortened by its documented test "
                            "hook) the page said nothing")
        miss = ([] if (idle.get("role") in ("alertdialog", "dialog", "alert") or idle.get("live")) else ["not announced (no role, no aria-live)"]) \
            + ([] if idle.get("name") else ["not named"]) + ([] if idle.get("focusIn") else ["focus stayed behind it"])
        txt = (f"the session-ending prompt \"{(idle.get('text') or '')[:90]}\" - role {idle.get('role')}, named "
               f"\"{idle.get('name')}\", focus {'moved to it' if idle.get('focusIn') else 'left behind'}")
        return ("FAIL", txt + " - " + "; ".join(miss)) if miss else ("ok", txt)
    if layer == "H":
        off = v.get("offline")
        if off is None:
            return "UNPROVEN", "this walk did not take the network away"
        if off.get("said"):
            return "ok", (f"with the network gone the open page said \"{str(off['said'])[:90]}\""
                          + (" in a live region" if off.get("announced") else "")
                          + (f", and on its return \"{off['back']}\"" if off.get("back") else ""))
        return "FAIL", ("the network went away under the open page and nothing on it said so - what it shows reads as "
                        "live")
    return "UNPROVEN", f"no judge for layer {layer}"


# A cube row reads its layer's ask through one PILLAR (roadmap §CX). The layer's judge above reads the truth and wiring of
# the page (F); most of what it reads is also what the person SEES (U) - crew words, a period and clock, a reachable
# provenance line, a visible bound, a failure sentence, a marked machine card, a "slice" sentence, a page that loads
# clean. Three readings the walk does not take yet are HELD, never banked and never written red: I (which hive's rows
# reached this persona's page), A on a layer other than A (offline and on 429, layer by layer), and U on the trail (L),
# whose evidence is in postgres where the person cannot see it. Held rows stay open for the instrument that answers them.
PILLAR_LENS = {"U": "the person can tell", "F": "it is true and wired", "I": "this persona may, and may not",
               "A": "at phone-390 and desktop-1280, offline and on 429"}
HOLD = "HOLD"


_PUBLIC: set | None = None


def public_by_design() -> set:
    """The tables and views every signed-in person may read across hives - tools/tenant_declarations.mjs, the one list
    prove_tenant_refusal and the AU identity prover already share (a marketplace listing is another hive's by nature)."""
    global _PUBLIC
    if _PUBLIC is None:
        r = subprocess.run(["node", "-e", "import('./tools/tenant_declarations.mjs').then((m) => console.log(JSON.stringify("
                            "[...Object.keys(m.PUBLIC_BY_DESIGN), ...Object.keys(m.PUBLIC_VIEWS_BY_DESIGN || {})])))"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=60)
        try:
            _PUBLIC = set(json.loads((r.stdout or "").strip() or "[]"))
        except ValueError:
            _PUBLIC = set()
    return _PUBLIC


def i_view(v: dict, page: str, ctx: dict, verdict: tuple[str, str]) -> tuple[str, str]:
    """I - this persona may, and may not. The walk records which hives' rows each read handed the person (lx_walk.body.js
    `scope`); a row from a hive they are not in, through a read that is not public by design, is the boundary failing."""
    own = ctx.get("castHives")
    scope = [s for s in v.get("scope") or [] if s.get("pg") == page]
    if own is None or "scope" not in v or any("asked" not in s for s in scope):
        return HOLD, "this walk did not record what each read asked for and which hives' rows came back"
    uid, name = (ctx.get("castUid") or ""), (ctx.get("cast") or "").strip().lower()
    pub = public_by_design()
    foreign, named, public, rls = [], 0, 0, 0
    for s in scope:
        base = str(s.get("t") or "").split("?")[0]
        if base in pub or base.replace("rpc/", "") in pub:
            public += 1
            continue
        a = s.get("asked") or {}
        bad = ([f"rows of {len(x)} other hive(s)" for x in [[h for h in s.get("hives") or [] if h != "null" and h not in own]] if x]
               + [f"asked for hive {h[:8]}" for h in a.get("hive") or [] if h not in own]
               + [f"asked for another account {u[:8]}" for u in a.get("uid") or [] if uid and u != uid]
               + [f"asked for {n!r}" for n in a.get("name") or [] if name and n.replace("+", " ").strip().lower() != name])
        if bad:
            foreign.append(f"{base} ({', '.join(bad[:2])})")
        elif a.get("hive") or a.get("uid") or a.get("name") or s.get("hives"):
            named += 1
        else:
            rls += 1
    if foreign:
        return "FAIL", "this person's page asked for or received another's rows: " + "; ".join(foreign[:4])
    v0, why = verdict
    note = (f"{named} read(s) named this person's own hive or identity, {public} public by design, {rls} decided by "
            f"row-level security alone - none asked for or returned another hive's rows" if scope else
            "the page made no data read of its own")
    return v0, note + "; " + why


def a_view(layer: str, verdict: tuple[str, str], v: dict, ctx: dict) -> tuple[str, str]:
    """A off the A layer - "the <layer> ask, at phone-390 and desktop-1280, offline and on 429" (2026-10-28). The walk answered
    every data read 429 with a Retry-After (lx_walk.body.js `r429`), counted the calls the page made while refused, and read
    the page with the network gone after a normal load (`aOff`). Each layer is asked what IT promises under that weather."""
    r = v.get("r429")
    if not r:
        return HOLD, "this walk did not rate-limit the page's reads"
    rd = r.get("read") or {}
    a, d, c = rd.get("a") or {}, rd.get("d") or {}, rd.get("c") or {}
    told = a.get("saysFailure")
    off = ((v.get("aOff") or {}).get("a") or {}).get("saysFailure")
    base = (f"on 429 ({r.get('calls')} call(s) to {r.get('endpoints')} endpoint(s) while refused, at most "
            f"{r.get('maxPerEndpoint')} to one)" + (f", the page said \"{told}\"" if told else ", the page said nothing about it")
            + (f"; offline it said \"{off}\"" if off else ""))
    # ★ON 429 THE WRONG MOVE IS TO ASK AGAIN (the client-retried-four-times lesson): the SAME request sent two or more times
    # MORE in a 10 s refusal window than in an equal window of an ordinary load is a retry loop, whatever the layer. A
    # duplicate the page always makes is not - the identity lookup goes out four times on every load, refused or not.
    if r.get("fastRepeats") is None:
        return HOLD, "this walk counted calls but not repeats of the same request - re-walk with the current lx_walk.body.js"
    if (r.get("fastRepeats") or 0) >= 2:
        return "FAIL", (f"on 429 (Retry-After 5 s) the page sent {r.get('fastReq')} {r.get('fastRepeats')} more times than an "
                        f"ordinary load does - it retries instead of backing off; " + base)
    if layer == "RL":
        return "ok", "the bound holds under refusal: no retry storm - " + base
    if layer == "S":
        if a.get("fakeEmpty") and not told:
            return "FAIL", (f"on 429 the page said \"{a['fakeEmpty']}\" - a refused read shown as an empty hive, which tells the "
                            f"person nothing exists rather than that they could not see it; " + base)
        return "ok", "a refused read is not shown as an empty hive - " + base
    if layer == "D":
        if (c.get("figures") or 0) >= 5 and d.get("saysRecency") and not told:
            return "FAIL", (f"on 429 the page showed {c.get('figures')} figures under a fresh-looking source line and never said "
                            f"its reads failed; " + base)
        return "ok", "no figure is passed off as fresh while every read failed - " + base
    if layer == "L":
        lv, lwhy = verdict
        if lv == "n/a":
            return "n/a", "the page records nothing for a trail to owe, offline or not - " + lwhy[:120]
        g = ctx.get("writeGuard")
        if not g:
            return "FAIL", ("the page writes and keeps a trail, but nothing in it refuses a write it cannot send or queues it "
                            "with its author - offline, an act could vanish without a name; " + base)
        return "ok", f"a write it cannot send is refused or queued with its author ({g}); " + base
    return "UNPROVEN", f"no A reading for layer {layer}"


def pillar_view(pillar: str | None, layer: str, verdict: tuple[str, str], v: dict | None = None, page: str = "",
                ctx: dict | None = None) -> tuple[str, str]:
    lv, why = verdict
    # S, AU and H are walked for their U rows only: their F and I close on the contract provers, never on a page reading
    if layer in ("S", "AU", "H") and pillar not in ("U", "A"):
        return HOLD, f"the {layer} ask through {pillar} is answered by its contract prover, not by this walk"
    # the S judge above reads the U sentence; S under 429 is its own reading, not a consequence of that one
    if pillar == "A" and layer == "S":
        return a_view(layer, verdict, v or {}, ctx or {})
    if not pillar or pillar == "F" or lv in ("FAIL", "UNPROVEN"):
        return verdict                       # F is the layer's own verdict, and a failing layer fails every lens
    if pillar == "U":
        # ★U ON THE TRAIL IS WHO DID WHAT, AS THE PERSON SEES IT (2026-10-28 - it was HELD: "the trail is written in postgres").
        # The trail being kept is L's F verdict; U asks whether this page tells the person: a name on the record ("logged by
        # Ben Ocampo", "Ben Ocampo · 2h ago"), or a history one tap away.
        if layer == "L" and lv == "ok":
            u = ((v or {}).get("healthy") or {}).get("u")
            if u is None:
                return HOLD, "this walk took no reading of who-did-what on the page - re-walk with the current lx_walk.body.js"
            if u.get("attrib"):
                return "ok", f"the page says who did what (\"{u['attrib'][:70]}\"); " + why
            if u.get("history"):
                return "ok", f"who did what is one tap away (\"{u['history']}\"); " + why
            ot = (v or {}).get("oneTap") or {}
            # a page holding NO record yet (the solo owner's empty register) has had nothing done on it to attribute
            if "opened" in ot and ot.get("opened") is None:
                return "n/a", ("the page holds no record yet - nothing has been done on it for it to say who did; " + why)
            if ot.get("attrib") or ot.get("history"):
                return "ok", (f"who did what is one tap away: opening \"{ot.get('opened')}\" shows "
                              f"\"{(ot.get('attrib') or ot.get('history'))[:70]}\"; " + why)
            return "FAIL", ("the page writes and the trail is kept, but nothing on it tells this person who did what - no "
                            "name on its records, no history to open"
                            + (f", and opening \"{ot['opened']}\" named nobody" if ot.get("opened") else "") + "; " + why)
        return lv, why
    if pillar == "A":
        return verdict if layer == "A" else a_view(layer, verdict, v or {}, ctx or {})
    if pillar == "I":
        return i_view(v or {}, page, ctx or {}, verdict)
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--layers", default="", help="bank only these layers (comma list) - the rest wait for a re-walk")
    ap.add_argument("--hold", default="", help="row ids to leave untouched (comma list) - a reading still being checked")
    a = ap.parse_args()
    recs = json.load(io.open(f".tmp/w4_steps/{a.batch}.records.json", encoding="utf-8"))
    steps_all = json.load(io.open(f".tmp/w4_steps/{a.batch}.json", encoding="utf-8"))
    import prove_w4_layer_trail as tr
    reg_rows = {t["id"]: t for t in _rio.load_doc()["trajectories"]}
    today = time.strftime("%Y-%m-%d")
    decided = []
    held_by_pillar = []
    for cell in recs.get("cells") or []:
        key = cell["persona"] + ":" + cell["page"]
        page = cell["page"]
        steps = [s for s in steps_all if s.get("cell") == key]
        vps = {v["viewport"]: v for v in cell.get("vps") or []}
        hive_id = None
        cast = cell.get("cast")
        if cast:
            r = psql("select m.hive_id from hive_members m where m.worker_name = '%s' and m.status = 'active' order by m.joined_at limit 1" % cast.replace("'", "''"))
            hive_id = r[0] if r else None
        ctx: dict = {}
        # every hive the cast is an active member of (a multi-hive cast reads several); none for a hive-less person
        ctx["castHives"] = set(psql("select m.hive_id from hive_members m where m.worker_name = '%s' and m.status = 'active'"
                                    % (cast or "").replace("'", "''"))) if cast else set()
        ctx["cast"] = cast or ""
        _uid = psql("select w.auth_uid from worker_profiles w where w.display_name = '%s' and w.auth_uid is not null limit 1"
                    % (cast or "").replace("'", "''")) if cast else []
        ctx["castUid"] = _uid[0] if _uid else ""
        layers = {r["layer"] for r in cell["rows"]}
        if "L" in layers:
            v0, w0 = tr.check_page(page)
            ctx["trailSrc"] = (v0, w0)
            # L offline/429 (the A pillar): does the page refuse a write it cannot send, or queue it with its author?
            _src = tr.ct.page_source(page) or ""
            _g = re.search(r"whRequireOnline|_whInvQueue|whOfflineQueue|offline-queue\.js|\.enqueue\(", _src)
            ctx["writeGuard"] = _g.group(0) if _g else None
            if hive_id:
                pg = psql("select count(*)||'|'||count(distinct actor)||'|'||coalesce((select actor||' / '||action||' / '||coalesce(target_type,'-')||' / '||to_char(created_at,'YYYY-MM-DD HH24:MI') from hive_audit_log where hive_id='%s' order by created_at desc limit 1),'') from hive_audit_log where hive_id='%s' and created_at > now() - interval '90 days'" % (hive_id, hive_id))
                n, actors, latest = (pg[0].split("|", 2) + ["", "", ""])[:3] if pg else ("0", "0", "")
                ctx["trailOk"] = int(n or 0) > 0 and bool(latest)
                ctx["trailPg"] = (f"postgres: {n} trail row(s) in this person's hive in 90 days, {actors} distinct actor(s), the newest "
                                  f"\"{latest}\" - readable later on audit-log.html by the hive's supervisor")
            else:
                ctx["noHive"] = True
                shown = (((vps.get("phone-390") or {}).get("healthy") or {}).get("url") or page)
                ctx["shownPage"] = shown
                ctx["trailSrcShown"] = tr.check_page(shown) if shown != page and (ROOT / shown).exists() else ctx["trailSrc"]
                pg = psql("select count(*)||'|'||coalesce(max(to_char(created_at,'YYYY-MM-DD')),'') from hive_audit_log where actor = '%s'" % (cast or "").replace("'", "''"))
                n, last = (pg[0].split("|") + ["", ""])[:2] if pg else ("0", "")
                ctx["trailOk"] = int(n or 0) > 0
                ctx["trailPg"] = (f"postgres: this person holds no hive, and {n} trail row(s) name them as the actor" + (f" (newest {last})" if last else
                                  " - a person with no hive leaves no readable trail of what they changed"))
        if "D" in layers and hive_id:
            v1 = vps.get("phone-390") or {}
            tbls = [r for r in healthy_reads(v1, page) if not r.startswith("fn:") and not r.startswith("rpc/")]
            for tb in tbls[:3]:
                cols = set(psql("select column_name from information_schema.columns where table_schema='public' and table_name='%s'" % tb))
                tcol = "updated_at" if "updated_at" in cols else ("created_at" if "created_at" in cols else None)
                if not tcol or "hive_id" not in cols:
                    continue
                who = "worker_name" if "worker_name" in cols else ("actor" if "actor" in cols else None)
                row = psql("select to_char(max(%s),'YYYY-MM-DD HH24:MI')%s from %s where hive_id='%s'" % (
                    tcol, (", (select %s from %s where hive_id='%s' order by %s desc limit 1)" % (who, tb, hive_id, tcol)) if who else "", tb, hive_id))
                if row and row[0].strip("|"):
                    ctx["dWitness"] = f"postgres: the newest write to {tb} in this hive is {row[0].replace('|', ' by ')}"
                    break
        if "CI" in layers:
            ctx["ciWitness"] = "the page is in the served roster every registered sweep walks (w4-layer-regression)"
        if "RL" in layers:
            # the postgres half: for each table the page read with a cap, how large the LARGEST hive's share is - a cap
            # this person never reaches can still be one another hive's reader meets every day
            caps: dict = {}
            for x in ((vps.get("phone-390") or {}).get("rl") or []):
                tb = str(x.get("t") or "")
                if (x.get("pg") == page and x.get("lim") and int(x["lim"]) > 1 and not x.get("single")
                        and tb not in RL_BOUNDED_BY_NATURE and re.fullmatch(r"[a-z0-9_]+", tb)):
                    caps[tb] = max(caps.get(tb, 0), int(x["lim"]))
            wit = []
            for tb, lim in list(caps.items())[:5]:
                cols = set(psql("select column_name from information_schema.columns where table_schema='public' and table_name='%s'" % tb))
                if "hive_id" in cols:
                    r = psql("select coalesce(max(c), 0) from (select count(*) c from public.%s group by hive_id) s" % tb)
                    wit.append((tb, lim, int(r[0]) if r and r[0].isdigit() else None))
            ctx["rlPg"] = wit
        for r in cell["rows"]:
            rid, layer = r["id"], r["layer"]
            if a.layers and layer not in a.layers.split(","):
                continue
            if rid in {x.strip() for x in a.hold.split(",") if x.strip()}:
                continue                                  # held back for a closer look - neither banked nor reddened
            pillar = (reg_rows.get(rid, {}).get("cx") or {}).get("pillar") or r.get("pillar")
            per = {}
            for vpn in ("phone-390", "desktop-1280"):
                per[vpn] = pillar_view(pillar, layer, judge(layer, cell["persona"], vps.get(vpn) or {}, page, ctx),
                                       vps.get(vpn) or {}, page, ctx)
            if any(x[0] == HOLD for x in per.values()):
                held_by_pillar.append((rid, layer, pillar, next(x[1] for x in per.values() if x[0] == HOLD)))
                continue                                  # no instrument reads this lens yet - neither banked nor reddened
            verdicts = {x[0] for x in per.values()}
            holds = verdicts <= {"ok", "n/a"} and len(per) == 2
            decided.append((rid, layer, cell, per, holds, steps))
    # ── write receipts + bank ──
    banked, red = [], []
    for rid, layer, cell, per, holds, steps in decided:
        reading = " | ".join(f"{vp}: {v[0]} - {v[1]}" for vp, v in per.items())
        _pl = (reg_rows.get(rid, {}).get("cx") or {}).get("pillar")
        head = f"CX {layer} read through {_pl} ({PILLAR_LENS.get(_pl, _pl)})" if _pl else f"LX-{layer}"
        note = (f"{head} on {cell['page']} walked {today} through the Playwright MCP (tools/lx_walk.js) as "
                f"{cell['cast']} ({cell.get('castRole')}) for the {cell['persona']} persona, through the wall and the row's route "
                f"({' -> '.join(cell.get('path') or [])}), each viewport a fresh context at a TRUE size. {reading}")
        if not a.apply:
            print(f"  {'HOLDS ' if holds else 'OPEN  '} {rid:8} {layer:3} {cell['page'][:26]:26} {cell['persona'][:14]:14} {reading[:230]}")
            continue
        sp = Path(tempfile.gettempdir()) / f"lx_steps_{rid}.json"
        io.open(sp, "w", encoding="utf-8", newline="\n").write(json.dumps(steps, ensure_ascii=False))
        cmd = [sys.executable, "tools/record_mcp_walk.py", "--id", rid, "--instrument", INSTRUMENT[layer],
               "--layer", layer, "--as-persona", cell["persona"], "--viewports", "phone-390,desktop-1280",
               "--cast", cell.get("cast") or "", "--steps", str(sp), "--note", note[:1800], "--witness", reading[:1800]]
        if not holds:
            cmd += ["--unproven", ("the " + layer + " ask does not hold: " + "; ".join(f"{vp} {v[0]}: {v[1]}" for vp, v in per.items() if v[0] not in ("ok", "n/a")))[:600]]
        rr = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (rr.stdout or "") + (rr.stderr or "")
        if rr.returncode != 0 or "refused" in out.lower():
            print(f"  {rid}: the recorder REFUSED the receipt - {out.strip()[-200:]}")
            continue
        # ★THE RECEIPT IS THE VERDICT (2026-10-12). record_mcp_walk.py also judges the walk's STEPS (every hop rendered,
        # identity kept on every hop) and writes ok:false when they fail - while this file judged only the layer and
        # banked anyway. Six skillmatrix rows became `locking` with RED receipts, which the ledger counts as open: two
        # files disagreeing about one walk. A row is banked only when the receipt the recorder wrote says ok.
        if holds:
            try:
                rec = json.loads((ROOT / ".tmp" / "mcp_walks" / f"{rid}.json").read_text(encoding="utf-8"))["results"][0]
                if not rec.get("ok"):
                    holds = False
                    reading += " | the walk itself did not hold: " + "; ".join(rec.get("problems") or [])[:300]
            except Exception as e:
                holds = False
                reading += f" | the receipt could not be read back ({e})"
        (banked if holds else red).append((rid, layer, cell, per, note, reading))
    if held_by_pillar:
        print(f"  held {len(held_by_pillar)} row(s) whose lens no instrument reads yet: "
              + ", ".join(sorted({f'{p}' + (f'/{ly}' if p != 'I' else '') for _, ly, p, _w in held_by_pillar})))
    if not a.apply:
        print("\n(dry run - pass --apply to record receipts and bank)")
        return 0
    reg = _rio.load_doc()
    byid = {t["id"]: t for t in reg["trajectories"]}
    for rid, layer, cell, per, note, reading in banked:
        t = byid[rid]
        prev = t.get("basis") or ""
        basis = (f"[{today}] pct -> 60. WALKED LIVE {today} via {INSTRUMENT[layer]} (tools/lx_walk.js, the Playwright MCP's "
                 f"own browser; no model call - every model function answered by a stub; nothing sent; every write the page "
                 f"attempted held): {note} Receipt .tmp/mcp_walks/{rid}.json.")
        t["basis"] = basis + ((" || " + prev) if prev else "")
        if prev and re.search(r"pct\s*(?:\d+\s*)?->\s*\d+", prev):
            t["basis"] += f" || [{today}] pct -> 60: walked and banked - the first segment says how"
        t["status"] = "locking" if t.get("status") not in ("locked",) else t["status"]
        t["pct"] = max(int(t.get("pct") or 0), 60) if t["status"] != "locked" else 100
        arts = t.setdefault("artifacts", {})
        arts["gates"] = sorted(set(arts.get("gates") or []) | set(GATES[layer]))
    for rid, layer, cell, per, note, reading in red:
        t = byid[rid]
        prev = t.get("basis") or ""
        if t.get("status") in ("locking", "locked"):
            continue                                    # never demote a banked row from a batch; say so instead
        finding = (f"[{today}] pct -> 25. WALKED LIVE {today} via {INSTRUMENT[layer]} (tools/lx_walk.js) - the {layer} ask "
                   f"does NOT hold yet, so the row stays open: {note} Receipt .tmp/mcp_walks/{rid}.json (red).")
        t["basis"] = finding + ((" || " + prev) if prev else "")
        if prev and re.search(r"pct\s*(?:\d+\s*)?->\s*\d+", prev):
            t["basis"] += f" || [{today}] pct -> 25: walked, the first segment says what it found"
        t["status"], t["pct"] = "walked", 25
    # through the union, at the file's own indent: this wrote indent=1 over a file kept at 2 (the 2-million-line-diff
    # class advance_trajectory records), and it wrote the main file only, so a cube row never reached its shard
    with io.open("trajectory_registry.json", encoding="utf-8") as fh:
        fh.readline()
        second = fh.readline()
    _rio.save_doc(reg, indent=max(1, len(second) - len(second.lstrip(" "))) if second.strip() else 2)
    print(f"banked {len(banked)} row(s), {len(red)} row(s) walked and left open with a red receipt")
    for rid, layer, cell, per, note, reading in red:
        print(f"  OPEN {rid:8} {layer:3} {cell['page'][:26]:26} {cell['persona'][:14]:14} {reading[:220]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
