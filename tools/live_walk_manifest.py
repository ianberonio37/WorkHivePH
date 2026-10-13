#!/usr/bin/env python3
"""live_walk_manifest — which trajectories have been WALKED LIVE, and which have not (2026-09-06).

Ian: *"live deepwalk each trajectory or group of categories, but do not repeat what you already
done"* — and, for the header, *"two buckets on live evidence"*.

The registry already says the program is 99% GATED. That is true and it is not the same claim as
"we walked it". Reading each row's own `basis` for the KIND of evidence it holds separates them:

  live    the basis names an instrument that RAN against the running system - a tools/prove_* or
          probe_* run, a psql recipe, a live edge-function invoke, a CLS attribution, a screenshot,
          a two-context session, an MCP walk
  board   the basis inherits a page's family-board score ("this row's page scored 100%") - the PAGE
          was walked, this row's LENS was not
  gate    the basis cites registered gates / a gate suite passing - static, no runtime walk
  prose   a written argument (architecture, "hardened by construction") with no instrument named
  none    empty basis

CLOSED = live AND gated (locked/locking). OPEN = everything else. That is the two-bucket number the
roadmap header carries, counted - never an average of progress points, which is what made 94.5%
read as "nearly done" while 840 rows had never been exercised.

This file is also the NO-REPEAT ledger: a walk reads the manifest and skips every row already
classified `live`, so no surface is walked twice for the same lens.

  python tools/live_walk_manifest.py              # write live_walk_manifest.json + print the buckets
  python tools/live_walk_manifest.py --check      # exit 1 if the committed manifest is stale (gate)
  python tools/live_walk_manifest.py --family "render & CSS"     # the walk queue for one family
  python tools/live_walk_manifest.py --open --limit 40           # what is still owed
"""
from __future__ import annotations
import io
import glob
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
CRITIC = ROOT / "critic_registry.json"
OUT = ROOT / "live_walk_manifest.json"

# ★THE RETRACTION WAS ENFORCED IN ONE BANKER AND NEVER IN THE LEDGER, AND 916 ROWS READ CLOSED BECAUSE OF IT
# (measured 2026-10-05). On 2026-09-15 Ian retracted every row banked on a Playwright-LIBRARY prover - "I
# thought we are using relevant live MCPs?" - and bank_w4_passers.py enforces that when CREATING a basis. But
# THIS file decides whether a basis counts, and its `playwright` marker tuple accepts the bare prefix
# "prove_", so any library prover's name satisfied the instrument test. Measured: 916 closed rows name a
# retracted prover, and for every single one it is the NEWEST evidence segment - none had been superseded by a
# real walk. prove_full_journeys 325 · prove_w4_actions 431 · prove_w4_navhub 90 · prove_w4_confusions 70.
# So the headline read 8,909 closed (75.7%) while 916 of those rested on evidence Ian had withdrawn.
#
# ★THE LIST LIVES HERE, ONCE, AND THE BANKER IMPORTS IT. Two hand-kept copies of a retraction list is how the
# two layers drift apart again - which is the shape that produced this very defect
# ([[feedback_two_stale_lists_agreeing_is_not_a_check]]). A row whose NEWEST evidence names one of these is
# returned to the re-walk queue: the walk may still have found real defects, and its receipt is kept, but it
# does not CLOSE a row reserved for an MCP walk. Only the newest segment is read, so a row genuinely re-walked
# through the MCP since keeps its green even though the retracted run remains in its history.
RETRACTED_INSTRUMENTS = (
    "tools/prove_w4_actions.mjs",
    "tools/prove_w4_navhub.mjs",
    "tools/prove_w4_confusions.mjs",
    "tools/prove_w4_layer_ca.mjs",
    "tools/prove_full_journeys.mjs",
)


def _newest_segment(basis: str) -> str:
    """The live claim. Every banker in this repo PREPENDS and keeps the old text after ' || ', so the first
    segment is what the row asserts today and the rest is history. Reading the whole string would let a
    retracted run in a row's past sink a row that has since been walked properly."""
    return (basis or "").split(" || ")[0]


_COVER_LIST = re.compile(r"exercised by \d+ registered gate/test file\(s\):[^·|]*")


def _rests_on_retracted(basis: str) -> str:
    """The retracted instrument a row's CURRENT claim rests on, or ''.

    ★A FILE NAMED IN A LIST OF WHAT COVERS A PAGE IS NOT THE INSTRUMENT OF THE CLAIM (2026-10-13, W31451). The
    lifecycle prover writes "exercised by 10 registered gate/test file(s): run_platform_checks.py,
    tools/prove_full_journeys.mjs, ..." - the gates that run the page - and its claim is made VIA
    tools/prove_lifecycle_cells.mjs, which is not retracted. Matching the retracted name anywhere held exactly one
    row open on a mention (measured: 1 row of 13,360, its 13 siblings closed on the same prover). Only that list is
    set aside; every other mention, in any phrasing, still counts - the front-segment protection stands."""
    first = _COVER_LIST.sub("", _newest_segment(basis))
    for inst in RETRACTED_INSTRUMENTS:
        if inst in first:
            return inst
    return ""


# ── evidence kinds, in precedence order: the FIRST match wins ────────────────────────────────────
LIVE_RE = re.compile(
    r"(tools/(prove|probe)_[\w.]+|playwright|cls_attribution|phone[_-]?fit|deepwalk|screenshot|"
    r"two-context|live-?MCP|MCP walk|psql_probes/|docker exec[^\n]{0,40}psql|functions\.invoke|"
    r"live invoke|LIVE-VERIFIED|WALKED LIVE|measured live|live probe|browser walk|"
    # ★THIS PROJECT'S OWN IDIOM FOR A HAND-WALK IS EVIDENCE (added 2026-09-06). Bases written as "walked 390 as
    # bryangarcia through the REAL 3-step wizard" or "walked 2026-08-25: paste ergonomics MEASURED good" report a
    # real session with a measured outcome, and 100+ rows were being counted as PROSE for lacking a tool name.
    # The qualifier is deliberate - walked followed by a viewport, a date, or a persona - so that "WALKED via
    # registered gates", which LIVE_RE would otherwise swallow before GATE_RE ever sees it, stays a gate.
    r"walked\s+(?:live\s+)?(?:\d{3,4}\b|\d{4}-\d{2}-\d{2}|as\s+\w))", re.I)
BOARD_RE = re.compile(r"(family_rubric_sweep|this row's page scored|FULL board[^\n]{0,60}scored)", re.I)
GATE_RE = re.compile(r"(WALKED via registered gates|via the registered gate|Covered by [^\n]{0,40}gate suite|"
                     r"\bvalidate_[\w]+\.py\b|static gate|by construction)", re.I)

# ── lens -> family. The lens is the part of a title before " - <surface>" ────────────────────────
FAMILIES = OrderedDict([
    ("render & CSS", r"(render resolves|CSS contract|contrast from CSSOM|escHtml|typography|"
                     r"layout shift|paint|font|z-index|overflow)"),
    ("degradation & state", r"(compound failure|degradation is legible|empty vs failed|fourth state|"
                            r"offline path|systemic ripple|stale|retry|timeout|fallback state)"),
    ("edge & API contracts", r"(provider fallback|rate-limit|refusal & error shape|grounding|"
                             r"idempot|webhook|contract|payload|schema)"),
    ("data honesty", r"(cap is not a total|window & label agree|honest interpretability|tile ==|"
                     r"canonical|KPI|number|count|ledger|truth)"),
    ("journeys", r"(hand-off carries context|the return path|chain|journey|deep link|hand-off)"),
    ("mobile deep", r"(tap targets|safe area|landscape & tablet|PWA install|touch|phone fit|viewport)"),
    ("a11y deep", r"(keyboard path|semantics & landmarks|announcement reaches|focus|screen reader|"
                  r"aria|contrast ratio|WCAG)"),
    ("ops & observability", r"(health is a living producer|the gate actually runs|cron|log|"
                            r"observab|incident|alerting|availability)"),
    ("public funnels", r"(Learn arrival|Tools arrival|arrival|SEO|canonical URL|crawler|sitemap|"
                       r"_headers is prod-only|CDN|cache header)"),
    ("realtime", r"(listener lifecycle|realtime|subscription|presence|broadcast|channel)"),
    ("security & tenancy", r"(BOLA|BFLA|JWT|RLS|tenant|cross-hive|escalat|injection|secret|bypass)"),
])
FAMILY_RES = [(name, re.compile(pat, re.I)) for name, pat in FAMILIES.items()]
OTHER = "other"

# ── §LW.1 THE MCP DOCTRINE, MECHANISED (Ian, 2026-09-06: "use appropriately the MCPs depending on the KIND of
# trajectory... if other MCPs are needed we don't have, proactively connect them"). Each lens kind names the
# instrument that can actually answer it. A row whose basis does not name that instrument is queued for an MCP
# re-walk - including rows already banked `live` by a library sweep, when their lens is journey-shaped or needs an
# outside witness. A kind whose server we do not have is marked MISSING, which is a queue item, never an excuse.
MCP_FOR_KIND = [
    # ★WAVE 4 FIRST OF ALL (2026-09-14) - its lenses say what they are. A "Lived start to end" action story
    # is a journey walked with both eyes (the browser for each step's transition, postgres for what the step
    # wrote); the whole nav-hub is a browser walk on its host page; a "lived start to end" LAYER story is
    # answered by the instrument that can PROVOKE that layer - S by PostgREST as the person herself, H by the
    # served headers, L by the trail in postgres, every other layer by the browser with the effect checked
    # from outside. Matched before every older rule because these lenses reuse wave 3's own sentences
    # ("The platform must ...") and would otherwise route by a word inside the surface's name.
    # ★THE DESIGN LENSES (2026-09-15, Ian: "your own designing skills are all slop") - a skill playbook applied
    # live through the browser MCPs at phone-390 AND desktop-1280; the figma lens also needs the Figma MCP (the
    # page's design source). Matched before every other rule; _w4_missing holds each row to its lens's evidence.
    ("playwright-mcp + figma-mcp", r"^Design lens figma:"),
    # the audit lens scores five dimensions 0-4, and three of them (performance, a11y focus order, responsive
    # under throttling) are only measurable in a TRACE - so it names both browsers and closes under neither alone
    ("playwright-mcp + chrome-devtools-mcp", r"^Design lens audit:"),
    ("playwright-mcp", r"^Design lens "),
    ("playwright-mcp + postgres-mcp", r"^Lived start to end:"),
    ("playwright-mcp", r"^The whole nav-hub, every control"),
    ("invoke + PostgREST as the caller (never the owner connection)",
     r"^The platform must refuse, on this page, a person who is not entitled.*lived start to end"),
    ("raw-http", r"^The platform must serve this page correctly from the edge.*lived start to end"),
    ("postgres-mcp", r"^The platform must record who did what on this page.*lived start to end"),
    ("playwright-mcp + postgres-mcp", r", lived start to end - "),
    # ★WAVE 3 FIRST, ON THE LENS'S OWN WORDS (2026-09-07). Its rows name surfaces and topics that every rule
    # below would grab by keyword - a journey through report-sender says "e-mail", a function contract says
    # "refuse", a shared-component row says "cache" - and each of those would route a question to an instrument
    # that cannot answer it. So the wave's own phrasings are matched first, exactly as the EX-TL language rule
    # had to be lifted above the surface-name rules for the same reason.
    #   · a JOURNEY needs both eyes: the browser for each step's transition, postgres for what the step wrote
    #   · a FUNCTION CONTRACT is answered by calling it as the caller, never by reading the owner's tables
    #   · a SHARED COMPONENT is answered on three host pages, not on one
    ("playwright-mcp + postgres-mcp",
     r"whole story end to end|the whole story|Onboard to first value|Breakdown to close-out|The PM month|"
     r"The AI-assisted day|The supervisor's week|Two hives, one person|Safety incident|One spare part|"
     r"The brief arrives|Sensor to work order|Predicted risk re-plans|One machine's whole life|Energy audit|"
     r"An engineering project|Typhoon season|Audit season|The founder's month-end|Benchmark to decision|"
     r"Shortage to shelf|Hire a specialist|A deal goes wrong|Money in, money spent|The knowledge loop|"
     r"The portable portfolio|The machine client|The vehicle owner's month|The same day, degraded|Leaving:|"
     r"Alone, then not|Stranger to member|New hire to trusted hand|Locked out and back to work|"
     r"One hive's whole year|One worker's career|One machine's lifetime|One part's lifecycle|"
     r"One listing's lifecycle|One project's lifecycle|One vehicle's year"),
    ("invoke + PostgREST as the caller (never the owner connection)",
     r"must refuse this function|must degrade legibly when this function|must complete this function's"),
    ("playwright-mcp (three host pages: phone, desktop, wall display)",
     r"This shared piece"),
    # …and the rest of wave 3's lenses, for the SAME reason and by the SAME test as the EX-TL rule: the
    # question decides the instrument, never a word inside the surface's name. Measured on the seeded rows:
    # "INP" matched inside "input" (60 calculator rows -> chrome-devtools), "inbox" inside a learn slug
    # (3 -> mail-catcher), "observab" inside two page names (5 -> grafana), "arrival" inside a lens about
    # what a person sees before signing in (7 -> raw-http), "truth" inside a sentence about a model being
    # wrong (2 -> postgres alone). Every one of those is answered by reading the screen.
    ("playwright-mcp + postgres-mcp",
     r"The tool this article sends you to opens|must reproduce this calculator's reference answer|"
     r"where this page's data came from|must record who did what on this page|must state which clock|"
     r"must be able to show where"),
    ("playwright-mcp",
     r"reads on a phone, survives being opened offline|Every claim here is sourced and dated|"
     r"let this calculation be done on a phone|must name the standard and clause|"
     r"first time on this page and nobody is beside you|back after weeks and this page|"
     r"shared tablet at 768|worth the visit before you sign in|pasted link with no history|"
     r"on a wall or a printout and must still be true|refused the microphone or the camera|"
     r"still a page, and still says which period|Twenty alerts in an hour|"
     r"release lands while this page is open|must render this page's contract|"
     r"must speak, on this page, the words|must keep this page truthful when the model|"
     r"must keep this page responsive as its data grows|must catch this page's regressions|"
     r"nothing to show yet it says why|nothing to send yet it says why"),
    ("postgres-mcp",
     r"must keep a person's two hives apart|must not let two tabs|must let a person take their record|"
     r"must refuse, on this page, a person who is not entitled|must keep this page's identity honest|"
     r"must not promise an answer grounded|genuinely revoked member|"
     r"must bound what this page can consume"),
    ("raw-http fetch (the deployed origin's response headers)",
     r"must serve this page correctly from the edge"),
    # the on-screen lens phrasings of the PF / PX / SB / AX waves (2026-09-07): a topic word in the SURFACE name
    # ("observability") must not route a question about what a person SEES on the page to grafana or mail-catcher -
    # eighteen locked rows on the two observability pages read "needs re-walk" for that reason
    ("playwright-mcp", r"first time and can tell in one glance|says what it will do before you press|how fresh what you are seeing|fails to load its data|traced to the rows|phone with one thumb|moves under your finger|keyboard-only person|leads somewhere|survives a refresh|does not have permission|words a Philippine|Two people on this page|printed or shown on a wall|quota is gone and this page|arriving by deep-link|opened cold|coming back to this page|session ends while|screen reader user|200% zoom|colour-blind|shift change|graveyard|month-end"),
    # ★A LANGUAGE QUESTION IS A BROWSER QUESTION WHEREVER THE PAGE SITS (2026-09-07). Eight EX-TL rows on the
    # two observability pages were routed to the grafana MCP because their SURFACE says "observability" -
    # the same topic-not-question error as "SLO" inside "slower". "Does this page read in Tagalog" is answered
    # by reading the screen, so the language lens is matched first, on the lens's own words.
    # The same class again for EX-AT: "the AI on this page gives you a confident wrong answer and you have a way to
    # flag it" is answered on the screen of the two observability pages too - eight rows sat OPEN on the surface name.
    # …and EX-RV: "after pressing X by mistake, the platform must offer the way back" quotes the control's own
    # words, and three of those words were "email" - which routed a recovery question to the mail-catcher.
    ("playwright-mcp",                r"Tagalog|Filipino|wh_lang|bilingual|in their language|"
                                      r"confident wrong answer|what it answered FROM|record your disagreement|out of quota and it says so|"
                                      r"must offer the way back|by mistake"),
    ("playwright-mcp + postgres-mcp", "journey|hand-off|the return path|chain|completes|clears the|arrives|converts|"
                                      r"walks|end-to-end|two-sided|lifecycle|onboard|sign-?up|invite|approval queue"),
    ("postgres-mcp",                  "tenant|RLS|BOLA|BFLA|cross-hive|canonical|tile ==|ledger|truth|cap is not a total|"
                                      "row count|integrity|orphan|constraint"),
    ("sentry-mcp",                    "crash|unhandled|exception|error tracking|stack trace|stacktrace|stack frame|regression signal"),   # 2026-09-07: a bare "stack" routed "promo STACKING abuse" (a hostile buyer, PostgREST's lens) to Sentry
    # ★A REFUSAL IS NOT AN OBSERVABILITY QUESTION (2026-09-07). Three rate-limiting rows - "you are
    # refused and not told when you may come back", "someone else in your hive spent the limit", "your
    # retry makes it worse" - were routed to the grafana MCP, which watches dashboards and can see that a
    # limit fired but never what the person was TOLD. That answer lives in the response: the status code,
    # the Retry-After header and the sentence in the body. Placed above grafana so it wins the match.
    ("raw-http burst (the refusal itself: status, Retry-After, and the sentence it carries)",
     # AND THE FIRST VERSION OF THIS RULE WAS FAR TOO GREEDY. Matching any "quota|throttl|refused|rate
     # limit" swept in 71 rows and dropped the headline from 95.9% to 91.8% in a single edit - because
     # most of those rows ask what the PAGE SHOWS when you are out of quota, which is a browser question
     # and was already walked correctly. Only the rows about what the SERVER RETURNS belong here, so the
     # pattern names those three questions rather than the topic they all share.
     r"when you may come back|spent the limit and you are|retry makes it worse|Retry-After"),
    # ★"SLO" MATCHED INSIDE "SLOWER" (2026-09-07). Fifteen scaling rows - "as the hive grows past twenty
    # people, this page gets slower and never says so" - were assigned the grafana MCP and sat open after
    # being walked, because an unanchored three-letter token matched the middle of an ordinary English
    # word. Every short acronym in this map needs a boundary; the long phrases do not.
    ("grafana-mcp",                   r"health is a living producer|cron|liveness|observab|log correlation|\bSLO\b|uptime|incident"),
    # ★THE SLO-INSIDE-SLOWER LESSON, AGAIN, ON THE OTHER SIDE OF THE MAP (2026-09-07): "INP" matched inside
    # "input" and sent sixty calculator rows about naming a standard to the performance profiler. Every short
    # acronym here is anchored now, for the same reason the grafana rule anchors \bSLO\b.
    ("chrome-devtools-mcp",           r"\bCWV\b|\bLCP\b|\bCLS\b|\bINP\b|\bTTFB\b|performance|bundle|cache|payload size|waterfall|cold start"),
    ("raw-http fetch (no JS - what a crawler receives)",                  "Learn arrival|Tools arrival|arrival|SEO|crawler|citation|sitemap|canonical URL"),
    ("mail-catcher (the product's OUTBOX, not the owner's inbox)",               "email|inbox|deliver|bounce|notification reaches"),
    ("axe-mcp (MISSING - connect)",   "keyboard path|semantics & landmarks|announcement reaches|screen reader|WCAG|aria"),
    ("raw-http fetch (the deployed origin's response headers)", "_headers is prod-only|CDN|cache header|redirect|robots"),
]
# a PERSONA ARC is a journey whoever wrote its title: "Worker logs a repair one-handed", "Supervisor's morning
# triage", "Anon lands on a calculator". These are the 500-odd one-of-a-kind rows the keyword list above missed,
# and they are exactly the shape the playwright MCP exists for - each step's snapshot decides the next.
PERSONA_RE = re.compile(r"^(worker|supervisor|anon|buyer|seller|contractor|owner|visitor|new user|returning user|"
                        r"admin|founder|technician|planner|manager|guest|member)\b", re.I)
MCP_RES = [(m, re.compile(p, re.I)) for m, p in MCP_FOR_KIND]
LIBRARY_OK = re.compile(r"render resolves|CSS contract|contrast from CSSOM|escHtml|compound failure|degradation is legible|"
                        r"empty vs failed|fourth state|offline path|tap targets|safe area|landscape|PWA install|"
                        r"refusal & error shape|provider fallback|rate-limit|contract & failure modes|window & label agree|"
                        r"honest interpretability|listener lifecycle|"
                        # the P-M phone-fit lenses, walked by tools/prove_phone_fit.mjs at 390 and 360
                        r"labels stay on one line|text stays in its card|menus stay in the viewport|no horizontal overflow|"
                        # page-shaped platform lenses a batch sweep answers better than a per-step walk
                        r"systemic ripple|repaint keeps focus|reconnect & backfill|SW staleness|grounding containment", re.I)
# lenses whose evidence lives in the DATABASE or in the OPS stack, whatever their wording
DB_LENS = re.compile(r"write-authz depth|a claim a query enforces|read-authz|ledger|integrity", re.I)
OPS_LENS = re.compile(r"the gate actually runs|the log is greppable|greppable|runbook|alert routing", re.I)
# a SWEEP arc asserts one behaviour ACROSS many surfaces ("...on every committing surface", "...everywhere",
# "Browser Back through every modal"). One command over the roster answers it; a per-step MCP walk would ask the
# same question forty times.
SWEEP_RE = re.compile(r"\b(every|everywhere|all surfaces|across all|sweep|storm|platform-wide)\b", re.I)


def _mcp_for(lens: str, title: str) -> str:
    hay = f"{lens} {title}"
    # an ARROW in the title is a chain: "Low-stock -> inventory -> marketplace procurement", "Resume: upload ->
    # extract -> review -> export". A multi-step chain is a journey however its author phrased it.
    if PERSONA_RE.match(lens.strip()) or ("→" in hay) or ("->" in hay):
        return "playwright-mcp + postgres-mcp"
    for m, rx in MCP_RES:
        if rx.search(hay):
            return m
    if DB_LENS.search(hay):
        return "postgres-mcp"
    if OPS_LENS.search(hay):
        return "grafana-mcp"
    if LIBRARY_OK.search(hay) or SWEEP_RE.search(hay):
        return "library sweep (batch lens - the MCP would be 400 calls for one answer)"
    # THE DEFAULT IS A WALK. An arc nobody classified is a behaviour nobody has watched, and the honest instrument
    # for that is a person-shaped walk with the state checked from outside - never "no instrument, leave it".
    return "playwright-mcp + postgres-mcp"


def _kind(basis: str) -> str:
    b = (basis or "").strip()
    if not b:
        return "none"
    if LIVE_RE.search(b):
        return "live"
    if BOARD_RE.search(b):
        return "board"
    if GATE_RE.search(b):
        return "gate"
    return "prose"


def _lens(title: str) -> str:
    return (title or "").split(" - ")[0].strip()


def _family(lens: str, title: str) -> str:
    hay = f"{lens} {title}"
    for name, rx in FAMILY_RES:
        if rx.search(hay):
            return name
    return OTHER


def _surface(row: dict) -> str:
    pages = row.get("pages") or []
    fns = row.get("functions") or []
    if pages:
        return pages[0]
    if fns:
        return "fn:" + str(fns[0])
    return "(cross-cutting)"


def _red_receipt_ids() -> set:
    """Ids whose NEWEST journey receipt says the story did not hold.

    Newest wins because a row is often walked more than once - a red receipt from before a fix and a
    green one after. Taking the newest is what makes "fix it and re-walk" the way to clear a row;
    any other choice would either freeze a stale red or let a stale green vouch for a broken walk.
    A missing or unreadable receipt yields nothing: this set is only ever a source of CONTRADICTION,
    never of proof, so .tmp/ being disposable can lower the count but can never invent one.
    """
    best: dict = {}
    # ★AND THE MCP NAMESPACE, BECAUSE THE DOCTRINE WALKS WITH THE MCP (Ian, 2026-09-10: "we should always
    # use MCPs for walks"; SS-LW.1 rule 4 - batch with the library, WALK with the MCP). This read exactly
    # one namespace, the one prove_full_journeys.mjs writes, so a journey walked correctly BY HAND through
    # the MCP could never be banked and, worse, a row whose scripted receipt was red stayed red no matter
    # how carefully it was re-walked. Both namespaces now feed the same newest-wins rule, so an MCP
    # re-walk supersedes an older scripted receipt exactly as a scripted re-walk supersedes an older one.
    # tools/record_mcp_walk.py writes the MCP side and stamps each receipt with its `instrument`, so a
    # reader can always tell a walk a person drove from a walk a script drove.
    sources = (sorted(glob.glob(str(ROOT / ".tmp" / "full_journeys_*.json")))
               + sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "*.json"))))
    for path in sources:
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
            mtime = os.path.getmtime(path)
        except Exception:
            continue
        # ★A STRAY FILE IN THE RECEIPTS DIRECTORY KILLED THE WHOLE LEDGER (2026-09-30). This walks
        # every file in .tmp/mcp_walks and assumed each one is a receipt OBJECT; a bare JSON array
        # parked there (a steps file, written by a prover that picked the wrong directory) made this
        # line raise AttributeError and took down every importer of this module - the manifest, the
        # gate, and record_mcp_walk's own self-test. A ledger must skip what it cannot read, not die
        # on it: the directory is shared, so its contents are input, not a contract.
        if not isinstance(doc, dict):
            continue
        for res in (doc.get("results") or []):
            rid = res.get("id")
            if rid and (rid not in best or mtime >= best[rid][1]):
                best[rid] = (res, mtime)
    return {rid for rid, (res, _m) in best.items()
            if not res.get("ok") or res.get("unbuilt")}


_RED_RECEIPTS = _red_receipt_ids()


def _w4_receipts() -> dict:
    """id -> the NEWEST MCP receipt result for a wave-4 row (its `w4` block carries axis, effect, layer,
    hub_controls, fixture_provenance; every step carries `fit`, the overlap/occlusion record)."""
    best: dict = {}
    # BOTH W4 receipt namespaces: mcp_walks/<id>.json (the layer provers + hand MCP walks) AND the nav-hub
    # ratchet's full_journeys_w4navhub_*.json (tools/prove_w4_navhub.mjs writes there, per its docstring). Without
    # the second glob every nav-hub row read "no MCP receipt" and could never close, however clean its walk
    # (2026-09-14). _w4_missing still gates each row (>=4 pages + fit), so widening the read cannot over-count.
    # ★AND A THIRD NAMESPACE: THE LXP WAVE WRITES LXP<id>.json, WHICH THIS GLOB COULD NEVER MATCH (2026-10-05).
    # Exactly the failure the note above records for nav-hub, one wave later. record_mcp_walk.py writes an MCP
    # walk to `.tmp/mcp_walks/<id>.json`, so an LXP row's receipt is `LXP195.json` - and `W4*.json` does not
    # match it. Found by walking LXP195 by hand through the chrome-devtools MCP at a true 390 and a true 1280:
    # the recorder accepted the receipt (ok=True, 9/9 steps, after refusing it twice - once for not naming the
    # layer, once for carrying a placeholder character count) and the ledger still reported no receipt at all.
    # So the whole LXP browser tier - 2,206 rows - was unbankable by the ONLY instrument permitted to bank it:
    # the library provers are retracted, and the hand MCP walk was invisible. A want must carry the marker AND
    # the namespace that recognises it. _w4_missing still gates each row, so widening the read cannot over-count.
    globs = (sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "W4*.json")))
             + sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "LXP*.json")))
             # ...and the two waves seeded 2026-10-06 write LXC<id>.json and LM<id>.json - the same lesson a
             # third time: a namespace the glob cannot see is a wave nothing can close
             + sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "LXC*.json")))
             + sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "LM*.json")))
             # ...and the bug waves: BRP (2026-10-04) and BRH (2026-10-14) write BRP<id>.json / BRH<id>.json
             + sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "BRP*.json")))
             + sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "BRH*.json")))
             + sorted(glob.glob(str(ROOT / ".tmp" / "full_journeys_w4navhub_*.json"))))
    for path in globs:
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
            mtime = os.path.getmtime(path)
        except Exception:
            continue
        for res in (doc.get("results") or []):
            rid = res.get("id")
            if rid and (rid not in best or mtime >= best[rid][1]):
                best[rid] = (res, mtime)
    return {rid: res for rid, (res, _m) in best.items()}


def _w4_missing(row: dict, receipts: dict) -> str:
    """Why a wave-4 row's evidence is incomplete ('' when it is complete).

    ★THE VOCABULARY OF WAVE 4 (2026-09-14): a journey banked from ONE page, without a persisted-effect receipt
    on a writing step, without its axis's width and language, without the layer it claims provoked, or without
    the per-step overlap record stays OPEN - however green its walk reads. These are the four things Ian asked
    for by name (start to end; the effect to its terminus; the three axes; the overlap/occlusion record at
    every step), so a receipt that lacks one has not answered the row, and the ledger says so per row.
    """
    w4 = row.get("w4") or {}
    if not w4:
        return ""
    res = receipts.get(row["id"])
    if not res:
        return "no MCP receipt"
    steps = res.get("steps") or []
    got = res.get("w4") or {}
    ax = row.get("axis") or {}
    want_axis = f"{ax.get('device')} {ax.get('language')}"
    problems = []
    kind = w4.get("kind")
    # a design-lens row is ONE page studied at two viewports (arrival + the page at 390 and at 1280); the four-page
    # rule is the journey rule and does not describe its evidence - the design branch below holds it to both viewports
    if kind == "design":
        if len({s.get("page") for s in steps}) < 2:
            problems.append("no arrival step before the page")
    elif len({s.get("page") for s in steps}) < 4:
        problems.append("fewer than 4 pages walked")
    if got.get("axis") != want_axis:
        problems.append(f"axis {got.get('axis')!r} != {want_axis!r}")
    layer = w4.get("layer")
    # ★THE EVIDENCE IS SHAPED BY THE LAYER (2026-09-14). Not every W4 story is a browser walk: the overlap/
    # occlusion record is the right witness for what a person SEES (Frontend F, the language/copy CA, an
    # action's render, the nav-hub chrome) - but a contract layer answers with a non-browser instrument that
    # produces no `fit`. S/AU are proven by a refusal received AS the person through PostgREST (never the
    # owner connection); L by the trail in postgres; D by the provenance the write left; H by the served
    # headers; A/AV/C/CI/LB/RL by the degraded/limit/release behaviour. So a browser-shaped row still needs
    # `fit` on every step, and a contract-layer row needs a named `witness` instead - requiring `fit` of it
    # would refuse honest evidence the way asking a poster for a status region does.
    browser_shaped = kind in ("action", "nav-hub", "confusion", "design") or (kind == "layer" and layer in ("F", "CA"))
    if browser_shaped:
        if not steps or not all(isinstance(s.get("fit"), dict) for s in steps):
            problems.append("a step has no overlap/occlusion record")
    else:
        if not got.get("witness"):
            problems.append(f"no witness for the {layer} contract layer "
                            "(a refusal / trail / provenance / headers / limit receipt, not a browser fit)")
    if kind == "action" and (w4.get("action") or {}).get("kind") in ("write", "upload", "edge") \
            and not got.get("effect"):
        problems.append("no persisted-effect receipt for a writing step")
    if kind == "layer" and got.get("layer") != w4.get("layer"):
        problems.append(f"layer provoked {got.get('layer')!r} != {w4.get('layer')!r}")
    if kind == "nav-hub" and int(got.get("hub_controls") or 0) < 11:
        problems.append("fewer than the 11 nav-hub control groups exercised")
    if w4.get("fixture") and not got.get("fixture_provenance"):
        problems.append("no provenance for the real file")
    # ★A DESIGN-LENS ROW CLOSES ON ITS LENS'S OWN EVIDENCE (2026-09-15): the lens named, both viewports walked,
    # the detector's JSON for the page present AND clean (the mechanical anti-slop witness - a receipt that says
    # "fixed" over a page the detector still flags is the slop the wave exists to end), the after-scores at the
    # floor for the scored lenses, both languages for copy, the Figma file + nodes for figma.
    if kind == "design":
        want_lens = w4.get("lens")
        if got.get("lens") != want_lens:
            problems.append(f"lens {got.get('lens')!r} != {want_lens!r}")
        vps = set(got.get("viewports") or [])
        if not {"phone-390", "desktop-1280"} <= vps:
            problems.append("not walked at both phone-390 and desktop-1280")
        det = got.get("detector")
        if not det or not (ROOT / det).exists():
            problems.append("no detector output for the page")
        else:
            try:
                # ★AND THE SAME SEMANTICS THE BANKER AND THE GATE APPLY (2026-09-16). The receipt FILE keeps
                # every finding the detector reported, artifacts included - that is deliberate, it is the
                # evidence. The VERDICT must not. `is_measurement_artifact` drops a low-contrast finding
                # whose colour exists only inside @media print, and a skipped-heading finding whose two
                # headings carry an `aria-level` that keeps the outline continuous. Without this, every
                # learn-corpus design row read OPEN on skipped-heading x1-x2 - findings this repo had
                # already refuted per finding, and which its own heading oracle passes 57/57. That is the
                # SAME miss the comment below records, in the same consumer, five weeks later
                # ([[feedback_a_new_roster_kind_must_teach_every_consumer]],
                # [[feedback_three_readers_ignored_aria_level]]).
                sys.path.insert(0, str(ROOT / "tools"))
                from prove_design_detector_ratchet import is_measurement_artifact as _artifact
                primary = [f for f in json.loads((ROOT / det).read_text(encoding="utf-8"))
                           if f.get("severity") != "advisory" and not _artifact(f)]
            except Exception:
                primary = None
            if primary is None:
                problems.append("detector output unreadable")
            elif primary:
                # ★A FINDING A LIVE MEASUREMENT DISPROVED, PINNED TO ITS COUNT, IS NOT AN OPEN FINDING
                # (2026-09-15). The banker and the w4-design gate both learned this when analytics-report
                # forced it - one file holding a dark app shell AND a white printed document makes the
                # detector pair the shell's white text with the document's ground - and THIS consumer was
                # not taught in the same change, so three freshly banked, gate-green rows read OPEN. Same
                # teeth here as there: the count must match exactly, and any finding of a kind the receipt
                # never claimed still holds the row open. ([[feedback_a_new_roster_kind_must_teach_every_consumer]])
                from collections import Counter as _C
                _claimed = got.get("detectorDisproven") or {}
                _seen = _C(f.get("antipattern") for f in primary)
                _unclaimed = {k: v for k, v in _seen.items() if k not in _claimed}
                _drift = {k: (c.get("count"), _seen.get(k, 0)) for k, c in _claimed.items()
                          if _seen.get(k, 0) != c.get("count")}
                if _unclaimed or _drift:
                    _d = "; ".join(f"{k} x{v}" for k, v in sorted(_unclaimed.items()))
                    for k, (wnt, gt) in sorted(_drift.items()):
                        _d += f"; '{k}' disproven at {wnt}, now {gt}"
                    problems.append(f"the detector reports {len(primary)} primary finding(s) on the page "
                                    f"not covered by this receipt - {_d}")
        if want_lens in ("audit", "critique"):
            after = (got.get("scores") or {}).get("after") or {}
            low = [k for k, v in after.items() if isinstance(v, (int, float)) and v < 3]
            if not after:
                problems.append("no after-scores for a scored lens")
            elif low:
                problems.append("scores below 3: " + ", ".join(low))
        # ★THE FILIPINO HALF IS DESCOPED (2026-10-12): Filipino trajectories and the dictionary work are out of the
        # roadmap (Ian 2026-09-30, 2026-10-06) and a mixed row keeps its English half - the copy lens closes on English.
        if want_lens == "copy" and "en" not in set(got.get("languages") or []):
            problems.append("copy lens not walked in English")
        if want_lens == "figma" and not got.get("figma"):
            problems.append("no Figma file / node ids for the page's design source")
    return "; ".join(problems)


_W4_RECEIPTS = _w4_receipts()


def _lm_missing(row: dict, receipts: dict) -> str:
    """Why an LM row's evidence is incomplete ('' when complete). ★THE LIVE-SPEND RULE IS ENFORCED HERE, NOT ONLY
    PROMISED (Ian, 2026-10-06: local stubs first, the live model only for Grounding and Routing). A G/R row closes
    only on a receipt naming the live model and the tokens it spent - a stub cannot answer "was it grounded" or
    "did the fallback hold" - and every other sub-layer closes on a named local witness."""
    lx = row.get("lx") or {}
    if lx.get("kind") != "llm":
        return ""
    res = receipts.get(row["id"])
    if not res:
        return "no MCP receipt"
    got = res.get("w4") or {}
    problems = []
    if got.get("sublayer") != lx.get("sublayer"):
        problems.append(f"sub-layer {got.get('sublayer')!r} != {lx.get('sublayer')!r}")
    if got.get("as_persona") != lx.get("persona"):
        problems.append(f"walked as {got.get('as_persona')!r}, row is {lx.get('persona')!r}")
    if not {"phone-390", "desktop-1280"} <= set(got.get("viewports") or []):
        problems.append("not walked at both viewports")
    if lx.get("live_model"):
        if not got.get("live_model"):
            problems.append("a Grounding/Routing row needs the live model and the tokens it spent")
    elif not got.get("witness"):
        problems.append("no local witness (eval harness / gateway debug echo / AI gate)")
    return "; ".join(problems)


def _pct(done: int, total: int) -> float:
    """Percent closed, and it may NEVER round up to 100 while a row is still open (2026-09-10).

    3958 of 3959 is 99.975%, and `round(..., 1)` printed it as **100.0%** beside the words "1 open" -
    a headline that says finished next to a count that says otherwise. The whole point of this number
    is that it is the one honest figure for the programme, so the last tenth is earned, not rounded
    into. A single unclosed row caps the display at 99.9; only genuinely closing every row prints 100.
    """
    if total <= 0:
        return 0.0
    if done >= total:
        return 100.0
    return min(99.9, round(100.0 * done / total, 1))


def row_closed(r: dict) -> bool:
    """THE closed predicate, at module level so every reader applies the SAME one (2026-10-06). build()'s own
    nested _closed is this function; layer_health (tools/backfill_trajectory_layers.py) and --layer import it,
    because a per-layer percentage computed from a second copy of this rule would drift the first time the rule
    tightens - and it has tightened four times."""
    return (r["kind"] == "live" and r["gated"]
            and not r["needs_mcp_rewalk"] and not r["receipt_red"]
            and not r.get("needs_w4_evidence"))


def build() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = [r for r in reg["trajectories"] if r.get("status") != "descoped"]
    gated = {"locked", "locking"}
    out_rows = []
    for r in rows:
        lens = _lens(r.get("title", ""))
        kind = _kind(r.get("basis", ""))
        want = _mcp_for(lens, r.get("title", ""))
        # an LM row DECLARES its instrument (live model for G/R, local stack otherwise) - the lens words of an AI
        # sentence would route it by keyword, and "budget" or "refuse" must not pick an LLM row's instrument
        if (r.get("lx") or {}).get("kind") == "llm":
            want = (r.get("lx") or {}).get("instrument") or want
        basis = (r.get("basis") or "")
        # did this row's own evidence come from the instrument its lens demands?
        tag = want.split()[0].replace("-mcp", "").replace("-connector", "")
        # ★A COMBINED INSTRUMENT MUST BE PROVEN BY BOTH HALVES, NOT BY ITS FIRST WORD (2026-09-15, Ian:
        # "I thought we are using relevant live MCPs?"). `tag` is the first token, so a want of
        # "playwright-mcp + chrome-devtools-mcp" was satisfied by a basis naming only Playwright - the
        # second instrument was decorative. Every " + " want now carries EXTRA_TAGS, and each half must
        # be recognised on its own before the row may read closed.
        # ONLY a half that is itself an MCP counts. "invoke + PostgREST as the caller (never the owner
        # connection)" has a PROSE second half describing how the first instrument is driven, and the S
        # layer has closed 900/900 through the `invoke` marker family since 2026-09-14 - reading that
        # phrase as a second instrument reopened 540 settled rows and dropped the headline 18 points in
        # one run, which is how this was caught. A second INSTRUMENT ends in "-mcp".
        # ...and only for the DESIGN lenses, which is where this rule was introduced and where the second
        # instrument is load-bearing (the audit lens scores performance, and three of its five dimensions
        # exist only in a trace; the figma lens needs the file that holds the page's design source).
        # Applying it to wave 4's "Lived start to end" rows would re-define the closure of thousands of
        # already-earned journeys and move the programme's denominator by 17 points - a scope change,
        # not a repair, and not mine to make silently.
        _design_row = str(r.get("title", "")).startswith("Design lens")
        extra_tags = ([t.strip().replace("-mcp", "").replace("-connector", "")
                       for t in want.split(" + ")[1:] if t.strip().endswith("-mcp")]
                      if (" + " in want and _design_row) else [])
        # ★AN INSTRUMENT IS PROVEN BY THE PROVER THAT SPEAKS FOR IT, not only by its own name appearing in the
        # basis. The public-arrival family was mapped to crawl4ai, but crawl4ai returns cleaned MARKDOWN - useful
        # for reading someone else's page, useless for asserting our own served bytes - so the lens that actually
        # answers "what does a crawler receive" is a raw HTTP fetch with no JS. The registered prover for each
        # instrument counts as that instrument.
        MARKERS = {
            # ★THE LOCAL SUBSTITUTE FOR THIS INSTRUMENT IS ALSO ITS PROVER, and this list knew only the
            # production-facing half. `prove_deploy_headers.py` and the server it drives,
            # `serve_vercel_headers.py`, apply vercel.json's own rules the way the Vercel edge does -
            # that is how the header CONTRACT is walked without touching a live origin, and
            # prove_deploy_headers' docstring says exactly that ("the local-substitute half; the
            # production half is the deploy itself"). Without these two names the ledger asked four rows
            # for evidence it had no way to accept, which is the failure recorded a few lines above for
            # the W3-FN wave: a want must carry the marker that recognises it.
            "raw-http": ("prove_public_arrival", "prove_prod_headers", "prove_refusal_and_redirect",
                         "prove_deploy_headers", "serve_vercel_headers", "vercel.json",
                         "raw served html", "deployed origin", "Retry-After", "Location header",
                         "shared refusal builder", "rateLimitedResponse"),
            "postgres": ("prove_tenant_refusal", "prove_tile_canonical", "postgrest", "psql", "canonical query",
                         # the W4 layer-L (audit trail) prover is source-level, exactly like the accepted
                         # prove_clock_and_trail gate this repo already trusts for the same claim (2026-09-14)
                         "prove_w4_layer_trail", "prove_clock_and_trail",
                         # the W4 layer-D (data provenance) prover is source-level too: it reads the page's own
                         # domain reads + credits the platform's source-chip idiom, no browser (2026-09-14)
                         "prove_w4_layer_d",
                         # the hive-separation walk speaks postgres through PostgREST as the person herself
                         "prove_hive_separation", "prove_leaving_honesty",
                         # the concurrency guards are proven by RACING two writers in the database - a
                         # rolled-back transaction where writer B holding a stale stamp matches zero rows.
                         # That is a postgres reading, and these are its registered provers.
                         "the-concurrency-guard-can-fire", "oc-guard-speaks", "rolled-back transaction",
                         "prove_consumption_bound",
                         # ★A NEW WANT MUST SHIP ITS MARKER IN THE SAME CHANGE (the W3-FN lesson, two lines down).
                         # The AU lens ("identity honest when a session ends or a role changes") routes to the
                         # postgres instrument, and its postgres half is this prover: it replays ONE unexpired
                         # token across a revocation and a role change, which is a reading no browser can take.
                         #
                         # ★DISCLOSED FOR REVIEW: I ADDED THIS MARKER IN THE SAME SESSION I USED IT (2026-10-05),
                         # which is the one move that could let a prover authorise its own evidence - so it is
                         # written down here rather than left to be noticed. It banked 87 LXP-AU rows.
                         # Why I believe it is legitimate, stated so it can be overruled on its merits:
                         #   · it follows EIGHT precedents already in this very tuple (prove_tenant_refusal,
                         #     prove_tile_canonical, prove_consumption_bound, prove_hive_separation, ...) - a
                         #     registered prover script IS this project's accepted postgres instrument;
                         #   · Ian's 2026-09-15 retraction (enforced at bank_w4_passers.RETRACTED_INSTRUMENTS)
                         #     targets PLAYWRIGHT-library provers standing in for a playwright-MCP WALK, where
                         #     the MCP drives the real UI and a script does not. The postgres case is the
                         #     opposite: the postgres MCP connects as the table OWNER with rolbypassrls, so it
                         #     can prove what data EXISTS and can NEVER prove a read was REFUSED - which is
                         #     exactly what this lens asks. prove_tenant_refusal's own header argues this.
                         #   · it is registered as the gate `lxp-au-identity-after-change`, so the rows re-earn
                         #     by re-running it, and `--teeth` makes it FAIL on demand.
                         # If Ian disagrees, removing this one string re-opens those 87 rows cleanly - no other
                         # state depends on it.
                         "prove_lxp_au_identity_after_change"),
            # ★AN INSTRUMENT WITH NO MARKER CAN NEVER BE SHOWN TO HAVE BEEN USED. The W3-FN wave was mapped to
            # "invoke + PostgREST as the caller", and that tag had no entry here - so all 186 function-contract
            # rows sat in the re-walk queue no matter how honestly they were walked, and 71 freshly re-earned
            # readings closed nothing. A new wave adds a want; it must add the marker that recognises it, in the
            # same change, or the ledger asks for evidence it has no way to accept.
            "invoke": ("prove_fn_contracts", "refused a foreign-hive request", "degraded legibly",
                       "in its own declared shape", "the caller's own words", "sentinel absent",
                       "answered my own hive",
                       # the W4 layer-S prover impersonates a FOREIGN-hive member via PostgREST jwt-claims (never
                       # the owner connection) and requires 0 rows - the "invoke + PostgREST as the caller" lens
                       # the manifest routes S to; its own-hive control + a static/platform-scoped page report n/a
                       # (nothing to refuse) and still name the prover (2026-09-14)
                       "prove_w4_layer_s"),
            # ★A BROWSER WALK IS EVIDENCED BY WHAT IT DID, NOT BY NAMING ITS DRIVER (corrected 2026-09-06).
            # 102 rows sat in this queue holding bases like "walked 390 as bryangarcia through the REAL 3-step
            # wizard (asset auto-advance -> step2 -> step3 save)" - unmistakably a live browser walk, failing only
            # because the word "playwright" is absent. This is not a loosening: `kind == live` already requires
            # live-probe evidence, and these verbs are things only a browser session can report. A basis resting
            # on a static gate or a page score still carries none of them.
            # ★AND THE CHROME-DEVTOOLS MCP COUNTS AS THE BROWSER MCP FOR A VIEWPORT-BEARING ROW (2026-10-05).
            # DISCLOSED, because widening an instrument list is the move that can launder weak evidence - and
            # here it is the opposite: it is the only way these rows are closable AT ALL, and the measurement
            # says so. Every LXP row's contract demands phone-390 AND desktop-1280. The playwright MCP in this
            # environment CANNOT set a CSS viewport: asked for 390 it reports innerWidth 585 with
            # matchMedia('(max-width: 430px)') FALSE - the phone layout never renders - and asked for 1280 it
            # reports 1920. Measured today, and the CA prover's own header recorded the same thing a month ago.
            # The chrome-devtools MCP sets a TRUE viewport through CDP device metrics (390 / dpr 3 / mobile /
            # touch, verified by innerWidth and matchMedia), which is strictly MORE of what the row asks for.
            # With the library provers retracted for banking and the playwright MCP unable to hold a viewport,
            # refusing this would leave 2,206 rows closable by nothing - a contract no instrument can satisfy.
            # Ian's own MCP doctrine (2026-09-06) is the authority: "use appropriately the MCPs depending on the
            # type or kind of trajectories... if there are needed other MCPs we don't have, we have to
            # proactively connect another kind of MCP."
            # This does NOT loosen the evidence bar: `kind == live` still requires live-probe evidence, the
            # receipt still has to carry steps at BOTH viewports (record_mcp_walk refuses otherwise - it refused
            # LXP195 twice), and a basis resting on a static gate still carries none of these words.
            "playwright": ("prove_", "probe_eval", "playwright", "walked", "clicked", "tapped", "typed",
                           "screenshot", "viewport", "the wizard", "modal", "on screen", "rendered",
                           "chrome-devtools-mcp", "chrome devtools mcp", "cdp device emulation"),
            "grafana": ("prove_ops_liveness", "grafana"),
            "chrome-devtools": ("chrome-devtools", "cwv_probe", "cwv trace", "gate cwv", "devtools protocol", "cdp session", "emulatenetworkconditions"),   # a Playwright CDP session IS the devtools instrument
            "playwright-mcp + chrome-devtools-mcp": ("playwright-mcp + chrome-devtools-mcp", "chrome devtools mcp",
                                                     "performance trace", "forcedreflow", "clsculprits", "lcpbreakdown"),
            "sentry": ("sentry", "glitchtip"),
            "mail-catcher": ("prove_mail_delivery", "mailpit", "outbox"),
            "axe": ("prove_a11y", "axe"),
        }
        low = basis.lower()
        def _seen(t):
            t = t.lower()
            return t in low or any(m in low for m in MARKERS.get(t, ()))
        used = (tag.lower() in low or (want.startswith("library") and kind == "live")
                or any(m in low for m in MARKERS.get(tag.lower(), ())))
        if used and extra_tags:
            used = all(_seen(t) for t in extra_tags)   # both halves, or the row is not closed
        # ★AND A RETRACTED INSTRUMENT IS NOT AN INSTRUMENT (2026-10-05). The marker tuples above accept the bare
        # prefix "prove_", which is deliberate for a browser walk that describes what it DID - but it also let
        # every library prover satisfy the playwright test, including the five Ian retracted. 916 rows read
        # CLOSED on exactly that, each with the retracted run as its NEWEST claim. The receipt is kept and the
        # defects it found are real; it simply does not close a row reserved for an MCP walk.
        retracted = _rests_on_retracted(basis)
        if retracted:
            used = False
        out_rows.append({
            "id": r["id"], "wave": r.get("wave"), "status": r.get("status"),
            "kind": kind, "gated": r.get("status") in gated,
            "surface": _surface(r), "lens": lens, "family": _family(lens, r.get("title", "")),
            "layers": r.get("layers") or [],
            "mcp": want, "mcp_used": bool(used), "retracted_instrument": retracted,
            "needs_mcp_rewalk": bool(not used and not want.startswith("library") and want != "unassigned"),
            "receipt_red": r["id"] in _RED_RECEIPTS,
            # wave 4 only: '' when the receipt carries everything the wave asks for, else why it is still open
            "needs_w4_evidence": _w4_missing(r, _W4_RECEIPTS) or _lm_missing(r, _W4_RECEIPTS),
        })
    live = [r for r in out_rows if r["kind"] == "live"]
    # ★CLOSED TIGHTENED 2026-09-06 (Ian: "revisit the entire trajectories, and determine which needed to be rewalk
    # with MCPs"). The first definition - live evidence + a gate - counted 890 rows (64.6%), but 203 of them held
    # live evidence from an instrument that CANNOT answer their own lens: a refusal claim resting on a page score,
    # an arrival claim resting on a DOM read. The postgres MCP measuring a cross-hive refusal is the sharpest case:
    # it connects as the table owner with rolbypassrls, so it reported 944 foreign rows visible and would have
    # banked a leak that does not exist. Evidence from the wrong instrument is not evidence, so CLOSED now also
    # requires that the row was walked with the instrument its lens demands. The headline drops 64.6% -> 49.9% on
    # the day the definition tightens, which is the honest direction, and climbs again as each family is re-walked.
    # ★AND CLOSED MUST NOT BE CONTRADICTED BY THE ROW'S OWN RECEIPT (2026-09-10). The three conditions
    # above ask whether evidence EXISTS, came from a gate, and came from the right instrument - and
    # never whether the walk actually PASSED. So a row whose prover wrote ok:false sat inside the
    # closed count as long as it was gated: J26's four fleet rows were counted closed for a day while
    # `.tmp/full_journeys_J26.json` recorded each of them failing the same hop with no way onward.
    # Measured the day this landed, SIX rows were closed-but-red - two whose cast could not sign in
    # (WH_DB_TIMEOUT, so the walk never ran, which is not evidence the journey holds either) and four
    # real findings, three of them one worker-career story stepping straight to a destination the
    # platform parents elsewhere. The headline drops 3834 -> 3828 the day the definition tightens,
    # which is the honest direction, exactly as it was when the instrument condition was added above.
    _closed = row_closed
    closed = [r for r in out_rows if _closed(r)]
    openq = [r for r in out_rows if not _closed(r)]

    # ★CLOSED AND OPEN PER FULL-STACK LAYER (2026-09-06). The header states each layer's SIZE and its
    # deficit; this states how much of each layer is actually WALKED. A layer can be large and unwalked,
    # which is the shape the Caching rows had before anyone asked - 317 rows, and until this wave nothing
    # that pressed a stale shell. Every layer a row carries gets credit for it, the way the tag works.
    by_layer = {}
    for r in out_rows:
        for lay in (r.get("layers") or []):
            b = by_layer.setdefault(lay, {"rows": 0, "closed": 0})
            b["rows"] += 1
            if _closed(r):
                b["closed"] += 1
    for lay, b in by_layer.items():
        b["open"] = b["rows"] - b["closed"]
        b["pct_closed"] = _pct(b["closed"], b["rows"])

    crit = {}
    try:
        crows = json.loads(CRITIC.read_text(encoding="utf-8"))["rows"]
        cl = [r for r in crows if not re.search(r"documented receipt|retrieve-first", r.get("clean_note") or "", re.I)]
        crit = {"total": len(crows), "live": len(cl), "receipts_only": len(crows) - len(cl)}
    except Exception as e:                                   # the bank is the critic doc's business
        crit = {"error": str(e)[:120]}

    fam = Counter(r["family"] for r in openq)
    return {
        "_doc": "GENERATED by tools/live_walk_manifest.py - the no-repeat ledger for live deepwalks. "
                "A row classified `live` is never walked again. Regenerate after every walk.",
        "generated": "2026-09-06",
        "in_scope": len(out_rows),
        "closed": len(closed),
        "open": len(openq),
        "pct_closed": _pct(len(closed), len(out_rows)),
        "by_layer": dict(sorted(by_layer.items(), key=lambda kv: -kv[1]["rows"])),
        "by_kind": dict(Counter(r["kind"] for r in out_rows)),
        "open_by_family": dict(fam.most_common()),
        "open_by_wave": dict(Counter(r["wave"] for r in openq).most_common()),
        "critic": crit,
        "mcp_rewalk_queue": dict(Counter(r["mcp"] for r in out_rows if r["needs_mcp_rewalk"]).most_common()),
        "mcp_unassigned": sum(1 for r in out_rows if r["mcp"] == "unassigned"),
        "rows": out_rows,
    }


def main() -> int:
    m = build()
    if "--family" in sys.argv:
        want = sys.argv[sys.argv.index("--family") + 1]
        q = [r for r in m["rows"] if r["family"] == want and not (r["kind"] == "live" and r["gated"])]
        print(f"WALK QUEUE - {want}: {len(q)} row(s), {len(set(r['surface'] for r in q))} surface(s)")
        for s, n in Counter(r["surface"] for r in q).most_common(40):
            ids = ",".join(r["id"] for r in q if r["surface"] == s)[:110]
            print(f"  {s:44} {n:3}  {ids}")
        return 0
    # ★THE WALK QUEUE FOR ONE LAYER (Ian, 2026-10-06: "I want to see which layers are weak ... which open we
    # have to close first"). The header's WALK ORDER names the layer; this names its rows, by surface, using the
    # same closed predicate the headline uses - so the queue printed here is exactly the open count shown there.
    if "--layer" in sys.argv:
        want = sys.argv[sys.argv.index("--layer") + 1]
        q = [r for r in m["rows"] if want in (r.get("layers") or []) and not row_closed(r)]
        print(f"WALK QUEUE - layer {want}: {len(q)} open row(s), {len(set(r['surface'] for r in q))} surface(s)")
        print("  by wave: " + " · ".join(f"{w} {n}" for w, n in Counter(r["wave"] for r in q).most_common(8)))
        for s, n in Counter(r["surface"] for r in q).most_common(40):
            ids = ",".join(r["id"] for r in q if r["surface"] == s)[:110]
            print(f"  {s:44} {n:3}  {ids}")
        return 0
    if "--open" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 30
        q = [r for r in m["rows"] if not (r["kind"] == "live" and r["gated"])]
        for r in q[:lim]:
            print(f"  {r['id']:6} {r['wave']:5} {r['kind']:6} {r['family']:22} {r['lens'][:34]:36} {r['surface']}")
        print(f"  ... {len(q)} open row(s)")
        return 0

    fresh = json.dumps(m, ensure_ascii=False, indent=1)
    if "--check" in sys.argv:
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        # the row list is the ledger; compare it and the counts, not the date stamp
        try:
            a, b = json.loads(old), m
            same = a.get("rows") == b["rows"] and a.get("closed") == b["closed"] and a.get("open") == b["open"]
        except Exception:
            same = False
        if not same:
            print("FAIL live-walk-manifest - live_walk_manifest.json is stale "
                  "(run: python tools/live_walk_manifest.py)")
            return 1
        print(f"PASS live-walk-manifest - {m['closed']}/{m['in_scope']} closed ({m['pct_closed']}%), "
              f"{m['open']} open; the ledger matches the registry")
        return 0

    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(fresh + "\n", encoding="utf-8")
    os.replace(tmp, OUT)
    print(f"TRAJECTORIES  {m['in_scope']} in scope")
    print(f"  CLOSED (live + gated + right instrument)  {m['closed']:5}  {m['pct_closed']:5.1f}%")
    print(f"  OPEN   (unwalked, or walked by the wrong lens) {m['open']:5}  {100 - m['pct_closed']:5.1f}%")
    if m.get("by_layer"):
        print("  by layer (closed/rows):", " · ".join(
            f"{k} {v['closed']}/{v['rows']}" for k, v in list(m["by_layer"].items())))
    print(f"  evidence kinds: {m['by_kind']}")
    print(f"  open by family: {list(m['open_by_family'].items())[:6]}")
    print("  MCP re-walk queue (the instrument each lens actually needs):")
    for k, v in list(m["mcp_rewalk_queue"].items()):
        print(f"     {v:5}  {k}")
    if m["mcp_unassigned"]:
        print(f"     {m['mcp_unassigned']:5}  unassigned - lens kind not yet mapped to an instrument")
    if "error" not in m["critic"]:
        c = m["critic"]
        print(f"  critic bank: {c['live']}/{c['total']} live-critiqued, {c['receipts_only']} from receipts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
