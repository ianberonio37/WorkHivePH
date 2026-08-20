#!/usr/bin/env python3
"""validate_live_mcp_bank.py — a green scenario must carry TYPED evidence, and that evidence EXPIRES.

BORN FROM A FALSE 343 (2026-08-04). The live-MCP bank reported 343 green / 0 owed. Ian: "I don't believe
what you have accomplished all the flywheel walks owed." He was right, and the mechanism was precise:

    LM-A-discovery-market-anon-populated was green on the oracle "the surface renders real rows and every
    visible number matches its source of truth". Walking it live showed the credits-back chip had
    DISAPPEARED from every priced listing — service_knob('reward_max_per_listing') returns NULL meaning
    "no cap" (the function says so in its own comment), the client read it through Number(null) -> 0, and
    Math.min(raw, 0) zeroed every chip. The one place a buyer meets the 10% reward was gone, and the page
    still rendered perfectly.

So the count was never the problem. The problems were:
  1. a green cell carried NO TYPED EVIDENCE — nobody could ask "green because of what?"
  2. a green cell NEVER EXPIRED — the code underneath could change and the row stayed green forever
  3. a STRUCTURAL probe was allowed to satisfy a BEHAVIOURAL oracle ("renders fine" vs "the number is right")

This gate fixes all three, mechanically. The anti-drift doctrine was already written down in
DEEPWALK_JOURNEY_BUGHUNT_ROADMAP.md §0 and CORRECTNESS_SCOREBOARD.md §6.0 — "COVERED requires EVIDENCE, a
cited gate name OR a live-walk ledger ref" — and nothing enforced it on the registry. Prose does not hold.

THE RULES (each with a self-test that proves it fires):
  R1  a non-owed row carries evidence{kind, ref, asserts} with a non-empty `asserts`
  R2  kind=gate  -> the ref names a gate id that exists in run_platform_checks.py
  R3  kind=live-walk -> the ref carries a date and a URL that exists in the SURFACES table
  R4  evidence.sha still matches a fresh hash of evidence.depends_on -> else the row is STALE
  R5  forward-only ratchet on green, with STALE excluded from the denominator so drift is visible
  R6  a behavioural `asserts` may not rest on purely structural evidence (the exact false-343 defect)
  R7  a LAYER or SEAM row must depend on the artifacts its layer actually rests on, not on whichever
      page was open when someone walked it

STALE is a first-class state and deliberately not "owed": it WAS true, the ground moved, re-walk it.
This is the same source_sha idea validate_substrate_freshness.py already uses for substrate chunks — a
proven pattern here, applied to the claim instead of the chunk.

Usage:  python tools/validate_live_mcp_bank.py [--selftest] [--report] [--accept]
"""
import hashlib
import json
import os
import re
import shutil
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")
BASELINE = os.path.join(ROOT, "live_mcp_bank_baseline.json")
CHECKS = os.path.join(ROOT, "run_platform_checks.py")

VALID_KINDS = {"live-walk", "gate", "psql", "declared-na"}

# A claim about a VALUE or a BEHAVIOUR cannot be settled by "the page rendered". These verbs are the tell.
BEHAVIOURAL_RE = re.compile(
    r"\bmatch(es|ing)?\b|\bequals?\b|\bcorrect\b|\bsame as\b|\bagrees?\b|\breturns?\b|\bwrites?\b|"
    r"\brefus(e|es|al)\b|\bblocks?\b|\bprevents?\b|\bconserv|\bbalance|\bexactly\b", re.I)
# What a purely structural probe can actually establish.
STRUCTURAL_ONLY_RE = re.compile(
    r"renders?|no overflow|unclipped|chars of visible text|no error chrome|no unrendered junk|"
    r"structural half", re.I)


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def rows_of(reg):
    return reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg


# ── R7 · WHAT EACH LAYER ACTUALLY RESTS ON ──────────────────────────────────────────────────────
# The single source of truth for both this gate and tools/verify_layer_invariants.py, which imports
# it. Two copies of this map would drift, and a drifted copy means the gate enforces one thing while
# the banker writes another.
LAYER_DEPS = {
    "layer_db":             ["supabase/migrations"],
    "layer_cron":           ["supabase/migrations"],
    "layer_realtime":       ["supabase/migrations"],
    "layer_storage":        ["supabase/migrations"],
    "layer_edge":           ["supabase/functions", "supabase/migrations"],
    "layer_ai":             ["supabase/functions"],
    "layer_gateway":        ["supabase/functions"],
    "layer_client":         ["marketplace.html", "utils.js"],
    "seam_edge_db":         ["supabase/functions", "supabase/migrations"],
    "seam_trigger_view":    ["supabase/migrations"],
    "seam_cron_db":         ["supabase/migrations"],
    "seam_gateway_edge":    ["supabase/functions"],
    "seam_realtime_client": ["supabase/migrations", "marketplace.html"],
    "seam_client_gateway":  ["marketplace.html", "utils.js"],
    "seam_storage_client":  ["supabase/migrations", "marketplace.html"],
}

# ── R7 FOR THE PAGE BANKS ────────────────────────────────────────────────────────────────────────
# The map above is keyed on the MARKETPLACE bank's surface ids ("layer_db", "seam_edge_db", ...). The 22
# page banks name their surface after the PAGE ("achievements", "logbook", ...) and carry the layer in
# the row's `subject.name` instead ("db (17 tables/views)", "gateway (PostgREST)", "client", ...). So the
# `surface in LAYER_DEPS` test below never matched a page-bank row, and R7 — the rule that exists because
# 136 DB invariants once declared they rested on marketplace.html — was silent on all 440 of them.
# Measured when this map was added: 92 GREEN page-bank layer rows declared a page + utils.js anchor for a
# db / gateway / edge / ai / auth claim. Every one is a false green in the freshness sense, which is the
# expensive direction: a migration that changes a grant expires NONE of them.
#
# WHY THIS IS A SECOND MAP AND NOT AN ALIAS OF THE FIRST — the thing that made a blind reuse unsafe:
# "gateway" DENOTES DIFFERENT ARTIFACTS IN THE TWO BANKS. In the marketplace bank layer_gateway is the
# edge-function front door, hence ["supabase/functions"]. In the page banks the anatomy says
# "L2 gateway (PostgREST reads)" / "gateway (grade_skill_exam RPC)" / "gateway (budget RPC)" — PostgREST
# and its RPCs, whose contract is DEFINED BY THE SCHEMA. Anchoring those to supabase/functions would
# have replaced one wrong anchor with a differently wrong one, which is worse than the noise it fixed.
# Two maps in one file with the distinction written down beats one map that quietly means two things.
PAGE_LAYER_DEPS = {
    # the layer word (first token of subject.name, lowercased) -> what a claim at that layer rests on.
    # "<page>" is substituted with the bank's own page file, so a CLIENT claim still rests on its page.
    "client":        ["<page>", "utils.js"],   # markup + shared client library: the page IS the subject
    "db":            ["supabase/migrations"],
    "cron":          ["supabase/migrations"],  # sweep-fed views: the schedule and the view are schema
    "realtime":      ["supabase/migrations"],  # publication + RLS decide what a channel may carry
    "storage":       ["supabase/migrations"],
    "auth":          ["supabase/migrations"],  # the anon boundary is RLS, not page code
    "gateway":       ["supabase/migrations"],  # PostgREST + RPCs (see the note above: NOT functions)
    "edge":          ["supabase/functions", "supabase/migrations"],
    "ai":            ["supabase/functions"],   # the prompt/gateway code, not the schema
    "external-send": ["supabase/functions"],   # the send transport lives in a function
    # cdn and print rest on the PAGE: the page pins the SRI hashes and carries the @media print rules.
    "cdn":           ["<page>", "utils.js"],
    "print":         ["<page>", "utils.js"],
}


def page_layer_deps(page_file, subject_name):
    """-> the anchor a page-bank layer row must declare, or None if the layer word is unmapped.

    Unmapped is deliberately a NO-OP rather than a failure: a new anatomy word should not brick the
    gate, and R8/R10 already refuse un-grounded subjects at build time.
    """
    word = re.split(r"[^a-z\-]", str(subject_name or "").strip().lower())
    word = next((w for w in word if w), "")
    spec = PAGE_LAYER_DEPS.get(word)
    if not spec:
        return None
    return sorted(page_file if d == "<page>" else d for d in spec)


def sha_of(paths):
    """Hash the files a claim depends on. Missing file => its own marker, so a DELETED dependency
    invalidates the claim rather than silently hashing to nothing.

    A dependency may be a DIRECTORY, and for the DB-layer rows it must be. Those rows assert things
    like "every grant has a caller-aware policy behind it" or "the ledger conserves credits" — claims
    about the SCHEMA, which lives in supabase/migrations, not in any page. They were declared against
    marketplace-seller.html + utils.js, which is wrong in both directions:

      noisy   — every page edit expired a claim the page cannot affect (this is most of the 124
                layer/seam rows sitting stale right now)
      unsafe  — and the direction that actually costs something: a MIGRATION could change a grant and
                NOT expire the claim. Mig 50 revoked a SELECT this session; under the old declaration
                not one grant_matches_policy row would have gone stale. A false green with no signal.

    A directory hashes its files' relative paths AND contents, recursively and in sorted order, so
    adding a migration, editing one, or deleting one all move the hash. Over-expiry is the cheap
    direction — stale is excluded from the denominator, so it costs a re-walk, never a wrong number.
    """
    h = hashlib.sha256()
    for p in sorted(paths or []):
        fp = os.path.join(ROOT, p)
        h.update(p.encode("utf-8"))
        if os.path.isdir(fp):
            for root, dirs, files in os.walk(fp):
                dirs.sort()
                for name in sorted(files):
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, ROOT).replace("\\", "/")
                    h.update(rel.encode("utf-8"))
                    with open(full, "rb") as f:
                        h.update(f.read())
        elif os.path.exists(fp):
            with open(fp, "rb") as f:
                h.update(f.read())
        else:
            h.update(b"<<MISSING>>")
    return h.hexdigest()[:16]


# ── R4b · A WHOLE-FILE HASH IS TOO BLUNT FOR A SHARED LIBRARY ────────────────────────────────────
# The file hash above is right for a page: edit marketplace.html and every claim about marketplace.html
# should be re-walked. It is WRONG for utils.js, which nearly every row depends on. Adding one new
# helper to it -- `whReadError`, appended, touching nothing -- expired 402 of 435 green rows in one
# commit (2026-08-04). None of those claims could possibly have been affected: "the seller edit form
# refuses a blank title" does not become doubtful because a function it never calls now exists.
#
# An instrument that cannot tell "the code this claim rests on changed" from "unrelated code was added
# beside it" is not measuring freshness, it is measuring file mtime with extra steps -- and the cost is
# paid in re-walks that re-confirm what nobody doubted, which is exactly how a discipline stops being
# followed.
#
# So a row may ALSO carry `fn_digests`: a map of {"utils.js::whWriteError": "<digest>", ...} plus the
# file's TOP-LEVEL code (everything outside any function body) under "::toplevel". A row stays fresh if
# every entry it recorded is still byte-identical. A NEW function is absent from the map, so it expires
# nothing; a CHANGED or DELETED one expires the row, which is the case that matters. Top-level code is
# included because that is where a wrapper, a monkey-patch or an assignment could change behaviour
# without touching any function body.
#
# This is a WIDENING of what counts as fresh, so it must not become a way to launder a real change:
# the map is written at BANK time from the code as it then was, never recomputed from the current file,
# and a row with no map falls back to the whole-file hash. The self-test proves both directions.
# INDENTED, because the pages are where the code actually lives. Until 2026-08-05 this matched only
# `^function` and only in `.js` files, so every .html dependency fell back to the whole-file hash --
# the exact blunt instrument R4b exists to replace. One touch anywhere in marketplace.html expired
# every row that named it, including rows whose claim was about a function I had not been near.
# The pages wrap everything in an IIFE, so their declarations are indented; allowing leading
# whitespace also matches NESTED functions, which is handled by dropping contained spans below.
#
# A v3 WAS TRIED AND REJECTED (2026-08-05), and the reason is worth keeping. utils.js injects its
# shared stylesheet from an anonymous top-level IIFE, which lands in the single `toplevel` unit — so
# adding one @media block to that CSS expired 831 rows whose claims had nothing to do with it. The
# obvious fix is to digest each top-level IIFE separately. It is the WRONG fix: every page wraps its
# ENTIRE script in one such IIFE, so that unit would cover the whole file and any page edit would
# expire every row naming that page — strictly worse than today. The self-test caught it ("adding a
# new function must not expire a row" went RED) before it shipped.
# A correct v3 would digest an IIFE's OWN code while excluding the named functions inside it — i.e.
# apply the `toplevel` treatment per-IIFE rather than per-file. Worth doing; not done here.
_FN_RE = re.compile(r"^[ \t]*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)


def _strip_js_comments(src, html=False):
    """Remove // and /* */ comments (and, for .html, <!-- -->) while preserving string literals.

    WHY THIS EXISTS — a PROSE COMMENT was expiring live evidence. v3 segments top-level code by
    counting brackets per line, and it counted them INSIDE COMMENTS. This repo's house style writes
    long explanatory comments that name calls: "every client routes through getDb(", "118 annotated
    catch (_) { ... } blocks". Such a line carries an unbalanced bracket, which raises the splitter's
    depth and glues every following line into one giant statement. Measured: adding the single line
    "// every client routes through getDb( and _timeoutFetch" to utils.js vanished **881 of 881**
    top-level keys, expiring every row anchored to the file.

    That is the actual root of this bank's four collapses (752 green -> 34, then 342, ~365, ~320),
    each previously read as "shared-library edits are expensive". They were not expensive because the
    library was shared; they were expensive because writing a SENTENCE ABOUT the code counted as
    changing the code.

    Strings are preserved so a URL's `//` and a literal "/*" are not mistaken for comment openers.
    Regex literals are NOT parsed: a regex holding an unbalanced bracket can still mis-segment. That
    is the same exposure v3 already carried, and it fails toward over-sensitivity — a needless
    re-walk — never toward a false green.

    HTML COMMENTS MATTER JUST AS MUCH, and the first cut of v4 missed them. `fn_digests` treats every
    byte of an .html file outside a function body as top-level content, so `<!-- ... -->` lands in the
    same bracket-counted stream. Measured on marketplace.html: the single line
    `<!-- the seller tab routes through getDb( for its rows -->` vanished **592 of 710** keys under
    v4-without-this. Every page-anchored row in the bank rests on a .html file, so leaving this out
    would have fixed the shared library and left the larger half of the bank exactly as fragile.
    Only enabled for .html, since `<!--` is legal (legacy) JS and stripping it there would change
    meaning rather than remove prose.
    """
    out, i, n = [], 0, len(src)
    quote = None
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if not quote and html and src.startswith("<!--", i):
            j = src.find("-->", i + 4)
            i = (j + 3) if j != -1 else n
            continue
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:      # an escaped quote does not close the literal
                out.append(nxt)
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c == "'" or c == '"' or c == "`":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def fn_digests(paths, version=3):
    """{"<file>::<fn>": digest} for every `function name(...)` declaration, plus "<file>::toplevel"
    for everything outside those bodies. Brace-matched rather than regex-sliced, because a regex that
    stops at the first `}` reports a two-line function for a fifty-line one and would call a real
    change unchanged.

    Covers .js AND .html: a page's inline script is code, and a row that names one function in it must
    not be expired by an edit to another. A repeated name (two pages' `escHtml`, or an inner helper
    shadowing an outer) is disambiguated by occurrence, so two different bodies can never collapse
    onto one key and hide a change."""
    out = {}
    for p in sorted(paths or []):
        fp = os.path.join(ROOT, p)
        if not os.path.exists(fp) or not (p.endswith(".js") or p.endswith(".html")):
            continue
        src = open(fp, "r", encoding="utf-8", errors="replace").read()
        spans = []
        seen_names = {}
        for m in _FN_RE.finditer(src):
            i = src.find("{", m.end() - 1)
            if i < 0:
                continue
            depth, j, n = 0, i, len(src)
            while j < n:
                c = src[j]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                continue                      # unbalanced: skip rather than guess
            body = src[m.start():j + 1]
            name = m.group(1)
            # A name can legitimately repeat -- an inner helper shadowing an outer one, or two pages
            # sharing `escHtml`. Keying on the name alone would let the second body overwrite the
            # first, so a change to the shadowed one would leave the map byte-identical and the row
            # fresh. Disambiguate by occurrence; the extra key costs nothing and cannot hide a change.
            seen_names[name] = seen_names.get(name, 0) + 1
            key = name if seen_names[name] == 1 else "%s#%d" % (name, seen_names[name])
            # v4 digests CODE, not prose. A comment rewritten inside a function body is not a
            # behaviour change, and expiring a live reading for one is exactly the over-sensitivity
            # this mechanism exists to remove.
            _body = _strip_js_comments(body, html=p.endswith(".html")) if version >= 4 else body
            out["%s::%s" % (p, key)] = hashlib.sha256(_body.encode("utf-8")).hexdigest()[:16]
            spans.append((m.start(), j + 1))
        # Allowing indented declarations means NESTED functions match too, and a nested span sits
        # INSIDE its parent's. Slicing overlapping spans out of the source would corrupt the top-level
        # remainder (and could even run `last` backwards), so keep only the outermost spans here. The
        # nested bodies keep their own digests -- they are simply already covered by the parent's.
        outer, cover = [], -1
        for a, b in sorted(spans):
            if a >= cover:
                outer.append((a, b))
                cover = b
        top, last = [], 0
        for a, b in outer:
            top.append(src[last:a])
            last = b
        top.append(src[last:])
        # Normalised, because appending a function leaves an extra blank line in the top-level slice
        # and a raw hash would read that as a behaviour change -- expiring every row for a whitespace
        # gap, which is the exact over-sensitivity this whole mechanism exists to remove. Whitespace
        # BETWEEN top-level declarations cannot change what the file does; whitespace INSIDE a function
        # is inside that function's own digest, untouched by this.
        # v4 strips comments BEFORE normalising, which is what stops a prose edit from
        # re-segmenting the statement stream below. See _strip_js_comments: one comment line
        # naming `getDb(` vanished all 881 of utils.js's top-level keys under v3.
        _top = ([_strip_js_comments(c, html=p.endswith(".html")) for c in top]
                if version >= 4 else top)
        norm = "\n".join(ln.strip() for chunk in _top for ln in chunk.splitlines() if ln.strip())
        if version >= 3:
            # ── ONE BUCKET FOR ALL TOP-LEVEL CODE MADE EVERY SHARED-LIBRARY FIX COST ~340 RE-WALKS ──
            # v2 hashed the whole top-level remainder into a single "<file>::toplevel" key, so APPENDING
            # one IIFE to utils.js changed that key and expired every row anchored to the file. Measured
            # three times in one session on this arc: 309 rows, then 164, then 343 - and the third was a
            # three-line fix to a clipped avatar badge. Since utils.js is anchored by every browser row,
            # and centralize-first is the correct pattern (one shared fix beat eleven page-local ones in
            # that same session), the cost fell on exactly the work worth doing most.
            #
            # v3 splits the remainder into TOP-LEVEL STATEMENTS and keys each by its own content hash, so
            # KEY == VALUE. The recorded map becomes a SET of statement hashes that must all still be
            # present, which gives the three behaviours this needs, by construction rather than by care:
            #   append  -> a NEW key appears; every recorded key still present; nothing expires.
            #   modify  -> that statement's hash changes, so its recorded key VANISHES -> stale.
            #   delete  -> its key vanishes -> stale.
            # The asymmetry is the safety argument: a mis-placed statement boundary can only make a change
            # look bigger (more keys move), never smaller. Over-sensitivity costs a re-walk; UNDER-
            # sensitivity mints a false green, and this splitter cannot under-report, because any edited
            # byte lands inside some chunk and changes that chunk's hash.
            depth, buf, stmts = 0, [], []
            for ln in norm.splitlines():
                buf.append(ln)
                depth += ln.count("{") + ln.count("(") + ln.count("[")
                depth -= ln.count("}") + ln.count(")") + ln.count("]")
                if depth <= 0:                      # back at top level: the statement is complete
                    stmts.append("\n".join(buf))
                    buf, depth = [], 0
            if buf:
                stmts.append("\n".join(buf))        # unbalanced tail: keep it rather than drop it
            for st in stmts:
                if not st.strip():
                    continue
                h = hashlib.sha256(st.encode("utf-8")).hexdigest()[:16]
                out["%s::top:%s" % (p, h)] = h      # key == value: membership IS the check
        else:
            out["%s::toplevel" % p] = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    if out:
        out["::v"] = str(version)  # see fn_digests_still_hold: a map must be checked byits own algorithm
    return out


# ── THE MEASUREMENT CHANGED, AND THAT IS NOT DRIFT ───────────────────────────────────────────────
# Widening R4b to .html and to indented declarations (2026-08-05) also changed what "toplevel" MEANS:
# nested function bodies used to be part of the remainder and are now carved out of it, so the
# normalised remainder hashes differently for a file NOBODY TOUCHED. Recomputing old recordings with
# the new algorithm expired 661 rows in one run -- green 742 -> 81 -- and the forward-only ratchet
# refused it, correctly: "green went backwards, re-walk, do not re-baseline."
#
# It would have been wrong to re-walk them, because nothing they claim had changed; and wronger to
# re-baseline, because that is how a false green is minted. A recorded map must be checked by the
# ALGORITHM THAT PRODUCED IT. Maps written from now on carry "::v" = 2; a map without it is v1 and is
# checked against a v1 recomputation, so those rows keep exactly the freshness contract they were
# banked under and lose nothing. Re-walking a v1 row upgrades it naturally, because the new map is
# written at bank time from the code as it then is.
_FN_RE_V1 = re.compile(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)


def _fn_digests_v1(paths):
    """The pre-2026-08-05 algorithm, kept verbatim so v1 recordings stay comparable: `.js` only,
    declarations at column 0 only, no nested-span handling, no duplicate-name disambiguation."""
    out = {}
    for p in sorted(paths or []):
        fp = os.path.join(ROOT, p)
        if not os.path.exists(fp) or not p.endswith(".js"):
            continue
        src = open(fp, "r", encoding="utf-8", errors="replace").read()
        spans = []
        for m in _FN_RE_V1.finditer(src):
            i = src.find("{", m.end() - 1)
            if i < 0:
                continue
            depth, j, n = 0, i, len(src)
            while j < n:
                c = src[j]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                continue
            out["%s::%s" % (p, m.group(1))] = hashlib.sha256(
                src[m.start():j + 1].encode("utf-8")).hexdigest()[:16]
            spans.append((m.start(), j + 1))
        top, last = [], 0
        for a, b in sorted(spans):
            top.append(src[last:a])
            last = b
        top.append(src[last:])
        norm = "\n".join(ln.strip() for chunk in top for ln in chunk.splitlines() if ln.strip())
        out["%s::toplevel" % p] = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    return out


def accept_allowed(prev, now):
    """The ratchet's one rule, as a function so it can be tested without re-entering main().
    --accept may only RAISE the high-water mark. Lowering it goes through the audited
    false-green-withdrawal path, which records which rows bought the decrease."""
    return int(now) >= int(prev)


def fn_digests_still_hold(recorded):
    """True when every function/top-level digest a row RECORDED is still byte-identical, recomputed
    with the SAME algorithm that wrote it. Names absent from `recorded` are new code and are
    deliberately ignored."""
    if not recorded:
        return False
    # A RECORDED MAP IS CHECKED BY THE ALGORITHM THAT WROTE IT, which is why the version travels with it.
    # v1 rows keep the v1 contract, v2 rows keep the single-toplevel-bucket contract they were banked
    # under, and only v3 rows get the per-statement set. Nothing is retroactively re-interpreted - the last
    # time this file's measurement changed without versioning, recomputing old recordings with the new
    # algorithm expired 661 rows in one run and the ratchet correctly refused it.
    version = str(recorded.get("::v") or "1")
    files = sorted({k.split("::", 1)[0] for k in recorded if k != "::v"})
    if version == "4":
        current = fn_digests(files, version=4)
    elif version == "3":
        current = fn_digests(files, version=3)
    elif version == "2":
        current = fn_digests(files, version=2)
    else:
        current = _fn_digests_v1(files)
    for k, v in recorded.items():
        if k == "::v":
            continue
        if current.get(k) != v:
            return False
    return True


def gate_ids():
    src = ""
    try:
        with open(CHECKS, encoding="utf-8") as f:
            src = f.read()
    except Exception:
        return set()
    # The character class used to be [a-z0-9_], which cannot match a HYPHEN -- and the gate registry
    # names gates like "edge-status-body", "admin-gates", "abort-timeout". Measured 2026-08-04: the
    # old pattern saw 186 of the 732 registered ids, so 546 gates (75% of the registry) were invisible
    # and rule R2 rejected any evidence citing them. The bank could only ever cite the underscore
    # quarter of its own gate suite, which silently pushed walks toward weaker live-walk evidence when
    # a whole-layer gate was the stronger proof available.
    return set(re.findall(r'"id"\s*:\s*"([a-z0-9_-]+)"', src))


def surface_urls(reg):
    urls = {r.get("url") for r in rows_of(reg) if r.get("url")}
    return {u for u in urls if u}


def classify(row, gates, urls):
    """-> (state, reason). state in {green, stale, owed, invalid}."""
    status = row.get("status")
    if status == "owed":
        return "owed", ""
    if status == "lane-reassigned":
        return "owed", ""
    ev = row.get("evidence")
    if not isinstance(ev, dict):
        return "invalid", "R1 no evidence block on a non-owed row"
    kind, ref, asserts = ev.get("kind"), (ev.get("ref") or ""), (ev.get("asserts") or "").strip()
    if kind not in VALID_KINDS:
        return "invalid", f"R1 evidence.kind {kind!r} is not one of {sorted(VALID_KINDS)}"
    if not asserts:
        return "invalid", "R1 evidence.asserts is empty — 'green because of what?' has no answer"
    if kind == "gate":
        gid = ref.split("gate:")[-1].strip()
        if gid not in gates:
            return "invalid", f"R2 evidence names gate {gid!r}, which is not registered"
    if kind == "live-walk":
        if not re.search(r"\d{4}-\d{2}-\d{2}", ref):
            return "invalid", "R3 a live-walk ref must carry the session date"
        if not any(u in ref for u in urls):
            return "invalid", "R3 a live-walk ref must name a surface URL from the bank"
    if BEHAVIOURAL_RE.search(asserts) and STRUCTURAL_ONLY_RE.search(str(ev.get("checked") or "")) \
            and not ev.get("value_checked"):
        return "invalid", ("R6 a behavioural claim resting on structural evidence — this is the exact "
                           "shape that produced the false 343")
    dep = ev.get("depends_on") or []

    # R7 · A CLAIM MUST NAME WHAT IT ACTUALLY RESTS ON.
    # Every one of the 136 layer/seam rows was declared to depend on marketplace.html + utils.js —
    # the page that happened to be open during the hand walk. A DB invariant does not rest on a page,
    # and the consequence is not cosmetic: the sha then moves when a PAGE is edited (124 rows expired
    # for nothing) and does NOT move when a MIGRATION lands. Mig 50 revoked a SELECT this session and
    # would not have expired a single grant_matches_policy row. That is a false green with no signal,
    # which is worse than the noise.
    #
    # A mis-declared row is reported STALE rather than invalid: the claim may well still be true, but
    # its freshness anchor never held, so it has to be re-earned rather than trusted.
    surface = row.get("surface") or ""
    if surface in LAYER_DEPS and status not in ("owed", "lane-reassigned"):
        if sorted(dep) != sorted(LAYER_DEPS[surface]):
            return "stale", (f"R7 a {surface} claim declares {dep or '[]'} but rests on "
                             f"{LAYER_DEPS[surface]} — re-walk it against the right artifacts")

    # R7, PAGE-BANK HALF. Same rule, different bookkeeping: these rows name the page in `surface` and
    # the layer in `subject.name`, so the test above could never see them. See PAGE_LAYER_DEPS.
    if ("-CA-layer-contract-" in str(row.get("id") or "")
            and status not in ("owed", "lane-reassigned")):
        page_file = next((d for d in (row.get("page_deps") or []) if str(d).endswith(".html")), None)
        if page_file is None:
            # derive it from the surface: the page banks' surface IS the page stem
            page_file = f"{surface}.html" if surface else None
        if page_file:
            want = page_layer_deps(page_file, (row.get("subject") or {}).get("name"))
            # SUBSET, NOT EQUALITY — and the asymmetry is the whole point of the rule. R7 exists to catch
            # a claim that MISSES what it rests on (a db invariant that no migration can expire: a false
            # green with no signal). A claim that declares MORE than its layer needs is the cheap
            # direction: over-expiry costs a re-walk, under-expiry costs a wrong number.
            # This is not a loophole, it is required for correctness. Some oracles genuinely span layers:
            # `ordering_totality` on a db read rests on the PAGE (which writes the ORDER BY clause) AND on
            # migrations (which decide whether the sort is unique) - its own evidence says "ORDER clauses
            # read site-by-site out of the source and tie density measured in SQL". An equality test
            # demanded that such a row DROP the page it genuinely depends on, which would have created the
            # exact unsafe anchor this rule exists to prevent, pointing the other way.
            if want is not None and not set(want).issubset(set(dep)):
                missing = sorted(set(want) - set(dep))
                return "stale", (f"R7 a {(row.get('subject') or {}).get('name')} claim declares "
                                 f"{dep or '[]'} but does not name {missing}, which it rests on — "
                                 f"re-walk it against the right artifacts (a migration that changes "
                                 f"this must expire the claim, and today it would not)")

    if dep:
        if sha_of(dep) != ev.get("sha"):
            # R4b: before calling it stale, ask the finer question. If the row recorded which FUNCTIONS
            # it rested on and every one of them is byte-identical, the file changed around the claim
            # rather than under it. Only rows that took the trouble to record that get the benefit.
            if not fn_digests_still_hold(ev.get("fn_digests")):
                return "stale", "R4 a file this claim depends on has changed since the walk"
    return "green", ""


# ── MULTI-BANK (2026-08-05, the page-testbank arc) ───────────────────────────────────────────────
# The marketplace registry was this gate's only subject for its whole life; the 22 page banks under
# banks/ now sit beside it. One registry per PAGE, not one 40MB pile, so each page's green% is
# legible on its own and the marketplace's 97.8% is not swamped under 4,400 fresh owed rows — the
# "one metric masks another" lesson applied structurally. The rules (R1-R7) are IDENTICAL for every
# bank; only the iteration changed. The baseline grew from {"green": N} to {"banks": {name: {...}}},
# and the old flat shape is read as the marketplace bank alone so no history is lost.

def discover_banks():
    banks = [("marketplace", REGISTRY)]
    bdir = os.path.join(ROOT, "banks")
    if os.path.isdir(bdir):
        for f in sorted(os.listdir(bdir)):
            if f.endswith("_live_mcp_bank.json"):
                banks.append((f[: -len("_live_mcp_bank.json")], os.path.join(bdir, f)))
    return banks


def load_baseline():
    base = load(BASELINE, {}) or {}
    if isinstance(base.get("banks"), dict):
        return base["banks"]
    if "green" in base:            # legacy flat shape = the marketplace bank alone
        return {"marketplace": base}
    return {}


def save_baseline(banks_base):
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump({"banks": banks_base,
                   "note": "forward-only ratchet on GREEN, per bank. stale is excluded from the "
                           "denominator."}, f, indent=1)


def process_bank(name, path, gates, argv, entry):
    """Run the full rule set over ONE bank. Returns (exit_code, new_baseline_entry_or_None).
    A returned entry means the baseline for this bank should be rewritten (accept or an audited
    withdrawal); None means leave it as it stands."""
    reg = load(path)
    if reg is None:
        print(f"  {RED}FAIL{RST} — {os.path.relpath(path, ROOT)} is unreadable")
        return 1, None
    rows = rows_of(reg)
    urls = surface_urls(reg)

    buckets = {"green": [], "stale": [], "owed": [], "invalid": []}
    for r in rows:
        st, why = classify(r, gates, urls)
        buckets[st].append((r.get("id"), why))

    denom = len(buckets["green"]) + len(buckets["owed"])          # stale excluded, deliberately
    pct = (100.0 * len(buckets["green"]) / denom) if denom else 0.0
    print(f"\n  {BOLD}{name}{RST} {DIM}· {os.path.relpath(path, ROOT)}{RST}")
    print(f"  {DIM}scenarios: {len(rows)} · green {len(buckets['green'])} · stale {len(buckets['stale'])} "
          f"· owed {len(buckets['owed'])} · invalid {len(buckets['invalid'])}{RST}")
    print(f"  {DIM}green% over non-stale: {pct:.1f}%  (stale is excluded so drift shows up rather than "
          f"being absorbed){RST}")

    if "--report" in argv:
        import collections
        cats = collections.Counter(r.get("category") or r.get("family") for r in rows)
        print(f"  {BOLD}distribution{RST}")
        for c, n in sorted(cats.items()):
            print(f"    {n:4d}  {c}")

    if buckets["invalid"]:
        print(f"\n  {RED}FAIL{RST} — {len(buckets['invalid'])} row(s) claim a status they cannot support:")
        for rid, why in buckets["invalid"][:15]:
            print(f"    · {rid}\n        {DIM}{why}{RST}")
        if len(buckets["invalid"]) > 15:
            print(f"    {DIM}… and {len(buckets['invalid']) - 15} more{RST}")
        print(f"\n  {DIM}A row is green because of something. Say what, in evidence.asserts, and cite it "
              f"in evidence.ref.{RST}")
        return 1, None

    if buckets["stale"]:
        print(f"  {YEL}STALE{RST} — {len(buckets['stale'])} row(s) were true and the ground moved:")
        for rid, _ in buckets["stale"][:10]:
            print(f"    · {rid}")
        if len(buckets["stale"]) > 10:
            print(f"    {DIM}… and {len(buckets['stale']) - 10} more{RST}")
        print(f"  {DIM}Re-walk them on the live MCP browser. Stale is not a failure; a stale row treated "
              f"as green is.{RST}")

    prev = int((entry or {}).get("green", 0))
    if "--accept" in argv:
        now = len(buckets["green"])
        # A RATCHET THAT TURNS BOTH WAYS IS NOT A RATCHET. --accept used to overwrite the baseline
        # unconditionally, so it LOWERED the high-water mark as happily as it raised it. On 2026-08-05
        # I edited utils.js (adding a reduced-motion guard), which legitimately expired most rows to
        # `stale`, then ran --accept out of habit while banking five unrelated rows: 752 -> 29,
        # silently, in the one mechanism whose whole job is that a walk cannot be quietly un-done. A
        # later 100 would then have read as progress from 29.
        # Accept may only RAISE. A drop caused by drift is what `stale` is for — re-walk it. A drop
        # caused by an honest retraction goes through the audited withdrawal path below, which demands
        # a false-green-withdrawn finding on each row and records the ids that bought the decrease.
        if not accept_allowed(prev, now):
            print(f"\n  {RED}REFUSED{RST} — --accept may only ratchet UP. green {prev} -> {now} "
                  f"({now - prev}); the baseline stays at {prev}.")
            print(f"  {DIM}{len(buckets['stale'])} row(s) are stale: a dependency changed, so their "
                  f"evidence expired. Re-walk them — that is what stale means. To LOWER the bar you "
                  f"must withdraw specific rows with a false-green-withdrawn finding, which is "
                  f"audited and records which ids bought the decrease.{RST}")
            return 1, None
        print(f"  {GREEN}ACCEPTED{RST} — baseline {prev} -> {now} green")
        return 0, {**(entry or {}), "green": now}
    # WITHDRAWING A FALSE GREEN IS NOT A REGRESSION. The ratchet exists so a walk cannot be quietly
    # un-done, and it was right to fire the first time it saw this drop. But it could not tell a lost
    # walk from an honest retraction, and on 2026-08-04 it blocked exactly the correction the bank
    # exists to make possible: a contrast_wcag row banked green on "axe: 0 violations" when axe had
    # actually ABSTAINED on 185 nodes it could not measure. Correcting a false claim must never be
    # harder than making one, or the ratchet quietly rewards leaving it green.
    #
    # The exception is narrow and auditable: a decrease is allowed ONLY when every missing green is
    # accounted for by a row that is now owed AND carries a `false-green-withdrawn` finding saying
    # why. Anything else -- an expired sha, a deleted row, a silently flipped status -- still FAILs.
    #
    # A RATCHET THAT TURNS BOTH WAYS IS NOT A RATCHET (found 2026-08-04). This compared a CUMULATIVE
    # pool of withdrawn rows against an INCREMENTAL drop, so every past withdrawal stayed in the pool
    # and kept authorising future drops. It fired for real: an edit to marketplace.html expired rows
    # into `stale`, the drop was covered by withdrawals audited in EARLIER runs, and the baseline
    # lowered itself 317 -> 312 while printing "not by absorbing drift" -- which is precisely what it
    # had done. Nothing had been withdrawn that run.
    # A withdrawal may only pay for a drop ONCE. The ids that bought a decrease are recorded in the
    # baseline and are not counted again.
    spent = set((entry or {}).get("withdrawn_ids") or [])
    withdrawn = [s for s in rows
                 if s.get("status") == "owed"
                 and s.get("id") not in spent
                 # findings are dicts in the newer rows and bare strings in the older ones
                 and any(isinstance(f, dict) and f.get("severity") == "false-green-withdrawn"
                         for f in (s.get("findings") or []))]
    drop = prev - len(buckets["green"])
    if drop > 0 and len(withdrawn) >= drop:
        print(f"\n  {YEL}WITHDRAWN{RST} — green {prev} -> {len(buckets['green'])} ({drop}), and "
              f"{len(withdrawn)} row(s) carry a false-green-withdrawn finding. A retraction is not a "
              f"regression; the baseline follows it DOWN so the correction sticks:")
        for s in withdrawn[:5]:
            title = next((f.get("title") for f in (s.get("findings") or [])
                          if isinstance(f, dict) and f.get("severity") == "false-green-withdrawn"), "")
            print(f"    · {s['id']}\n        {title}")
        return 0, {"green": len(buckets["green"]),
                   "note": "lowered by an audited false-green withdrawal, not by absorbing drift",
                   # the ids that bought this decrease; they cannot buy another one
                   "withdrawn_ids": sorted(spent | {s["id"] for s in withdrawn})}
    if len(buckets["green"]) < prev:
        print(f"\n  {RED}FAIL{RST} — green went backwards: {prev} -> {len(buckets['green'])}. Either a walk "
              f"was undone or evidence expired; re-walk, do not re-baseline.")
        return 1, None

    print(f"  {GREEN}PASS{RST} — every non-owed row carries typed, unexpired evidence "
          f"(baseline {prev} green)")
    return 0, None


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Live-MCP bank — typed evidence, and evidence that expires{RST}")
    if selftest() != 0:
        return 1

    gates = gate_ids()
    banks_base = load_baseline()
    rc, dirty = 0, False
    for name, path in discover_banks():
        brc, new_entry = process_bank(name, path, gates, argv, banks_base.get(name))
        rc = max(rc, brc)
        if new_entry is not None:
            banks_base[name] = new_entry
            dirty = True
    # PERSIST PER-BANK, NOT ALL-OR-NOTHING (fixed 2026-08-05, first --accept across 23 banks).
    # This used to be `if dirty and rc == 0`, and the very first multi-bank accept exposed why that
    # is wrong: the marketplace bank correctly REFUSED its accept (752 -> 412 under the parallel
    # walking session's drift), which set rc=1 — and that discarded the page banks' legitimate,
    # independently-validated accepts while the run had already printed "ACCEPTED" for each of them.
    # A tool that prints a success it did not persist is the silently-failed-write class, and here it
    # would have quietly cost a real banked walk.
    # Each entry is decided on its OWN bank's ratchet inside process_bank, which returns an entry
    # ONLY when that bank's accept is lawful. So a refusal elsewhere must not veto it: one bank's
    # drift is not another bank's regression. rc still reports the failure, so the gate stays RED.
    if dirty:
        save_baseline(banks_base)
    return rc


def selftest():
    print("  selftest: each rule must FIRE on a rigged row")
    ok = True
    gates, urls = {"validate_public_read_surface"}, {"/workhive/marketplace.html"}
    # THIS file, because it is certainly present and certainly inside ROOT. The first version used
    # CLAUDE.md, which lives one directory UP — so the fixture hashed an empty list while classify()
    # hashed the missing-file marker, and the self-test failed its own well-formed case. A fixture that
    # does not exist is the oldest way to fail a test that is actually passing.
    DEP = "tools/validate_live_mcp_bank.py"
    good_sha = sha_of([DEP])

    cases = [
        # (row, expected_state, label)
        ({"status": "green"}, "invalid", "R1 green with no evidence block"),
        ({"status": "green", "evidence": {"kind": "vibes", "ref": "x", "asserts": "a"}},
         "invalid", "R1 unknown kind"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:x", "asserts": ""}},
         "invalid", "R1 empty asserts"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:no_such_gate", "asserts": "a"}},
         "invalid", "R2 gate that is not registered"),
        ({"status": "green", "evidence": {"kind": "live-walk", "ref": "/workhive/marketplace.html",
                                          "asserts": "a"}},
         "invalid", "R3 live-walk with no date"),
        ({"status": "green", "evidence": {"kind": "live-walk", "ref": "2026-08-04 /workhive/nope.html",
                                          "asserts": "a"}},
         "invalid", "R3 live-walk naming a surface not in the bank"),
        ({"status": "green", "evidence": {"kind": "live-walk", "ref": "2026-08-04 /workhive/marketplace.html",
                                          "asserts": "the chip matches service_knob_pct",
                                          "checked": "renders content; no overflow"}},
         "invalid", "R6 behavioural claim on structural evidence"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface",
                                          "asserts": "a", "depends_on": [DEP], "sha": "deadbeef"}},
         "stale", "R4 dependency changed since the walk"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface",
                                          "asserts": "a", "depends_on": [DEP], "sha": good_sha}},
         "green", "a well-formed, unexpired row"),
        ({"status": "owed"}, "owed", "an owed row needs no evidence"),

        # R7 — the exact shape all 136 layer/seam rows carried: a DB invariant anchored to a page.
        ({"status": "green", "surface": "layer_db",
          "evidence": {"kind": "psql", "ref": "psql 2026-08-05", "asserts": "the ledger conserves",
                       "depends_on": ["marketplace.html", "utils.js"], "sha": "whatever"}},
         "stale", "R7 a layer_db claim anchored to a page"),
        ({"status": "green", "surface": "seam_edge_db",
          "evidence": {"kind": "psql", "ref": "psql 2026-08-05", "asserts": "edge fns scope by hive",
                       "depends_on": ["supabase/migrations"], "sha": "whatever"}},
         "stale", "R7 a seam that names only half of what it rests on"),
        # and the other direction: layer_client genuinely DOES rest on the page, so it must pass
        ({"status": "green", "surface": "layer_client",
          "evidence": {"kind": "psql", "ref": "psql 2026-08-05", "asserts": "the client envelope",
                       "depends_on": ["marketplace.html", "utils.js"],
                       "sha": sha_of(["marketplace.html", "utils.js"])}},
         "green", "R7 must NOT fire on a client-layer row that legitimately depends on the page"),

        # ── R7, PAGE-BANK HALF ────────────────────────────────────────────────────────────────────
        # The shape that 92 GREEN page-bank rows carried: a schema claim anchored to the page that was
        # open when it was walked. This half of R7 was missing entirely, so none of them was flagged.
        ({"status": "green", "surface": "marketplace",
          "id": "PB-marketplace-011-CA-layer-contract-L3-envelope_shape",
          "subject": {"key": "L3", "name": "db (17 tables/views)"},
          "evidence": {"kind": "psql", "ref": "psql 2026-08-10", "asserts": "bare JSON array envelope",
                       "depends_on": ["marketplace.html", "utils.js"], "sha": "whatever"}},
         "stale", "R7 page-bank: a db claim anchored to the page"),
        # gateway on a PAGE bank means PostgREST, so supabase/functions is ALSO wrong here - this is the
        # case that made a blind alias of LAYER_DEPS unsafe.
        ({"status": "green", "surface": "marketplace",
          "id": "PB-marketplace-006-CA-layer-contract-L2-idempotency",
          "subject": {"key": "L2", "name": "gateway (PostgREST reads)"},
          "evidence": {"kind": "psql", "ref": "psql 2026-08-10", "asserts": "same request, same bytes",
                       "depends_on": ["supabase/functions"], "sha": "whatever"}},
         "stale", "R7 page-bank: a PostgREST gateway claim anchored to functions, not the schema"),
        # and it must stay SILENT on a client-layer row, which really does rest on its page
        ({"status": "green", "surface": "marketplace",
          "id": "PB-marketplace-001-CA-layer-contract-L1-units_declared",
          "subject": {"key": "L1", "name": "client"},
          "evidence": {"kind": "live-walk", "ref": "2026-08-10 live MCP /workhive/marketplace.html",
                       "asserts": "every quantity carries its unit",
                       "value_checked": "read from the rendered rows",
                       "depends_on": ["marketplace.html", "utils.js"],
                       "sha": sha_of(["marketplace.html", "utils.js"])}},
         "green", "R7 page-bank must NOT fire on a client row that legitimately rests on its page"),
        # an UNMAPPED layer word is a no-op, not a failure: a new anatomy word must not brick the gate
        ({"status": "green", "surface": "marketplace",
          "id": "PB-marketplace-016-CA-layer-contract-L4-units_declared",
          "subject": {"key": "L4", "name": "quantum-flux (not a real layer)"},
          "evidence": {"kind": "psql", "ref": "psql 2026-08-10", "asserts": "a",
                       "depends_on": [DEP], "sha": good_sha}},
         "green", "R7 page-bank leaves an unmapped layer word alone"),
        # SUBSET, both directions. A SPANNING claim (ordering_totality reads the ORDER BY from the page
        # and the tie density from the schema) declares MORE than its layer requires and must PASS -
        # an equality test would have forced it to drop the page it really rests on.
        ({"status": "green", "surface": "marketplace",
          "id": "PB-marketplace-013-CA-layer-contract-L3-ordering_totality",
          "subject": {"key": "L3", "name": "db (9 tables/views)"},
          "evidence": {"kind": "psql", "ref": "psql 2026-08-10",
                       "asserts": "every paginated ORDER is total",
                       "value_checked": "ORDER clauses read from the page; tie density measured in SQL",
                       "depends_on": ["marketplace.html", "utils.js", "supabase/migrations"],
                       "sha": sha_of(["marketplace.html", "utils.js", "supabase/migrations"])}},
         "green", "R7 page-bank must ALLOW a claim that declares more than its layer requires"),
        # ...but a claim that OMITS its layer's artifact still fails, which is the unsafe direction
        ({"status": "green", "surface": "marketplace",
          "id": "PB-marketplace-014-CA-layer-contract-L3-ordering_totality",
          "subject": {"key": "L3", "name": "db (9 tables/views)"},
          "evidence": {"kind": "psql", "ref": "psql 2026-08-10",
                       "asserts": "every paginated ORDER is total",
                       "depends_on": ["marketplace.html", "utils.js"], "sha": "whatever"}},
         "stale", "R7 page-bank still catches a db claim that omits supabase/migrations"),
    ]
    for row, want, label in cases:
        got, _ = classify(row, gates, urls)
        if got != want:
            print(f"  {RED}FAIL{RST} — {label}: expected {want}, got {got}")
            ok = False

    # ── R4b, both directions, against a REAL temporary .js rather than a mocked digest ────────────
    # The widening must survive the question "does it still catch a change?", so it is tested by
    # actually editing a file: appending a function must NOT expire the row, and editing a recorded
    # one MUST. A one-directional test here would let R4b quietly become "never stale".
    tmp = os.path.join(ROOT, "_r4b_selftest.js")
    try:
        open(tmp, "w", encoding="utf-8").write(
            "function alpha() {\n  if (1) { return 'a'; }\n}\nvar top = 1;\n")
        rec = fn_digests(["_r4b_selftest.js"])
        row = {"status": "green",
               "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface", "asserts": "a",
                            "depends_on": ["_r4b_selftest.js"], "sha": "stale-on-purpose",
                            "fn_digests": rec}}
        if classify(row, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b: an unchanged function should read green even with a stale file sha")
            ok = False
        # append a NEW function: nothing the row recorded moved, so the row must survive
        open(tmp, "a", encoding="utf-8").write("function beta() {\n  return 'b';\n}\n")
        if classify(row, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b: appending an unrelated function must not expire a row")
            ok = False
        # now EDIT the recorded function: this must expire it
        open(tmp, "w", encoding="utf-8").write(
            "function alpha() {\n  if (1) { return 'CHANGED'; }\n}\nvar top = 1;\n")
        if classify(row, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b: editing a recorded function MUST expire the row")
            ok = False
        # and a change to TOP-LEVEL code must expire it too -- that is where a wrapper would hide
        open(tmp, "w", encoding="utf-8").write(
            "function alpha() {\n  if (1) { return 'a'; }\n}\nvar top = 2;\n")
        if classify(row, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b: a top-level change MUST expire the row")
            ok = False
        # a row that recorded nothing gets no benefit: it falls back to the whole-file hash
        bare = {"status": "green",
                "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface", "asserts": "a",
                             "depends_on": ["_r4b_selftest.js"], "sha": "stale-on-purpose"}}
        if classify(bare, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b: a row with no fn_digests must still fall back to the file hash")
            ok = False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # ── R4b on an .HTML page, both directions, and the two traps the widening introduced ──────────
    # The pages are where the code lives, and until 2026-08-05 they were excluded, so one touch
    # anywhere in a page expired every row that named it. Matching INDENTED declarations brings them
    # in, and brings two hazards with it: nested functions (whose spans sit inside their parent's and
    # would corrupt the top-level remainder) and repeated names (where the second body would silently
    # overwrite the first, hiding a change in the shadowed one). Both are asserted here.
    tmph = os.path.join(ROOT, "_r4b_selftest.html")
    try:
        page = ("<html><body><script>\n(function () {\n"
                "  function outer() {\n    function inner() { return 1; }\n    return inner();\n  }\n"
                "  function other() { return 'x'; }\n"
                "  var wired = 1;\n})();\n</script></body></html>\n")
        open(tmph, "w", encoding="utf-8").write(page)
        rec = fn_digests(["_r4b_selftest.html"])
        if "_r4b_selftest.html::outer" not in rec or "_r4b_selftest.html::inner" not in rec:
            print(f"  {RED}FAIL{RST} — R4b/html: an inline script's functions must be digested")
            ok = False
        row = {"status": "green",
               "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface", "asserts": "a",
                            "depends_on": ["_r4b_selftest.html"], "sha": "stale-on-purpose",
                            "fn_digests": rec}}
        if classify(row, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b/html: an untouched page should read green despite a stale file sha")
            ok = False
        # add a function the row never recorded: it must expire nothing
        open(tmph, "w", encoding="utf-8").write(page.replace(
            "  var wired = 1;", "  function added() { return 2; }\n  var wired = 1;"))
        if classify(row, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b/html: adding a new function must not expire a row")
            ok = False
        # edit a NESTED function: the parent's body contains it, so the row MUST expire
        open(tmph, "w", encoding="utf-8").write(page.replace("return 1;", "return 99;"))
        if classify(row, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b/html: editing a NESTED function MUST expire the row")
            ok = False
        # top-level code inside the IIFE is inside `outer`'s siblings, not the file remainder, so
        # assert the remainder too: the markup around the script must still count
        open(tmph, "w", encoding="utf-8").write(page.replace("<body>", "<body data-changed='1'>"))
        if classify(row, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b/html: a change OUTSIDE every function must expire the row")
            ok = False
        # a repeated name must not collapse onto one key and hide a change in the shadowed body
        dup = ("<html><body><script>\n"
               "  function dupe() { return 'first'; }\n"
               "  function dupe() { return 'second'; }\n</script></body></html>\n")
        open(tmph, "w", encoding="utf-8").write(dup)
        d1 = fn_digests(["_r4b_selftest.html"])
        if "_r4b_selftest.html::dupe#2" not in d1:
            print(f"  {RED}FAIL{RST} — R4b/html: a repeated function name must get its own key")
            ok = False
        rowd = {"status": "green",
                "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface", "asserts": "a",
                             "depends_on": ["_r4b_selftest.html"], "sha": "stale-on-purpose",
                             "fn_digests": d1}}
        open(tmph, "w", encoding="utf-8").write(dup.replace("'second'", "'CHANGED'"))
        if classify(rowd, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b/html: changing the SHADOWED duplicate MUST expire the row")
            ok = False
    finally:
        if os.path.exists(tmph):
            os.remove(tmph)

    # ── A v1 MAP MUST STILL BE HONOURED, AND MUST STILL HAVE TEETH ───────────────────────────────
    # Widening the algorithm changed what "toplevel" means, so recomputing a v1 recording with the v2
    # algorithm expired 661 untouched rows. A map is checked by the algorithm that wrote it. Both
    # halves are asserted: a v1 row survives code it does not name, and STILL dies on code it does.
    tmp1 = os.path.join(ROOT, "_r4b_v1_selftest.js")
    try:
        # The fixture must REPRODUCE the divergence, or this case is a teeth test that never fires.
        # An IIFE with INDENTED declarations is the real shape (utils.js, every page): v1 matches no
        # `^function` at all, so its toplevel remainder is the whole file INCLUDING those bodies,
        # while v2 carves them out. A fixture with a column-0 function wrapping an indented one does
        # NOT diverge -- v2's outermost-span rule keeps the same remainder -- and an earlier version
        # of this test used exactly that, passed under a deliberately broken checker, and proved
        # nothing.
        iife = ("(function () {\n"
                "  function alpha() { return 'a'; }\n"
                "  var wired = 1;\n"
                "})();\n")
        open(tmp1, "w", encoding="utf-8").write(iife)
        v1 = _fn_digests_v1(["_r4b_v1_selftest.js"])          # no "::v" key: this is a v1 recording
        if "::v" in v1:
            print(f"  {RED}FAIL{RST} — R4b/v1: a v1 map must not carry a version marker")
            ok = False
        if v1.get("_r4b_v1_selftest.js::toplevel") == fn_digests(
                ["_r4b_v1_selftest.js"]).get("_r4b_v1_selftest.js::toplevel"):
            print(f"  {RED}FAIL{RST} — R4b/v1: fixture does not diverge, so the version test proves nothing")
            ok = False
        rowv1 = {"status": "green",
                 "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface", "asserts": "a",
                              "depends_on": ["_r4b_v1_selftest.js"], "sha": "stale-on-purpose",
                              "fn_digests": v1}}
        if classify(rowv1, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b/v1: an untouched v1 row must stay green under the new algorithm")
            ok = False
        open(tmp1, "a", encoding="utf-8").write("function added() { return 2; }\n")
        if classify(rowv1, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b/v1: adding a function must not expire a v1 row")
            ok = False
        open(tmp1, "w", encoding="utf-8").write(
            "function alpha() {\n  function helper() { return 99; }\n  return helper();\n}\nvar top = 1;\n")
        if classify(rowv1, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b/v1: a v1 row MUST still expire when its recorded body changes")
            ok = False
    finally:
        if os.path.exists(tmp1):
            os.remove(tmp1)

    # ── R5 · THE RATCHET MUST ONLY TURN ONE WAY ──────────────────────────────────────────────────
    # --accept overwrote the baseline unconditionally, so it lowered the high-water mark as happily as
    # it raised it: on 2026-08-05 a legitimate utils.js edit expired most rows to stale and a habitual
    # --accept took the baseline 752 -> 29 in silence.
    for prev, now, want_ok, label in [
        (752, 29, False, "a drift-driven drop must be REFUSED"),
        (752, 752, True, "an unchanged count is allowed (no-op)"),
        (752, 760, True, "a genuine increase must be ACCEPTED"),
        (0, 5, True, "from a cold baseline any count is an increase"),
    ]:
        if accept_allowed(prev, now) is not want_ok:
            print(f"  {RED}FAIL{RST} — R5: {label} (prev={prev}, now={now})")
            ok = False

    # ── R4c · A DIRECTORY DEPENDENCY MUST MOVE ON EVERY KIND OF CHANGE ───────────────────────────
    # The DB-layer rows depend on the migration SET, not on any page. That only protects them if the
    # hash moves when a migration is ADDED (the common case — a new grant), when one is EDITED, and
    # when one is DELETED. Testing only "edit" would let a new migration slip past a green row, which
    # is precisely the false green this dependency exists to prevent.
    dtmp = os.path.join(ROOT, "_r4c_selftest_dir")
    try:
        # Clean at the START, not only in the finally. The first run of this test died on a missing
        # import INSIDE the finally, so the scratch directory survived with the nested file already
        # in it — and the next run's `base` therefore already contained the file the test was about
        # to add, so "adding it changed nothing" read as a hash defect in sha_of. The code was fine;
        # the test was reading leftover state. A test that assumes a clean slate it did not create
        # reports the previous run's crash as this run's bug.
        shutil.rmtree(dtmp, ignore_errors=True)
        os.makedirs(os.path.join(dtmp, "nested"), exist_ok=True)
        one = os.path.join(dtmp, "0001_first.sql")
        open(one, "w", encoding="utf-8").write("grant select on t to authenticated;\n")
        base = sha_of(["_r4c_selftest_dir"])

        if sha_of(["_r4c_selftest_dir"]) != base:
            print(f"  {RED}FAIL{RST} — R4c: an untouched directory hashed differently twice")
            ok = False

        two = os.path.join(dtmp, "0002_added.sql")
        open(two, "w", encoding="utf-8").write("revoke select on t from anon;\n")
        if sha_of(["_r4c_selftest_dir"]) == base:
            print(f"  {RED}FAIL{RST} — R4c: ADDING a migration left the hash unchanged")
            ok = False
        added = sha_of(["_r4c_selftest_dir"])

        open(two, "w", encoding="utf-8").write("revoke select on t from anon, authenticated;\n")
        if sha_of(["_r4c_selftest_dir"]) == added:
            print(f"  {RED}FAIL{RST} — R4c: EDITING a migration left the hash unchanged")
            ok = False

        os.remove(two)
        if sha_of(["_r4c_selftest_dir"]) != base:
            print(f"  {RED}FAIL{RST} — R4c: DELETING the added migration did not return the hash")
            ok = False

        # a nested file must count too — migrations sit flat today, but a hash that ignores
        # subdirectories would silently stop covering them the day someone nests one
        open(os.path.join(dtmp, "nested", "0003_deep.sql"), "w", encoding="utf-8").write("-- x\n")
        if sha_of(["_r4c_selftest_dir"]) == base:
            print(f"  {RED}FAIL{RST} — R4c: a file in a SUBDIRECTORY did not move the hash")
            ok = False
    finally:
        shutil.rmtree(dtmp, ignore_errors=True)

    if ok:
        print(f"  {GREEN}PASS{RST} — R1/R2/R3/R4/R4b/R4c/R5/R6/R7 all fire; a well-formed row passes; owed is exempt")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
