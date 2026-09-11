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
        for res in (doc.get("results") or []):
            rid = res.get("id")
            if rid and (rid not in best or mtime >= best[rid][1]):
                best[rid] = (res, mtime)
    return {rid for rid, (res, _m) in best.items()
            if not res.get("ok") or res.get("unbuilt")}


_RED_RECEIPTS = _red_receipt_ids()


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


def build() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = [r for r in reg["trajectories"] if r.get("status") != "descoped"]
    gated = {"locked", "locking"}
    out_rows = []
    for r in rows:
        lens = _lens(r.get("title", ""))
        kind = _kind(r.get("basis", ""))
        want = _mcp_for(lens, r.get("title", ""))
        basis = (r.get("basis") or "")
        # did this row's own evidence come from the instrument its lens demands?
        tag = want.split()[0].replace("-mcp", "").replace("-connector", "")
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
                         # the hive-separation walk speaks postgres through PostgREST as the person herself
                         "prove_hive_separation", "prove_leaving_honesty",
                         # the concurrency guards are proven by RACING two writers in the database - a
                         # rolled-back transaction where writer B holding a stale stamp matches zero rows.
                         # That is a postgres reading, and these are its registered provers.
                         "the-concurrency-guard-can-fire", "oc-guard-speaks", "rolled-back transaction",
                         "prove_consumption_bound"),
            # ★AN INSTRUMENT WITH NO MARKER CAN NEVER BE SHOWN TO HAVE BEEN USED. The W3-FN wave was mapped to
            # "invoke + PostgREST as the caller", and that tag had no entry here - so all 186 function-contract
            # rows sat in the re-walk queue no matter how honestly they were walked, and 71 freshly re-earned
            # readings closed nothing. A new wave adds a want; it must add the marker that recognises it, in the
            # same change, or the ledger asks for evidence it has no way to accept.
            "invoke": ("prove_fn_contracts", "refused a foreign-hive request", "degraded legibly",
                       "in its own declared shape", "the caller's own words", "sentinel absent",
                       "answered my own hive"),
            # ★A BROWSER WALK IS EVIDENCED BY WHAT IT DID, NOT BY NAMING ITS DRIVER (corrected 2026-09-06).
            # 102 rows sat in this queue holding bases like "walked 390 as bryangarcia through the REAL 3-step
            # wizard (asset auto-advance -> step2 -> step3 save)" - unmistakably a live browser walk, failing only
            # because the word "playwright" is absent. This is not a loosening: `kind == live` already requires
            # live-probe evidence, and these verbs are things only a browser session can report. A basis resting
            # on a static gate or a page score still carries none of them.
            "playwright": ("prove_", "probe_eval", "playwright", "walked", "clicked", "tapped", "typed",
                           "screenshot", "viewport", "the wizard", "modal", "on screen", "rendered"),
            "grafana": ("prove_ops_liveness", "grafana"),
            "chrome-devtools": ("chrome-devtools", "cwv_probe", "cwv trace", "gate cwv", "devtools protocol", "cdp session", "emulatenetworkconditions"),   # a Playwright CDP session IS the devtools instrument
            "sentry": ("sentry", "glitchtip"),
            "mail-catcher": ("prove_mail_delivery", "mailpit", "outbox"),
            "axe": ("prove_a11y", "axe"),
        }
        low = basis.lower()
        used = tag.lower() in low or (want.startswith("library") and kind == "live")             or any(m in low for m in MARKERS.get(tag.lower(), ()))
        out_rows.append({
            "id": r["id"], "wave": r.get("wave"), "status": r.get("status"),
            "kind": kind, "gated": r.get("status") in gated,
            "surface": _surface(r), "lens": lens, "family": _family(lens, r.get("title", "")),
            "layers": r.get("layers") or [],
            "mcp": want, "mcp_used": bool(used),
            "needs_mcp_rewalk": bool(not used and not want.startswith("library") and want != "unassigned"),
            "receipt_red": r["id"] in _RED_RECEIPTS,
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
    def _closed(r):
        return (r["kind"] == "live" and r["gated"]
                and not r["needs_mcp_rewalk"] and not r["receipt_red"])
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
