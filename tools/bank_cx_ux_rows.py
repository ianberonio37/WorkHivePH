#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bank the CX-UX rows - "rubric class K was never graded on page P" - when EVERY dim of K is accounted for on P.

THE ROW. Wave CX-UX (T6) holds one row per (page, rubric class) cell that no critic row on that page had graded on the
day the cube was seeded (tools/cube_census.py ux_cells). Each row closes when "rubric class K is graded on P by the
critic deepwalk". Nothing banked them: 360 sat at specced.

★A CLASS IS ANSWERED ONLY WHEN EVERY DIM OF IT IS (2026-11-03, the coordinator, settling the question this tool's first
version raised). "Every dim the page survey asks came back N/A" is NOT N/A for the class: AI1-AI5 are the lens's, AI6
is the AI write-provenance validator's, and a class with one dim nobody asked is a class nobody finished. So each dim
is accounted for by THE INSTRUMENT THAT OWNS IT (ufai-rubric-spec.json `owner`):
  * a dim the page lens owns  -> the critic walk's survey file of P (or a finding the bank wrote naming P)
  * any other dim             -> its owner's per-page record (OWNER_SOURCES below), read for P and that dim only
and the three answers are:
  (a) GRADED  every dim accounted for, at least one MEASURED with a real denominator
  (b) N/A     every dim accounted for, every one N/A, each with its instrument's reason
  (c) OPEN    a dim is unaccounted for - and the report says which dim, whose, and what would produce it: a page
              survey (critic_walk_batch.mjs), a run of its owner, structure its owner lacks, or no instrument at all.

★A JUDGED DIM IS NOT A GRADE, AND IS AN ANSWER ONLY WHERE THE SPEC MAKES IT ONE. The lens reports JUDGED with pct null:
"a cited criterion with no honest denominator" (survey_ufai_rubric.js). It never counts toward (a). It ACCOUNTS for a
dim only when the spec declares that dim `verdict: judged` AND owns it to the lens (F3, H2, H3, J2, R5): judging is the
whole of that instrument's contract for that dim, and nothing else exists to measure it. A dim the spec owns to someone
else (I1, F2, D2 belong to the battery) is not answered by the lens judging it - its owner must say. A MEASURED dim
whose pct is null (a denominator of 0) answers nothing.

★THE CENSUS'S RULE FOUND THE CELLS; IT CANNOT CLOSE THEM. ux_cells credits a page with a class when a critic row whose
`_target` (last page) is that page lists a dim of the class in `dims_graded`. Read against the evidence it is wrong
in both directions, measured 2026-11-03:
  * a walk's `dims_graded` is the UNION over every page it surveyed (bank_critic_walk.collect), and it includes N/A
    dims - so the rule credits the LAST page with dims measured on the pages before it. W41717 walked index -> hive ->
    marketplace -> platform-actions; its union lists AI1-AI5, and the platform-actions survey itself says every one
    is N/A ("no AI input surface on this page"). The census would have closed platform-actions' AI cell on that.
  * it credits NOTHING to the earlier pages of a walk, though each was surveyed in full - the bank's own clean_note
    says "Surveyed: about 91 dims, 7 sub-100", and about/index.html still carries 32 CX-UX rows because it is the
    FIRST page of W41354's walk, not the last.
  * it reads the REGISTRY row's route: 766 trajectories have been re-routed since their critic walk (W41717's route
    now ends at founder-console.html), so it credits a page that was never opened with another page's survey.
So the per-page truth is used instead: the survey file the walk wrote for THAT page (critic_walk_batch.mjs writes
.tmp/batchsurvey/<walk id>_<pageId>.json, one per page, and bank_critic_walk.py banks from exactly those files), or a
finding the bank wrote naming the page ("about: B3 0% - ..."). `_target` is still read, to report how many of the
cells banked here the census's rule would also have credited.

★A READING IS EVIDENCE ONLY OF THE SCREEN IT READ, AT THE MOMENT IT WAS BANKED. Four guards on every survey file:
  * its pageId is P's (the batch's own pageIdOf: a nested index.html is its directory), and it was not access-denied;
  * it is no newer than the critic row's bank (`banked_at`, to the second; else the END of `walked_at`'s day) - the
    batch writes a walk's files before it banks them, so a newer file came from a later run the bank never took
    (a dry run, or a walk refused for a denied page);
  * every dim it records for K is in the row's `dims_graded` - the bank accepted that reading;
  * on a page that is not public, the walk's cast is the row's own cast: a signed-out or wrong-role visit to an
    auth-gated page can land somewhere else while the file still says P ([[feedback_a_closer_must_ask_when_and_which_screen]]).
    A public page (an article, a calculator, about) serves every visitor the same document, so any cast reads it.
An owner's record is held to the same page identity: it is read under P's own path, never under another page's.

USAGE
  python tools/bank_cx_ux_rows.py                    dry run: the three buckets, (c) by what would close it
  python tools/bank_cx_ux_rows.py --apply            bank (a) and (b): locking, pct 60, basis appended, gate named
  python tools/bank_cx_ux_rows.py --check            the gate cx-ux-graded (exit 1 when a banked row lost its evidence)
  python tools/bank_cx_ux_rows.py --self-test
  --receipts DIR    where the walk's survey files are (default .tmp/batchsurvey)
  --owners DIR      where the owners' per-page records are (default: the repo root, where each owner writes them)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import cube_census as _cc          # noqa: E402  the census that seeded these rows: its rubric path and _target
import registry_io as _rio         # noqa: E402  the registry and critic UNIONS (the cube lives in the CX shards)
from cube_census import _target    # noqa: E402

REGISTRY = ROOT / "trajectory_registry.json"
LENS = ROOT / "survey_ufai_rubric.js"
RECEIPTS = ROOT / ".tmp" / "batchsurvey"
CTA_PROVER = ROOT / "tools" / "prove_cta_activation.mjs"
GATE_ID = "cx-ux-graded"            # as registered in run_platform_checks.py
TOOL = "tools/bank_cx_ux_rows.py"   # the basis names it; its presence is what makes a re-run idempotent
WAVE = "CX-UX"
LENS_OWNER = "rubric-lens"
BANKED = ("critiqued", "improving", "locked")     # a critic row back at `pending` has been RESET and vouches for nothing
SLACK = timedelta(seconds=2)        # file-time granularity; the batch writes a survey seconds before it banks it
# ★the dims the PAGE LENS asks, read from the lens itself: M(...) measured, J(...) judged, NA(...) n/a. The spec's
# `owner` is not this list - D2, F2 and I1 are owned by the battery and still emitted (JUDGED) by the lens - and a
# second hand-typed copy would drift the first time the lens gains a dim.
LENS_DIM_RE = re.compile(r"\b(?:M|J|NA)\(\s*'([A-Z]+\d+)'")
# the finding bank_critic_walk.collect writes for a sub-100 MEASURED dim: "<pageId>: <dim> <pct>% - <note>"
FINDING_RE = re.compile(r"^(?P<pid>[A-Za-z0-9_.\-]+):\s+(?P<dim>[A-Z]+\d+)\s+(?P<pct>\d+)%(?:\s+-\s+(?P<note>.*))?$", re.S)

# ★WHERE EACH OWNER RECORDS "THIS PAGE, THIS DIM", read from each owner's source, not assumed (2026-11-03):
#   journey     validate_journey_ux_dims.py writes journey_ux_dims_report.json; `pages[<page>][J3|G5|S4]` = {verdict
#               MEASURED (pct 100 held / 0 the gap) | N/A, note} - its own rules per page (page_verdicts), held equal to
#               its ratchet's gaps by its self-test. Static, so a run is cheap. Gitignored (*_report.json).
#   provenance  validate_ai_write_provenance.py writes ai_write_provenance_report.json; `pages[<page>].AI6` = MEASURED
#               over the AI writes the page can reach, or N/A when it reaches none (measure_pages). Static. Gitignored.
#   board       family_rubric_sweep.mjs writes family_rubric_scoreboard.json (tracked); `pages[<page>].dims[]` carries
#               I1 (Core Web Vitals) and D2 (feedback < 400 ms) MEASURED LIVE - the battery's own numbers. F2 is
#               there too but always JUDGED: the sweep has no axe verdict for it, so the board never answers F2.
#   corpus      survey_component_consistency.py writes component_consistency_corpus.json (tracked);
#               `corpus[<page>].primitives` lists every card-primitive instance and its missing_required parts - S3.
#               It scanned the root *.html pages only until 2026-11-04; it now records EVERY page of the generated
#               public families too (learn hub + guides, calculators, the four public-root pages), with their own
#               card primitives pinned (.article-card, .author-card), and its --check holds the record current.
#   cta         prove_cta_activation.mjs writes cta_activation_report.json; `results[]` per click, keyed by its ROSTER's
#               slug (read from the prover) - CV1. It walks a five-page roster, and writes nothing for a page whose
#               walk found no primary CTA, so only a MEASURED reading exists.
#   chrome      prove_shared_chrome_parity.py writes shared_chrome_parity.json (tracked, 2026-11-04); `pages[<page>].S2`
#               = {verdict MEASURED, pct, note}: the five shared-chrome parts (skip link, banner, primary nav, main,
#               footer) against the DECLARED public template (build_pillar_pages.py). Static; the public families
#               only - the app pages draw their chrome at runtime (the lens's W2), so it writes no record for them.
#   conversion  prove_page_conversion.mjs writes page_conversion_cv.json (tracked, 2026-11-04); `pages[<page>].CV2|CV3`
#               = {verdict, pct, note}, walked signed out FROM that page: CV2 every wall reachable from it doored (N/A
#               when no wall is reachable, with the links followed), CV3 the six funnel steps through its own door.
#   cta (again) since 2026-11-04 the CTA report also carries `pages[<slug>].walked` - what each viewport's walk found -
#               so a page walked at 390 and 1280 with no primary-styled CTA reads N/A instead of "no record".
OWNER_SOURCES = {
    "journey":    {"file": "journey_ux_dims_report.json", "tracked": False, "dims": ("J3", "G5", "S4"),
                   "needs": "run", "how": "python tools/validate_journey_ux_dims.py  (static)"},
    "provenance": {"file": "ai_write_provenance_report.json", "tracked": False, "dims": ("AI6",),
                   "needs": "run", "how": "python tools/validate_ai_write_provenance.py  (static)"},
    "board":      {"file": "family_rubric_scoreboard.json", "tracked": True, "dims": ("I1", "D2"),
                   "needs": "run", "how": "node tools/family_rubric_sweep.mjs --page <page>  (browser)"},
    # F2 left the board on 2026-11-04: the board only ever JUDGES it (no axe verdict in the sweep). The battery's axe
    # kernel runs live in tools/axe_scan_live.js, which now records per page the applicable WCAG 2.2 AA rules that pass.
    "axe":        {"file": "axe_live_violations_report.json", "tracked": False, "dims": ("F2",),
                   "needs": "run", "how": "node tools/axe_scan_live.js --page <page>  (browser)"},
    "corpus":     {"file": "component_consistency_corpus.json", "tracked": True, "dims": ("S3",),
                   "needs": "run", "how": "python tools/survey_component_consistency.py  (static)"},
    "cta":        {"file": "cta_activation_report.json", "tracked": False, "dims": ("CV1",),
                   "needs": "structure", "how": "prove_cta_activation.mjs walks its ROSTER only - add the page"},
    "chrome":     {"file": "shared_chrome_parity.json", "tracked": True, "dims": ("S2",),
                   "needs": "run", "how": "python tools/prove_shared_chrome_parity.py --write  (static)"},
    "conversion": {"file": "page_conversion_cv.json", "tracked": True, "dims": ("CV2", "CV3"),
                   "needs": "run", "how": "node tools/prove_page_conversion.mjs --page <page>  (browser, signed out)"},
}
SOURCE_OF = {d: s for s, o in OWNER_SOURCES.items() for d in o["dims"]}
# dims whose owner writes NO per-page record anywhere - a missing instrument, not a missing run (read from each owner's
# source 2026-11-03): JA1-JA3 are the journey validator's ratchet totals, not yet in its per-page record. (2026-11-04:
# S2 left this list - tools/prove_shared_chrome_parity.py measures it per page, the "chrome" owner; and CV2/CV3 left it
# - the journeys that answered them (prove_journey J1-J3, LA8/LA10/LA11/LA12) each speak for the ONE page they walked,
# so reading LA11's verdict for about/ would credit a page with a walk that never opened it. tools/
# prove_page_conversion.mjs walks each page itself with those journeys' steps - the "conversion" owner.)
NO_INSTRUMENT = {
    "JA1": "the journey validator records deep-link arrival as a ratchet total, not per page",
    "JA2": "the journey validator records the return promise as a ratchet total, not per page",
    "JA3": "the journey validator records back-dismiss as a ratchet total, not per page",
}


# ── the rubric ────────────────────────────────────────────────────────────────────────────────────────────────────
def load_spec() -> dict:
    return json.loads(_cc.RUBRIC.read_text(encoding="utf-8"))


def spec_classes(spec: dict) -> tuple[dict, dict]:
    """(dim -> class, class -> sorted dims). The class of a dim is its `class` field - ux_cells' own reading."""
    dimcls = {k: v.get("class") for k, v in spec.items() if k != "_meta" and isinstance(v, dict)}
    members: dict = defaultdict(list)
    for d, k in dimcls.items():
        members[k].append(d)
    return dimcls, {k: sorted(v) for k, v in members.items()}


def owner_of(spec: dict, dim: str) -> str:
    return str((spec.get(dim) or {}).get("owner") or LENS_OWNER)


def lens_dims(src: str | None = None) -> set:
    if src is None:
        src = LENS.read_text(encoding="utf-8") if LENS.exists() else ""
    return set(LENS_DIM_RE.findall(src))


def accounts(spec: dict, dim: str, v, by_lens: bool) -> bool:
    """Does reading v = (kind, pct, note) account for `dim`? MEASURED with a number or N/A always; a lens JUDGED only
    where the spec declares the dim judged and owns it to the lens (see the module note)."""
    kind, pct = v[0], v[1]
    if kind == "MEASURED":
        return pct is not None
    if kind == "N/A":
        return True
    return (by_lens and kind == "JUDGED" and owner_of(spec, dim) == LENS_OWNER
            and (spec.get(dim) or {}).get("verdict") == "judged")


# ── the walk's own per-page survey files ──────────────────────────────────────────────────────────────────────────
def page_id(page: str) -> str:
    """critic_walk_batch.mjs pageIdOf: a nested index.html is named by its DIRECTORY (the 54 articles and 60
    calculators are one index per directory), anything else by its file name."""
    parts = str(page).replace("\\", "/").split("/")
    if parts[-1] == "index.html" and len(parts) > 1:
        return parts[-2]
    return re.sub(r"\.html$", "", parts[-1])


def receipt_name(rid: str, page: str) -> str:
    # the batch's own file name: `${OUTDIR}/${w.ids[0]}_${pid.replace(/[^a-z0-9-]/gi, '_')}.json`
    return f"{rid}_{re.sub(r'[^a-z0-9-]', '_', page_id(page), flags=re.I)}.json"


class ReceiptDir:
    """Survey files by (walk id, page). Read lazily - the directory holds thousands and a cell needs a handful."""

    def __init__(self, path):
        self.path = Path(path)
        self.names = set(os.listdir(self.path)) if self.path.is_dir() else set()
        self._cache: dict = {}

    def __len__(self):
        return len(self.names)

    def get(self, rid: str, page: str):
        name = receipt_name(rid, page)
        if name not in self.names:
            return None
        if name not in self._cache:
            p = self.path / name
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(s, dict) and "result" in s:          # an MCP tool wraps its output
                    s = s["result"]
                self._cache[name] = (s, datetime.fromtimestamp(p.stat().st_mtime), name)
            except (OSError, ValueError):
                self._cache[name] = None                          # an unreadable file is not evidence either way
        return self._cache[name]


def bank_moment(c: dict):
    """When the critic row's reading was banked. `banked_at` is to the second; a row banked before that field existed
    has only `walked_at`, a day, read as the END of that day - a survey file from that day was written by that day's
    walk (the batch deletes a walk's old files before writing new ones), one from a later day cannot have been its input."""
    b = c.get("banked_at")
    if b:
        try:
            return datetime.fromisoformat(str(b))
        except ValueError:
            pass
    w = str(c.get("walked_at") or "")[:10]
    if w:
        try:
            return datetime.fromisoformat(w + "T23:59:59")
        except ValueError:
            pass
    return None


def cast_of(c: dict) -> str:
    parts = str(c.get("cell") or "").split("|")
    return parts[1] if len(parts) > 1 and parts[1] else str(c.get("persona") or "")


def page_reading(c: dict, page: str, cls: str, members: dict, dimcls: dict, receipts):
    """What critic row `c`'s walk recorded for class `cls` ON `page` itself: ({source, dims{dim: (kind, pct, note)},
    file, when}, "") or (None, why-not). Only per-page records count - never the walk's union."""
    dg = set(c.get("dims_graded") or [])
    if not any(d in dg for d in members.get(cls, ())):
        return None, ""                                           # this walk says nothing about the class at all
    if page not in (c.get("pages") or []):
        return None, "the page is not on the walk's declared path"
    why = ""
    rec = receipts.get(c["id"], page) if receipts is not None else None
    if rec:
        s, mtime, name = rec
        when = bank_moment(c)
        if str(s.get("pageId") or "") != page_id(page):
            why = f"its survey file {name} grades pageId {s.get('pageId')!r}, not this page"
        elif s.get("_denied"):
            why = f"its survey file {name} rendered access-denied"
        elif when is None:
            why = "the critic row records no bank time, so its survey file cannot be tied to its bank"
        elif mtime > when + SLACK:
            why = f"its survey file {name} is newer than the bank - a later run the bank never took"
        else:
            got = {x["dim"]: (x.get("kind"), x.get("pct"), " ".join(str(x.get("note") or "").split()))
                   for x in (s.get("dims") or []) if isinstance(x, dict) and dimcls.get(x.get("dim")) == cls}
            if not got:
                why = f"its survey file {name} records no dim of the class"
            elif not all(d in dg for d in got):
                why = f"its survey file {name} records dims the bank never took ({', '.join(sorted(set(got) - dg))})"
            else:
                return {"source": "receipt", "file": name, "dims": got, "when": when,
                        "reused": s.get("_reusedFrom")}, ""
    # the durable half: a finding the bank itself wrote about this page (a sub-100 MEASURED dim, with its number)
    got = {}
    for f in (c.get("findings") or []):
        m = FINDING_RE.match(str((f or {}).get("evidence") or "").strip())
        if m and m.group("pid") == page_id(page) and dimcls.get(m.group("dim")) == cls and m.group("dim") in dg:
            got[m.group("dim")] = ("MEASURED", int(m.group("pct")), " ".join((m.group("note") or "").split()))
    if got:
        return {"source": "finding", "file": None, "dims": got, "when": bank_moment(c), "reused": None}, ""
    return None, why or "no per-page record (no survey file of this page from this walk, no finding naming it)"


# ── the owners' per-page records ──────────────────────────────────────────────────────────────────────────────────
class OwnerSources:
    """Each owner's per-page record, read for one (page, dim) at a time. `data` injects the parsed files (the
    self-test); otherwise each is read lazily from `root`, where its owner writes it."""

    def __init__(self, root=ROOT, data: dict | None = None, cta_roster: dict | None = None):
        self.root = Path(root)
        self.data = dict(data or {})
        self._roster = cta_roster

    def present(self, src: str) -> bool:
        return self.doc(src) is not None

    def ever_answers(self, src: str, dim: str, spec: dict) -> bool:
        """Has this owner EVER accounted for `dim` on any page it recorded? If not, a run on one more page cannot
        either - the board records F2 JUDGED on all 57 of its pages, so 'run the sweep on feedback' would be a wasted
        browser run reported as the way to close the row. An absent report proves nothing, so it counts as yes."""
        d = self.doc(src)
        if d is None:
            return True
        if src == "board":
            recs = [x for p in (d.get("pages") or {}).values() for x in (p.get("dims") or []) if x.get("dim") == dim]
            return any(accounts(spec, dim, (x.get("kind"), x.get("pct"), ""), False) for x in recs)
        return True

    def covers(self, src: str, page: str) -> bool:
        """Could a RUN of this owner, as built, ever record this page? False means it needs structure first: the
        corpus scans the root *.html pages only, and the CTA prover walks its roster only."""
        if src == "corpus":
            # every generated public page is scanned; a root page unless the corpus excludes it by name
            if "/" in page:
                return True
            from survey_component_consistency import EXCLUDE_RE
            return not EXCLUDE_RE.search(page)
        if src == "cta":
            return page in self.cta_roster()
        if src == "chrome":
            return "/" in page                   # the static-chrome public families; app chrome is the lens's W2
        return True

    def doc(self, src: str):
        if src not in self.data:
            p = self.root / OWNER_SOURCES[src]["file"]
            try:
                self.data[src] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
            except (OSError, ValueError):
                self.data[src] = None
        return self.data[src]

    def cta_roster(self) -> dict:
        """page -> slug, read from the prover itself (its report names the slug, never the page)."""
        if self._roster is None:
            try:
                src = CTA_PROVER.read_text(encoding="utf-8")
            except OSError:
                src = ""
            self._roster = {p: s for p, s in re.findall(r"\{\s*page:\s*'([^']+)',\s*slug:\s*'([^']+)'\s*\}", src)}
        return self._roster

    def reading(self, page: str, dim: str):
        """((kind, pct, note), source) or (None, why). Read under THIS page's own path - never another page's."""
        src = SOURCE_OF.get(dim)
        if not src:
            return None, NO_INSTRUMENT.get(dim, f"no owner instrument writes a per-page record for {dim}")
        d = self.doc(src)
        f = OWNER_SOURCES[src]["file"]
        if d is None:
            return None, f"{f} is not on disk - run its owner"
        if src in ("journey", "provenance", "chrome", "conversion"):
            rec = ((d.get("pages") or {}).get(page) or {}).get(dim)
            if not rec:
                return None, f"{f} has no record of {page}" + ("" if d.get("pages") else " (an older report with no per-page record)")
            if rec.get("verdict") is None:
                return None, f"{f}: {dim} on {page} has no verdict - {rec.get('note') or '?'}"
            return (rec["verdict"], rec.get("pct"), str(rec.get("note") or "")), src
        if src == "axe":
            if d.get("skipped"):
                return None, f"{f} is a skipped run ({d.get('reason') or '?'}) - run its owner again"
            p = (d.get("detail") or {}).get(page)
            if not p:
                return None, f"{f} has no record of {page}"
            if p.get("skipped"):
                return None, f"{f}: {page} was skipped ({p.get('reason') or '?'})"
            x = p.get("F2")
            if not x:
                return None, f"{f}: {page} was scanned by an older run that recorded no rule totals - run it again"
            return (x.get("verdict"), x.get("pct"), str(x.get("note") or "")), src
        if src == "board":
            p = (d.get("pages") or {}).get(page)
            if not p:
                return None, f"{f} has no record of {page}"
            x = next((x for x in (p.get("dims") or []) if x.get("dim") == dim), None)
            if not x:
                return None, f"{f} records no {dim} for {page}"
            return (x.get("kind"), x.get("pct"), str(x.get("note") or "")), src
        if src == "corpus":
            p = (d.get("corpus") or {}).get(page)
            if not p:
                return None, f"{f} has no record of {page}"
            inst = [i for v in (p.get("primitives") or {}).values() for i in (v or [])]
            if not inst:
                return ("N/A", None, "no card primitive on the page (the corpus's census of it)"), src
            whole = sum(1 for i in inst if not i.get("missing_required"))
            return ("MEASURED", round(100 * whole / len(inst)),
                    f"{whole}/{len(inst)} card-primitive instance(s) carry every required part"), src
        if src == "cta":
            slug = self.cta_roster().get(page)
            if not slug:
                return None, f"{page} is not on prove_cta_activation.mjs's roster"
            res = [r for r in (d.get("results") or []) if r.get("page") == slug
                   and not str(r.get("verdict") or "").startswith("walk-error")]
            walked = ((d.get("pages") or {}).get(slug) or {}).get("walked") or {}
            if not res and walked:
                # the prover's own record of the walk (2026-11-04): N/A only when EVERY viewport was walked to the end
                # and found no primary-styled control - an error, or a viewport never walked, answers nothing
                errs = [v for v, w in walked.items() if (w or {}).get("error")]
                if errs or set(walked) != {"390", "1280"}:
                    return None, f"{f}: the walk of {page} did not finish at {', '.join(errs) or 'both viewports'}"
                if all(int((w or {}).get("ctas") or 0) == 0 for w in walked.values()):
                    return ("N/A", None, "walked as anon at 390 and 1280: no primary-styled CTA on the page (by class "
                                         "or by brand fill)"), src
            if not res:
                return None, f"{f} holds no click on {page} (a walk with no primary CTA writes nothing to tell apart)"
            alive = sum(1 for r in res if not r.get("dead"))
            return ("MEASURED", round(100 * alive / len(res)), f"{alive}/{len(res)} primary CTA click(s) had a consequence"), src
        return None, f"no reader for {src}"


def index_critic(crit_rows: list) -> dict:
    """page -> the critic rows whose declared walk includes it."""
    by_page: dict = defaultdict(list)
    for c in crit_rows:
        for p in set(c.get("pages") or []):
            by_page[p].append(c)
    return by_page


def _is_grade(v) -> bool:
    """THE one definition of a grade: MEASURED with a number. JUDGED never is; a null-pct MEASURED never is."""
    return v[0] == "MEASURED" and v[1] is not None


def _measured(dims: dict) -> dict:
    return {d: v for d, v in dims.items() if _is_grade(v)}


def classify(row: dict, by_page: dict, members: dict, dimcls: dict, lens: set, spec: dict, receipts,
             owners: OwnerSources) -> dict:
    """One open CX-UX row -> {bucket a|b|c, witnesses [(critic row, reading)], owned {dim: (reading, source)},
    missing [(dim, need, why)], doubts, census}."""
    cx = row.get("cx") or {}
    page, cls = cx.get("page"), cx.get("rubric_class")
    out = {"id": row["id"], "page": page, "cls": cls, "bucket": "c", "witnesses": [], "owned": {}, "missing": [],
           "doubts": Counter(), "census": False, "lens_part": []}
    if _target(row) != page:
        out["missing"] = [("*", "route", f"the row's route ends at {_target(row)!r}, not its cell's page {page!r}")]
        return out
    cls_dims = members.get(cls) or []
    lens_part = [d for d in cls_dims if owner_of(spec, d) == LENS_OWNER]
    owner_part = [d for d in cls_dims if owner_of(spec, d) != LENS_OWNER]
    public = cx.get("cls") == "public"
    cast = cx.get("cast") or row.get("persona") or ""

    # the lens half: every banked walk of this page whose own survey of it records the class
    cands = []
    if lens_part:
        for c in by_page.get(page, ()):
            if c.get("status") not in BANKED:
                continue
            if not any(d in (c.get("dims_graded") or []) for d in lens_part):
                continue
            if not public and cast and cast_of(c) != cast:
                out["doubts"][f"walked as {cast_of(c) or '?'}, not the row's {cast} - a page that is not public renders "
                              f"per cast, so that was another screen"] += 1
                continue
            ev, why = page_reading(c, page, cls, members, dimcls, receipts)
            if not ev:
                out["doubts"][why] += 1
                continue
            cands.append((c, ev))

    def covered(ev):
        return [d for d in lens_part if d in ev["dims"] and accounts(spec, d, ev["dims"][d], True)]

    def rank(cv):
        c, ev = cv
        return (len(covered(ev)), len(_measured(ev["dims"])), _target(c) == page, ev.get("when") or datetime.min)

    cands.sort(key=rank, reverse=True)
    whole = [cv for cv in cands if len(covered(cv[1])) == len(lens_part)]
    missing = []
    if lens_part and not whole:
        best = cands[0][1]["dims"] if cands else {}
        for d in lens_part:
            if d in best and accounts(spec, d, best[d], True):
                continue
            if d in best:
                why = f"the lens answered {d} with {best[d][0]}{' and no denominator' if best[d][0] == 'MEASURED' else ''} only"
                missing.append((d, "lens-only-judges", why))
            elif d in lens:
                why = (f"surveyed by an older lens that never asked {d}" if cands else
                       ("no usable walk of this page - " + re.sub(r"^walked as \S+,", "walked as another cast,",
                                                                 out["doubts"].most_common(1)[0][0])
                        if out["doubts"] else "no banked critic walk of this page records the class"))
                missing.append((d, "survey", why))
            else:
                missing.append((d, "no-instrument", f"the page lens never asks {d}, though the spec owns it to the lens"))

    # the owners' half: each dim the lens does not own, from its owner's record of THIS page
    for d in owner_part:
        v, src = owners.reading(page, d)
        if v and accounts(spec, d, v, False):
            out["owned"][d] = (v, src)
            continue
        if v:                                              # the owner said something that answers nothing
            missing.append((d, "no-instrument", f"{OWNER_SOURCES[src]['file']} records {d} on {page} as {v[0]} only - "
                                                f"its owner has no measured or N/A verdict for it"))
        elif d in NO_INSTRUMENT or not SOURCE_OF.get(d):
            missing.append((d, "no-instrument", src))
        elif not owners.ever_answers(SOURCE_OF[d], d, spec):
            missing.append((d, "no-instrument", f"{OWNER_SOURCES[SOURCE_OF[d]]['file']} never records {d} as MEASURED "
                                                f"or N/A on any page - its owner only judges it, so a run cannot close it"))
        else:
            s = SOURCE_OF[d]
            missing.append((d, f"{'run' if owners.covers(s, page) else 'structure'}:{s}", src))
    out["missing"] = missing
    out["lens_part"] = lens_part
    if missing:
        return out

    owned = [v for v, _ in out["owned"].values()]

    def bucket_of(ev):
        vs = [v for d, v in ev["dims"].items() if d in lens_part] + owned if ev else owned
        if any(_is_grade(v) for v in vs):
            return "a"
        return "b" if vs and all(v[0] == "N/A" for v in vs) else "c"

    # the bucket is the TOP reading's; a second walk is cited only when it gives the same answer
    top = bucket_of(whole[0][1] if whole else None)
    if top == "c":
        out["missing"] = [("*", "judged-only", "every dim is accounted for, but only by JUDGED and N/A verdicts - "
                                               "neither a grade nor an N/A for the class")]
        return out
    out.update(bucket=top, witnesses=[cv for cv in whole[:2] if bucket_of(cv[1]) == top])
    out["census"] = any(_target(c) == page for c, _ in out["witnesses"])
    return out


# ── the basis and the evidence record ─────────────────────────────────────────────────────────────────────────────
def _verdict(v) -> str:
    kind, pct, _note = v
    return f"{kind} {pct}%" if kind == "MEASURED" and pct is not None else str(kind)


def _src(c: dict, ev: dict) -> str:
    if ev["source"] == "receipt":
        when = ev["when"].isoformat(timespec="seconds") if ev.get("when") else "?"
        reused = f", reused from {ev['reused']}'s identical screen" if ev.get("reused") else ""
        return f"its survey file .tmp/batchsurvey/{ev['file']}{reused}, banked {when}"
    return "a finding the bank wrote naming this page"


def _lens_dims_of(v: dict, ev: dict) -> list:
    """The dims a witness speaks for: the lens-owned ones (an owner's dim the lens merely judged is its owner's)."""
    return sorted(d for d in ev["dims"] if d in (v.get("lens_part") or ev["dims"]))


def basis_sentence(v: dict, today: str) -> str:
    page, cls = v["page"], v["cls"]
    na = v["bucket"] == "b"

    def say(d, x):
        # an N/A carries its instrument's reason; a measurement its number; on a GRADED class an owner's note too
        if x[0] == "N/A":
            return f"{d} N/A ('{x[2][:70]}')" if x[2] else f"{d} N/A"
        return f"{d} {_verdict(x)}"

    parts = []
    for c, ev in v["witnesses"]:
        dims = ", ".join(say(d, ev["dims"][d]) for d in _lens_dims_of(v, ev))
        parts.append(f"critic row {c['id']} ({c.get('status')}, walked as {cast_of(c) or '?'}; {_src(c, ev)}) "
                     f"recorded {dims}")
    for d, (x, src) in sorted(v["owned"].items()):
        parts.append(f"{d} from its owner's record, {OWNER_SOURCES[src]['file']}: {say(d, x)}"
                     + (f" ('{x[2][:60]}')" if x[0] != "N/A" and x[2] else ""))
    head = (f"[{today}] pct -> 60. Rubric class {cls} GRADED on {page} - every dim accounted for by the instrument "
            f"that owns it" if not na else
            f"[{today}] pct -> 60. Rubric class {cls} answered N/A on {page} - every dim of the class N/A from the "
            f"instrument that owns it, so its subject is not on this page")
    lens_note = (" - the lens dims from a Playwright walk (tools/critic_walk_batch.mjs) that surveyed this page itself "
                 "with survey_ufai_rubric.js" if v["witnesses"] else "")
    return f"{head}: {'; '.join(parts)}{lens_note}; read per page by {TOOL}, held by gate {GATE_ID}."


def evidence_record(v: dict, today: str) -> dict:
    """What --check re-reads: the critic rows and dims the lens half rested on, and each owner dim's source."""
    return {"page": v["page"], "class": v["cls"], "verdict": "graded" if v["bucket"] == "a" else "n/a",
            "rows": {c["id"]: {d: _verdict(ev["dims"][d]) for d in _lens_dims_of(v, ev)} for c, ev in v["witnesses"]},
            "source": {c["id"]: (ev["file"] or "finding") for c, ev in v["witnesses"]},
            "owners": {d: {"source": src, "file": OWNER_SOURCES[src]["file"], "verdict": _verdict(x)}
                       for d, (x, src) in sorted(v["owned"].items())},
            "banked": today}


def bank(rows_by_id: dict, verdicts: list, today: str) -> tuple[list, list]:
    """Write (a) and (b) onto their rows. Returns (banked ids, ids whose basis already carried this tool's sentence)."""
    banked, kept = [], []
    for v in verdicts:
        if v["bucket"] not in ("a", "b"):
            continue
        row = rows_by_id[v["id"]]
        prev = row.get("basis") or ""
        # ★IDEMPOTENT ON THE BASIS. A row that already carries this tool's sentence keeps it - a second --apply (or a
        # row reset to specced and banked again) must not grow the basis by one more copy of the same receipt.
        if TOOL in prev:
            kept.append(row["id"])
        else:
            # APPENDED, newest LAST: validate_trajectory_registry reads the LAST "pct -> N" as the row's account of
            # itself (rule 6); a sentence put in front of an older one leaves the field disagreeing with the prose
            row["basis"] = (prev + " || " if prev else "") + basis_sentence(v, today)
        row["status"] = "locking"
        row["pct"] = 60
        art = row.setdefault("artifacts", {})
        gates = art.setdefault("gates", [])
        # locking MEANS the gate is built (validator rule 5): the row names the gate that re-reads its evidence
        if GATE_ID not in gates:
            gates.append(GATE_ID)
        if TOOL not in prev or not art.get("critic_evidence"):
            art["critic_evidence"] = evidence_record(v, today)
        banked.append(row["id"])
    return banked, kept


# ── the gate ──────────────────────────────────────────────────────────────────────────────────────────────────────
def check_rows(rows: list, crit_by_id: dict, dimcls: dict, members: dict, spec: dict | None = None,
               owners: OwnerSources | None = None) -> tuple[int, list, int]:
    """Every CX-UX row this gate holds (locking/locked, naming cx-ux-graded) must still have what it was banked on.
    Returns (held, problems, owner readings not re-checkable because their gitignored report is not on disk)."""
    spec = spec or {}
    held, problems, unverifiable = 0, [], 0
    for t in rows:
        if t.get("wave") != WAVE or t.get("status") not in ("locking", "locked"):
            continue
        art = t.get("artifacts") or {}
        if GATE_ID not in (art.get("gates") or []):
            continue
        held += 1
        cx = t.get("cx") or {}
        page, cls = cx.get("page"), cx.get("rubric_class")
        ev = art.get("critic_evidence") or {}
        if ev.get("page") != page or ev.get("class") != cls:
            problems.append(f"{t['id']}: names gate {GATE_ID} but carries no evidence record for {cls} on {page}")
            continue
        named, owned = ev.get("rows") or {}, ev.get("owners") or {}
        if not named and not owned:
            problems.append(f"{t['id']}: its evidence names no critic row and no owner")
            continue
        for cid, dims in named.items():
            c = crit_by_id.get(cid)
            if not c:
                problems.append(f"{t['id']}: critic row {cid} it was banked on is gone from the critic bank")
                continue
            if c.get("status") not in BANKED:
                problems.append(f"{t['id']}: critic row {cid} was RESET to {c.get('status')!r} - it vouches for nothing")
                continue
            if page not in (c.get("pages") or []):
                problems.append(f"{t['id']}: critic row {cid} no longer walks {page}")
                continue
            dg = set(c.get("dims_graded") or [])
            for d in dims:
                if dimcls.get(d) != cls:
                    problems.append(f"{t['id']}: dim {d} is no longer in rubric class {cls} "
                                    f"(the spec says {dimcls.get(d)!r})")
                elif d not in dg:
                    problems.append(f"{t['id']}: critic row {cid} no longer lists {d} in dims_graded")
        for d, o in owned.items():
            if dimcls.get(d) != cls:
                problems.append(f"{t['id']}: owner dim {d} is no longer in rubric class {cls}")
                continue
            if owners is None:
                continue
            src = o.get("source")
            if src not in OWNER_SOURCES:
                problems.append(f"{t['id']}: owner dim {d} rests on an unknown source {src!r}")
                continue
            if not owners.present(src):
                if OWNER_SOURCES[src]["tracked"]:
                    problems.append(f"{t['id']}: {OWNER_SOURCES[src]['file']} (tracked) is gone - {d} lost its owner's record")
                else:
                    unverifiable += 1          # a gitignored report its owner's gate rewrites; absent is not "gone"
                continue
            v, why = owners.reading(page, d)
            if not v or not accounts(spec, d, v, False):
                problems.append(f"{t['id']}: {OWNER_SOURCES[src]['file']} no longer accounts for {d} on {page}"
                                + (f" ({why})" if why else f" (it now says {v[0]})" if v else ""))
        # EVERY dim of the class must still be accounted for: a dim the class has gained since was never asked
        whole = set(members.get(cls) or [])
        for cid, dims in (list(named.items()) or [(None, {})]):
            unasked = sorted(whole - set(dims) - set(owned))
            if unasked:
                problems.append(f"{t['id']}: class {cls} now has {', '.join(unasked)}, which the evidence"
                                + (f" from {cid}" if cid else "") + " never accounted for")
        if ev.get("verdict") == "graded" and not any(str(v).startswith("MEASURED")
                                                     for dims in list(named.values()) + [{k: o.get("verdict") for k, o in owned.items()}]
                                                     for v in dims.values()):
            problems.append(f"{t['id']}: banked GRADED but its evidence holds no MEASURED dim")
    return held, problems, unverifiable


# ── run ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _save(reg: dict) -> dict:
    # through the union, at the main file's own indent: a CX row lives in its shard, and a rewrite of the main file
    # alone never reaches it (registry_io.save_doc is atomic per file) - bank_tenant_refusal_rows.py's reading
    with io.open(REGISTRY, encoding="utf-8") as fh:
        fh.readline()
        second = fh.readline()
    return _rio.save_doc(reg, indent=max(1, len(second) - len(second.lstrip(" "))) if second.strip() else 2)


def _need_label(need: str) -> str:
    if need.startswith("run:"):
        s = need[4:]
        return f"run {OWNER_SOURCES[s]['how']}"
    if need.startswith("structure:"):
        s = need[10:]
        return f"structure - {OWNER_SOURCES[s]['how']}"
    return {"survey": "a page survey (tools/critic_walk_batch.mjs)",
            "lens-only-judges": "nothing: the lens only judges it here",
            "no-instrument": "a missing instrument",
            "judged-only": "nothing: answered only by JUDGED and N/A",
            "route": "a route repair"}.get(need, need)


def run(apply: bool, receipts_dir: str, owners_dir: str) -> int:
    spec = load_spec()
    dimcls, members = spec_classes(spec)
    lens = lens_dims()
    receipts = ReceiptDir(receipts_dir)
    owners = OwnerSources(owners_dir)
    reg = _rio.load_doc()
    rows = reg["trajectories"]
    crit_rows = _rio.load_critic()["rows"]
    by_page = index_critic(crit_rows)
    ux = [t for t in rows if t.get("wave") == WAVE]
    open_rows = [t for t in ux if t.get("status") == "specced"]
    verdicts = [classify(t, by_page, members, dimcls, lens, spec, receipts, owners) for t in open_rows]
    A = [v for v in verdicts if v["bucket"] == "a"]
    B = [v for v in verdicts if v["bucket"] == "b"]
    C = [v for v in verdicts if v["bucket"] == "c"]
    st = Counter(t.get("status") for t in ux)
    print(f"CX-UX rows: {len(ux)} ({', '.join(f'{k} {n}' for k, n in sorted(st.items()))}); survey files from "
          f"{receipts_dir} ({len(receipts)}); owner records from {owners_dir} ("
          + ", ".join(f"{s} {'yes' if owners.present(s) else 'MISSING'}" for s in OWNER_SOURCES) + ")")
    print(f"  (a) bankable now - graded:    {len(A):>4}  ({sum(1 for v in A if v['owned'])} with an owner's dim; "
          f"the census's _target rule would also credit {sum(1 for v in A if v['census'])})")
    print(f"  (b) bankable now - n/a:       {len(B):>4}  ({sum(1 for v in B if v['owned'])} with an owner's dim; "
          f"the census's _target rule would also credit {sum(1 for v in B if v['census'])})")
    print(f"  (c) open:                     {len(C):>4}")
    for name, lst in (("(a) GRADED", A), ("(b) N/A", B)):
        if lst:
            print(f"\n{name} - first 8 of {len(lst)}:")
            for v in lst[:8]:
                lensd = (f"{v['witnesses'][0][0]['id']} " + ", ".join(
                    f"{d} {_verdict(x)}" for d, x in sorted(v["witnesses"][0][1]["dims"].items()))) if v["witnesses"] else ""
                ownd = ", ".join(f"{d} {_verdict(x)} ({s})" for d, (x, s) in sorted(v["owned"].items()))
                print(f"   {v['id']:9} {v['page']:52} {v['cls']:3} <- {lensd}{' + ' if lensd and ownd else ''}{ownd}")
    doubts = Counter()
    for v in verdicts:
        for why, n in v["doubts"].items():
            doubts[re.sub(r"\S+\.json", "<file>", why)] += n
    if doubts:
        print("\nINSTRUMENT DOUBTS - lens readings set aside (one count per critic row per cell):")
        for why, n in doubts.most_common(8):
            print(f"   {n:>5}  {why}")
    # (c), by WHAT would close each row: the first unmet need decides where a row is listed, every need is counted
    need_rows = defaultdict(list)
    for v in C:
        for d, need, why in v["missing"]:
            need_rows[need].append((v, d, why))
    print(f"\n(c) OPEN, by what would close it ({len(C)} rows; a row with two unmet dims counts under both):")
    for need in sorted(need_rows, key=lambda n: (-len({v['id'] for v, _, _ in need_rows[n]}), n)):
        lst = need_rows[need]
        print(f"\n  {_need_label(need)} - {len({v['id'] for v, _, _ in lst})} row(s)")
        grp = defaultdict(list)
        for v, d, why in lst:
            grp[v["page"]].append((v, d, why))
        for page in sorted(grp, key=lambda p: (-len(grp[p]), p)):
            items = grp[page]
            print(f"     {page} ({len(items)}): " + " ".join(f"{v['cls']}:{d}={v['id']}" for v, d, _ in sorted(items, key=lambda x: x[0]['cls'])))
            for why, n in Counter(w for _, _, w in items).most_common(2):
                print(f"          {n} x {why}")
    if not apply:
        print("\n(dry run - pass --apply to bank (a) and (b))")
        return 0
    banked, kept = bank({t["id"]: t for t in rows}, A + B, date.today().isoformat())
    if banked:
        written = _save(reg)
        print(f"\nBANKED {len(banked)} row(s) -> locking 60 ({len(kept)} already carried this tool's sentence); "
              f"written: {written}")
    else:
        print("\nnothing to bank")
    return 0


def run_check(owners_dir: str) -> int:
    spec = load_spec()
    dimcls, members = spec_classes(spec)
    rows = _rio.load_doc()["trajectories"]
    crit_by_id = {c["id"]: c for c in _rio.load_critic()["rows"]}
    held, problems, unverifiable = check_rows(rows, crit_by_id, dimcls, members, spec, OwnerSources(owners_dir))
    for p in problems[:40]:
        print("  FAIL " + p)
    if len(problems) > 40:
        print(f"  ... and {len(problems) - 40} more")
    print(f"{'FAIL' if problems else 'PASS'} cx-ux-graded - {held} banked CX-UX row(s) re-read against the critic bank, "
          f"the rubric spec and their owners' records; {len(problems)} lost the evidence they were banked on"
          + (f"; {unverifiable} owner reading(s) not re-read (their gitignored report is not on disk - its own gate "
             f"rewrites it)" if unverifiable else ""))
    return 1 if problems else 0


# ── self-test: synthetic fixtures, each bucket proved and each guard given teeth ──────────────────────────────────
class _FakeReceipts:
    def __init__(self, files: dict):
        self.files = files                                     # {(rid, page): (survey, mtime)}

    def __len__(self):
        return len(self.files)

    def get(self, rid, page):
        hit = self.files.get((rid, page))
        return (hit[0], hit[1], receipt_name(rid, page)) if hit else None


def _self_test() -> int:
    import copy
    fails: list = []
    L = {"owner": "rubric-lens", "verdict": "measured"}
    spec = {"_meta": {},
            "A1": dict(L, **{"class": "A"}), "A2": dict(L, **{"class": "A"}),
            "DD1": dict(L, **{"class": "DD"}), "DD2": dict(L, **{"class": "DD"}),
            "AI1": dict(L, **{"class": "AI"}), "AI6": {"class": "AI", "owner": "ai-write-provenance-validator", "verdict": "measured"},
            "I1": {"class": "I", "owner": "battery", "verdict": "judged"}, "I2": dict(L, **{"class": "I"}),
            "J1": dict(L, **{"class": "J"}), "J2": {"class": "J", "owner": "rubric-lens", "verdict": "judged"},
            "J3": {"class": "J", "owner": "journey-validator", "verdict": "measured"},
            "H1": dict(L, **{"class": "H"}), "H2": {"class": "H", "owner": "rubric-lens", "verdict": "judged"},
            "S1": dict(L, **{"class": "S"}), "S2": {"class": "S", "owner": "family-sweep", "verdict": "measured"},
            "CV1": {"class": "CV", "owner": "journey-validator", "verdict": "measured"}}
    dimcls, members = spec_classes(spec)
    lens = lens_dims("M('A1', x) M('A2', x) NA('DD1', x) NA('DD2', x) NA('AI1', x) J('I1', x) NA('I2', x) "
                     "M('J1', x) J('J2', x) M('H1', x) J('H2', x) M('S1', x)")
    if lens != {"A1", "A2", "DD1", "DD2", "AI1", "I1", "I2", "J1", "J2", "H1", "H2", "S1"}:
        fails.append(f"the lens reader must find every M/J/NA dim, got {sorted(lens)}")
    T = datetime(2026, 10, 13, 12, 0, 0)
    ABOUT, FEED, HIVE, CALC, TERMS = ("about/index.html", "feedback/index.html", "hive.html",
                                      "tools/oee-calculator/index.html", "terms-of-service/index.html")

    def dim(d, kind, pct=None, note=""):
        return {"dim": d, "kind": kind, "pct": pct, "note": note}

    def survey(pid, dims, **kw):
        return dict({"pageId": pid, "dims": dims, "_denied": False}, **kw)

    every = ["A1", "A2", "DD1", "DD2", "AI1", "I1", "I2", "J1", "J2", "H1", "H2", "S1", "IN-MOTION"]
    crit = [
        # W1 walked about -> terms -> hive; on ABOUT: A1 measured, DD all N/A, AI1 N/A, I judged/N/A, J N/A, H judged/N/A
        {"id": "W1", "status": "critiqued", "pages": [ABOUT, TERMS, HIVE], "cell": "phone-390|anon|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
        # W2 walked hive -> feedback (the census's _target is FEEDBACK) and its union lists A1 - measured on HIVE only
        {"id": "W2", "status": "improving", "pages": [HIVE, FEED], "cell": "phone-390|worker|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
        # W3 was RESET: its survey of the calculator would grade A, but a pending row vouches for nothing (its
        # dims_graded is kept here on purpose, so the STATUS is what refuses it, not an empty list)
        {"id": "W3", "status": "pending", "pages": [CALC], "cell": "phone-390|anon|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
        # W4's calculator survey file is NEWER than its bank - a later run the bank never took
        {"id": "W4", "status": "critiqued", "pages": [CALC], "cell": "phone-390|anon|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
        # W5's calculator survey file was access-denied; W6's has A1 MEASURED with a null pct (a denominator of 0)
        {"id": "W5", "status": "critiqued", "pages": [CALC], "cell": "phone-390|anon|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
        {"id": "W6", "status": "critiqued", "pages": [CALC], "cell": "phone-390|anon|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
        # W7 has no survey file, but the bank wrote findings naming the page - the durable per-page record
        {"id": "W7", "status": "critiqued", "pages": ["learn/x/index.html"], "cell": "phone-390|anon|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(),
         "findings": [{"evidence": "x: A1 70% - small type"}, {"evidence": "x: A2 40% - long sentences"}]},
        # W8 walked hive as a worker; W9 as a supervisor - the hive row's own cast
        {"id": "W8", "status": "critiqued", "pages": [HIVE], "cell": "phone-390|worker|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
        {"id": "W9", "status": "critiqued", "pages": [HIVE], "cell": "phone-390|supervisor|browser|operate",
         "dims_graded": every, "banked_at": T.isoformat(), "findings": []},
    ]
    na_dd = [dim("DD1", "N/A", note="not a KPI dashboard"), dim("DD2", "N/A", note="no stat tiles")]
    about_dims = ([dim("A1", "MEASURED", 80), dim("A2", "N/A")] + na_dd
                  + [dim("AI1", "N/A", note="no AI surface"), dim("I1", "JUDGED"), dim("I2", "N/A"),
                     dim("J1", "N/A", note="no first-run state"), dim("J2", "N/A", note="no undo-able action"),
                     dim("H1", "N/A"), dim("H2", "JUDGED"), dim("S1", "N/A", note="no family")])
    pre = T - timedelta(minutes=5)
    files = {
        ("W1", ABOUT): (survey("about", about_dims), pre),
        ("W1", TERMS): (survey("terms-of-service", about_dims), pre),
        ("W1", HIVE): (survey("hive", [dim("A1", "MEASURED", 100)]), pre),
        ("W2", HIVE): (survey("hive", [dim("A1", "MEASURED", 90), dim("A2", "MEASURED", 90)]), pre),
        ("W3", CALC): (survey("oee-calculator", [dim("A1", "MEASURED", 70), dim("A2", "N/A")]), pre),
        ("W4", CALC): (survey("oee-calculator", [dim("A1", "MEASURED", 70), dim("A2", "N/A")]), T + timedelta(hours=1)),
        ("W5", CALC): (survey("oee-calculator", [dim("A1", "MEASURED", 70), dim("A2", "N/A")], _denied=True), pre),
        ("W6", CALC): (survey("oee-calculator", [dim("A1", "MEASURED", None), dim("A2", "N/A")]), pre),
        ("W8", HIVE): (survey("hive", [dim("A1", "MEASURED", 95), dim("A2", "N/A")]), pre),
        ("W9", HIVE): (survey("hive", [dim("A1", "MEASURED", 85), dim("A2", "N/A")]), pre),
    }
    receipts = _FakeReceipts(files)
    # the owners: J3 and AI6 recorded for ABOUT; for TERMS the journey record is ABSENT (one owner dim missing) and the
    # provenance record exists only under a DIFFERENT page's path; the board answers I1 for ABOUT only as JUDGED
    owner_data = {
        "journey": {"pages": {ABOUT: {"J3": {"verdict": "N/A", "pct": None, "note": "no destructive handler"}},
                              "privacy-policy/index.html": {"J3": {"verdict": "N/A", "pct": None, "note": "x"}}}},
        "provenance": {"pages": {ABOUT: {"AI6": {"verdict": "N/A", "pct": None, "note": "reaches no AI writer"}},
                                 "privacy-policy/index.html": {"AI6": {"verdict": "N/A", "pct": None, "note": "x"}}}},
        "board": {"pages": {ABOUT: {"dims": [{"dim": "I1", "kind": "JUDGED", "pct": None, "note": "no CWV"}]}}},
        "corpus": None, "cta": None, "chrome": {"pages": {}},
    }
    owners = OwnerSources(data=owner_data, cta_roster={})

    def row(rid, page, k, cls="public", cast="anon"):
        return {"id": rid, "wave": WAVE, "status": "specced", "pct": 5, "pages": [page], "persona": cast,
                "cx": {"kind": "cube-ux", "cls": cls, "page": page, "rubric_class": k, "cast": cast}}

    rows = [row("CX1", ABOUT, "A"), row("CX2", ABOUT, "DD"), row("CX3", ABOUT, "AI"), row("CX4", ABOUT, "I"),
            row("CX5", FEED, "A"), row("CX6", CALC, "A"), row("CX7", "learn/x/index.html", "A"),
            row("CX8", HIVE, "A", cls="production", cast="supervisor"), row("CX9", ABOUT, "CV"),
            row("CX10", ABOUT, "J"), row("CX11", TERMS, "J"), row("CX12", TERMS, "AI"), row("CX13", ABOUT, "H"),
            row("CX14", ABOUT, "S")]
    by_page = index_critic(crit)
    got = {r["id"]: classify(r, by_page, members, dimcls, lens, spec, receipts, owners) for r in rows}
    b = {k: v["bucket"] for k, v in got.items()}
    needs = {k: [m[1] for m in v["missing"]] for k, v in got.items()}

    if b["CX1"] != "a" or [c["id"] for c, _ in got["CX1"]["witnesses"]] != ["W1"]:
        fails.append(f"(a): A1 MEASURED 80% + A2 N/A on about itself must bank GRADED on W1, got {b['CX1']}")
    if b["CX2"] != "b" or "not a KPI dashboard" not in basis_sentence(got["CX2"], "2026-11-03"):
        fails.append(f"(b): every DD dim N/A on about must bank N/A with the survey's reason, got {b['CX2']}")
    if b["CX3"] != "b" or "AI6" not in got["CX3"]["owned"]:
        fails.append(f"(b) mixed: AI1 N/A (lens) + AI6 N/A (its owner's record of about) must bank N/A, got {b['CX3']}")
    if b["CX4"] != "c" or "no-instrument" not in needs["CX4"]:
        fails.append("a battery dim the board records only as JUDGED is not answered - I must stay open, named as "
                     f"its owner's gap, got {b['CX4']} {needs['CX4']}")
    if b["CX5"] != "c":
        fails.append("DIFFERENT PAGE: A measured on hive must not bank feedback, though the census's _target rule "
                     f"(W2 ends at feedback, its union lists A1) would - got {b['CX5']}")
    if b["CX6"] != "c":
        fails.append(f"a reset row, a newer-than-bank file, a denied file and a null pct must all be refused, got {b['CX6']}")
    d6 = " | ".join(got["CX6"]["doubts"])
    for needle in ("newer than the bank", "access-denied"):
        if needle not in d6:
            fails.append(f"the refusal must be reported as an instrument doubt ({needle!r} missing from {d6!r})")
    if b["CX7"] != "a" or got["CX7"]["witnesses"][0][1]["source"] != "finding":
        fails.append(f"findings the bank wrote naming the page are per-page MEASURED evidence, got {b['CX7']}")
    if b["CX8"] != "a" or [c["id"] for c, _ in got["CX8"]["witnesses"]] != ["W9"]:
        fails.append("a gated page banks only on its own cast's walk (the supervisor's W9), never the worker's W8 or "
                     f"the anon W1 - got {b['CX8']} {[c['id'] for c, _ in got['CX8']['witnesses']]}")
    if b["CX9"] != "c" or needs["CX9"] != ["structure:cta"] and needs["CX9"] != ["run:cta"]:
        fails.append(f"a class the lens never asks (CV) stays open on its owner's record, got {b['CX9']} {needs['CX9']}")
    if b["CX10"] != "b" or "J3" not in got["CX10"]["owned"]:
        fails.append(f"J1/J2 N/A (lens) + J3 N/A (the journey validator's record of about) must bank N/A, got {b['CX10']}")
    if b["CX11"] != "c" or not any(n == "run:journey" for n in needs["CX11"]):
        fails.append("ONE OWNER DIM MISSING: J on terms has J1/J2 from the lens but no J3 record of terms - it must not "
                     f"bank, and must name the journey validator's run, got {b['CX11']} {needs['CX11']}")
    if b["CX12"] != "c" or not any(n == "run:provenance" for n in needs["CX12"]):
        fails.append("OWNER RECORD FOR A DIFFERENT PAGE: AI6 is recorded for privacy-policy, not terms - terms' AI must "
                     f"not bank, got {b['CX12']} {needs['CX12']}")
    if b["CX13"] != "c" or "judged-only" not in needs["CX13"]:
        fails.append("H1 N/A + H2 JUDGED (a lens-owned judged dim) accounts for H but is neither a grade nor an N/A - "
                     f"open as judged-only, got {b['CX13']} {needs['CX13']}")
    if b["CX14"] != "c" or needs["CX14"] != ["run:chrome"]:
        fails.append("S2's owner (the shared-chrome record) has no reading of about here - S must stay open and name "
                     f"its owner's run, got {b['CX14']} {needs['CX14']}")
    # once the chrome record measures S2 on about, S1 N/A (lens) + S2 MEASURED (its owner) is GRADED; a record of
    # S2 for a DIFFERENT page answers nothing here; an app page is outside what that owner can ever record
    od_s = copy.deepcopy(owner_data)
    od_s["chrome"] = {"pages": {ABOUT: {"S2": {"verdict": "MEASURED", "pct": 80, "note": "4/5 parts: footer"}}}}
    s_ok = classify(row("CX16", ABOUT, "S"), by_page, members, dimcls, lens, spec, receipts,
                    OwnerSources(data=od_s, cta_roster={}))
    s_other = classify(row("CX17", TERMS, "S"), by_page, members, dimcls, lens, spec, receipts,
                       OwnerSources(data=od_s, cta_roster={}))
    s_app = classify(row("CX18", HIVE, "S", cls="production", cast="supervisor"), by_page, members, dimcls, lens,
                     spec, receipts, OwnerSources(data=od_s, cta_roster={}))
    if s_ok["bucket"] != "a" or s_ok["owned"].get("S2", (None,))[0][:2] != ("MEASURED", 80):
        fails.append(f"S2 MEASURED in the chrome record of about must grade S there, got {s_ok['bucket']} {s_ok['missing']}")
    if s_other["bucket"] != "c" or [m[1] for m in s_other["missing"]] != ["run:chrome"]:
        fails.append(f"S2 recorded for about must not answer terms, got {s_other['bucket']} {s_other['missing']}")
    if not any(m[1] == "structure:chrome" for m in s_app["missing"]):
        fails.append(f"an app page is outside the static chrome record - a structure gap, got {s_app['missing']}")
    # the board has no record of TERMS: if it has only ever JUDGED I1, a run cannot help (a missing instrument); once it
    # MEASURES I1 on some page, a run on terms is the move
    i_terms = row("CX15", TERMS, "I")
    n1 = [x[1] for x in classify(i_terms, by_page, members, dimcls, lens, spec, receipts, owners)["missing"]]
    od2 = copy.deepcopy(owner_data)
    od2["board"]["pages"][HIVE] = {"dims": [{"dim": "I1", "kind": "MEASURED", "pct": 90, "note": "CLS 0.02"}]}
    n2 = [x[1] for x in classify(i_terms, by_page, members, dimcls, lens, spec, receipts,
                                 OwnerSources(data=od2, cta_roster={}))["missing"]]
    if n1 != ["no-instrument"] or n2 != ["run:board"]:
        fails.append("an owner that has only ever JUDGED a dim is a missing instrument, not a run - and once it measures "
                     f"the dim elsewhere, a run on this page is the move: got {n1} then {n2}")
    s3 = basis_sentence(got["CX3"], "2026-11-03")
    if not s3.startswith("[2026-11-03] pct -> 60.") or "W1" not in s3 or "AI6" not in s3 or "ai_write_provenance_report.json" not in s3:
        fails.append(f"the basis must start '[date] pct -> 60.' and name the critic row, the owner's file and each dim: {s3[:200]}")

    # the owners' readers, each on its own page only
    corpus = OwnerSources(data={"corpus": {"corpus": {
        "hive.html": {"primitives": {"simple-card": [{"missing_required": []}, {"missing_required": ["sc-label"]}]}},
        "achievements.html": {"primitives": {"simple-card": [], "sum-card": []}}}}})
    if corpus.reading("hive.html", "S3")[0][:2] != ("MEASURED", 50) or corpus.reading("achievements.html", "S3")[0][0] != "N/A":
        fails.append("S3 from the corpus: 1 of 2 whole instances is 50%, a page with no card primitive is N/A")
    if corpus.reading("about/index.html", "S3")[0] is not None:
        fails.append("S3 for a page the corpus never scanned must be no record, never an N/A")
    cta = OwnerSources(data={"cta": {"results": [{"page": "index", "dead": False}, {"page": "index", "dead": True},
                                                 {"page": "feed", "verdict": "walk-error: x", "dead": False}]}},
                       cta_roster={"index.html": "index", "public-feed.html": "feed"})
    if cta.reading("index.html", "CV1")[0][:2] != ("MEASURED", 50) or cta.reading("public-feed.html", "CV1")[0] is not None:
        fails.append("CV1 from the CTA report: 1 of 2 clicks alive is 50%; a walk-error is no reading")
    # the prover's per-page walk record: walked at both viewports with no primary CTA is N/A; a walk that errored or
    # missed a viewport is no reading; a page the record does not name is no reading
    roster = {"about/index.html": "about", "terms-of-service/index.html": "terms", "privacy-policy/index.html": "privacy"}
    walks = OwnerSources(data={"cta": {"results": [], "pages": {
        "about": {"walked": {"390": {"ctas": 0}, "1280": {"ctas": 0}}},
        "terms": {"walked": {"390": {"ctas": 0}, "1280": {"error": "timeout"}}},
        "privacy": {"walked": {"390": {"ctas": 0}}}}}}, cta_roster=roster)
    if (walks.reading("about/index.html", "CV1")[0] or ("",))[0] != "N/A":
        fails.append("CV1: a page walked at 390 and 1280 with no primary CTA must read N/A from the walk record")
    if walks.reading("terms-of-service/index.html", "CV1")[0] is not None or \
            walks.reading("privacy-policy/index.html", "CV1")[0] is not None:
        fails.append("CV1: a walk that errored, or one that never reached a viewport, must not read as N/A")
    # CV2/CV3 from the per-page conversion walk, each page under its own path
    conv = OwnerSources(data={"conversion": {"pages": {ABOUT: {
        "CV2": {"verdict": "N/A", "pct": None, "note": "no auth wall reachable - 0 link(s) to app pages followed"},
        "CV3": {"verdict": "MEASURED", "pct": 83, "note": "5/6 steps"}}}}})
    if (conv.reading(ABOUT, "CV2")[0] or ("",))[0] != "N/A" or (conv.reading(ABOUT, "CV3")[0] or ("", 0))[:2] != ("MEASURED", 83):
        fails.append(f"CV2/CV3 from the conversion record of about: {conv.reading(ABOUT, 'CV2')} {conv.reading(ABOUT, 'CV3')}")
    if conv.reading(TERMS, "CV3")[0] is not None:
        fails.append("CV3 walked from about must not answer terms")
    # F2 from the live axe scan: a scanned page with rule totals answers; a page scanned before the totals were
    # recorded, a skipped page, and a skipped run do not
    ax = OwnerSources(data={"axe": {"detail": {
        ABOUT: {"skipped": False, "F2": {"verdict": "MEASURED", "pct": 100, "note": "31/31 rules pass"}},
        TERMS: {"skipped": False, "nodes": 0},
        FEED: {"skipped": True, "reason": "auth gate"}}}})
    if (ax.reading(ABOUT, "F2")[0] or ("", 0))[:2] != ("MEASURED", 100):
        fails.append(f"F2 from the axe record of about must read MEASURED 100: {ax.reading(ABOUT, 'F2')}")
    if ax.reading(TERMS, "F2")[0] is not None or ax.reading(FEED, "F2")[0] is not None:
        fails.append("F2: a page scanned without rule totals, or skipped, must be no reading")
    if OwnerSources(data={"axe": {"skipped": True, "reason": "GoTrue down"}}).reading(ABOUT, "F2")[0] is not None:
        fails.append("F2: a skipped axe run is evidence of nothing")

    # --apply: appended LAST, gate named, idempotent on a second run
    reg_rows = copy.deepcopy(rows)
    reg_rows[0]["basis"] = "[2026-10-26] pct -> 5. seeded"
    by_id = {r["id"]: r for r in reg_rows}
    vs = list(got.values())
    banked, kept = bank(by_id, vs, "2026-11-03")
    want_banked = ["CX1", "CX10", "CX2", "CX3", "CX7", "CX8"]
    if sorted(banked) != want_banked or kept:
        fails.append(f"--apply must bank exactly the (a) and (b) rows {want_banked}, got {sorted(banked)} kept {kept}")
    r1 = by_id["CX1"]
    last = re.findall(r"pct\s*->\s*(\d+)", r1["basis"])
    if r1["status"] != "locking" or r1["pct"] != 60 or last[-1] != "60" or not r1["basis"].startswith("[2026-10-26]"):
        fails.append("the sentence must be APPENDED (the validator reads the LAST pct ->) and the row set to locking 60")
    gates1 = (r1.get("artifacts") or {}).get("gates") or []
    if GATE_ID not in gates1:
        fails.append("a locking row must name the gate that holds it")
    once = r1["basis"]
    banked2, kept2 = bank(by_id, vs, "2026-11-04")
    if by_id["CX1"]["basis"] != once or sorted(kept2) != sorted(banked2) or gates1.count(GATE_ID) != 1:
        fails.append("a second --apply must not duplicate the basis or the gate")

    # --check: green on intact evidence, red on each way it can be lost
    crit_by_id = {c["id"]: copy.deepcopy(c) for c in crit}
    held, probs, _u = check_rows(list(by_id.values()), crit_by_id, dimcls, members, spec, owners)
    if held != 6 or probs:
        fails.append(f"--check must hold the 6 banked rows green, got held={held} {probs}")

    def red(mutate, needle, what):
        cb = copy.deepcopy(crit_by_id)
        sp = copy.deepcopy(spec)
        od = copy.deepcopy(owner_data)
        mutate(cb, sp, od)
        dc, mb = spec_classes(sp)
        _h, p, _u2 = check_rows(list(by_id.values()), cb, dc, mb, sp, OwnerSources(data=od, cta_roster={}))
        if not any(needle in x for x in p):
            fails.append(f"--check teeth: {what} must FAIL (looked for {needle!r}, got {p})")

    red(lambda cb, sp, od: cb["W1"].update(status="pending", dims_graded=[]), "RESET", "a critic row reset to pending")
    red(lambda cb, sp, od: cb["W1"]["dims_graded"].remove("A1"), "no longer lists A1", "a dim gone from dims_graded")
    red(lambda cb, sp, od: sp.update(DD3=dict(L, **{"class": "DD"})), "now has DD3",
        "a class that gained a dim the evidence never accounted for")
    red(lambda cb, sp, od: sp["A1"].update({"class": "Z"}), "no longer in rubric class A", "a dim moved out of its class")
    red(lambda cb, sp, od: cb.pop("W1"), "gone from the critic bank", "a critic row deleted")
    red(lambda cb, sp, od: cb["W1"].update(pages=[HIVE]), "no longer walks", "a critic row whose path dropped the page")
    red(lambda cb, sp, od: od["journey"]["pages"].pop(ABOUT), "no longer accounts for J3",
        "an owner's record of the page gone from its report")
    red(lambda cb, sp, od: od["provenance"]["pages"][ABOUT]["AI6"].update(verdict="JUDGED"), "no longer accounts for AI6",
        "an owner's verdict that no longer answers the dim")

    print("FAIL bank_cx_ux_rows self-test - " + "; ".join(fails) if fails else
          "self-test OK: (a) on a measured dim of the page itself, (b) only when EVERY dim is N/A - the lens's and its "
          "owners' (AI1 + AI6, J1-J2 + J3) - with each reason; an owner dim missing for the page, or recorded only for a "
          "DIFFERENT page, keeps the row open and names the owner's run; S2 graded from the shared-chrome record of the "
          "page itself (never another page's, an app page a structure gap); a battery dim the board only judges and a "
          "judged-only class stay open; a class graded on a DIFFERENT page refused (where the census's "
          "_target rule would credit it); a reset row / a newer-than-bank file / a denied file / a null pct refused; a "
          "gated page banked only on its own cast; the S3 and CV1 readers per page; the basis appended once; and --check "
          "reddens on a reset row, a lost dim, a grown class, a moved dim, a deleted row, a dropped page, a lost owner "
          "record and an owner verdict that no longer answers")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="bank (a) and (b)")
    ap.add_argument("--check", action="store_true", help="the gate: exit 1 when a banked row lost its evidence")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--receipts", default=str(RECEIPTS), help="the walk survey files (default .tmp/batchsurvey)")
    ap.add_argument("--owners", default=str(ROOT), help="where the owners' per-page records are (default: repo root)")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if a.check:
        return run_check(a.owners)
    return run(a.apply, a.receipts, a.owners)


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
