#!/usr/bin/env python3
"""
validate_journey_ux_dims.py — source-grep gate for 3 experience-in-motion rubric dims that the runtime
__RUBRIC lens can't cleanly see (they're behavioral, detectable in the page SOURCE, not a single DOM load):

  J3 · Consequence transparency — every DESTRUCTIVE action (delete/remove/wipe/purge handler) routes through
       the central whConfirm() (which the platform uses with a consequence message + action-specific label).
       A destructive onclick that does NOT go through whConfirm can fire an irreversible write on a mis-tap
       with no consequence preview. Measure: destructive-action pages that use whConfirm / such pages.
  G5 · System memory & personalization — a page with a FILTER/VIEW/SORT control persists the user's choice
       (localStorage.setItem of a *filter/view/sort/tab/pref* key) so it restores next visit (recognition,
       not re-setup). Measure: filterable pages that persist a preference / filterable pages.
  S4 · Behavioral consistency — the SAME action behaves the same everywhere: across all destructive-action
       pages, the confirm mechanism is the ONE shared whConfirm (not a raw window.confirm or a bespoke modal
       on some pages). Measure: 1 - (pages using a NON-shared confirm / destructive-action pages).

Forward-only ratchets (baselines in journey_ux_dims_baseline.json). Emits journey_ux_dims_report.json (read
by rubric_coverage.py as the measurement source for J3/G5/S4). Static (grep), fast. Self-test: --selftest.

USAGE: python tools/validate_journey_ux_dims.py [--json] [--selftest] [--accept]
Exit 0 = no regression, 1 = a dim regressed below baseline (or self-test failed).
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "journey_ux_dims_report.json"
BASELINE = ROOT / "journey_ux_dims_baseline.json"

# The 32 user-facing "family" pages (the rubric's measured denominator). Internal dev consoles + distinct
# artifacts are excluded, same basis as the family sweep + the S1 EXCLUDE list.
EXCLUDE = {
    "architecture.html", "design-system.html", "symbol-gallery.html", "validator-catalog.html",
    "llm-observability.html", "agentic-rag-observability.html", "ai-quality.html", "status.html",
    "offline-fallback.html", "promo-poster.html", "resume.html", "platform-health.html",
    "engineering-design-test.html",   # test/dev page, not a production surface
}
# a DESTRUCTIVE handler: an onclick/handler whose verb is irreversible-loss (mirrors the lens Z3 _destRe).
_DESTRUCTIVE = re.compile(r"onclick=\"[^\"]*\b(delete|remove|wipe|purge|discard|revoke)[A-Za-z]*\s*\(", re.I)
_WHCONFIRM = re.compile(r"\bwhConfirm\s*\(")
# An action is J3-safe if it CONFIRMS (whConfirm) OR is UNDOABLE — a soft-delete (deleted_at) with a
# 5s-undo / supervisor-recovery IS the NN/g "undo > confirmation" pattern (community's deletePost), an
# equally-valid consequence-safety mechanism, NOT a J3 gap. Credit it alongside whConfirm.
_UNDO_SAFE = re.compile(r"deleted_at|soft.?delete|\bundo\b|recover", re.I)
_RAWCONFIRM = re.compile(r"(?<![.\w])(window\.)?confirm\s*\(")   # native confirm() = NOT the shared mechanism
_FILTER_CTL = re.compile(r"id=\"[^\"]*(filter|sort)[^\"]*\"|class=\"[^\"]*\bfilter\b[^\"]*\"|placeholder=\"[^\"]*(filter|search)", re.I)
# G5a is satisfied by a raw localStorage-persist of a filter/view/sort key OR by adopting the SHARED
# whRememberView() helper (the centralize-first fix — one helper, not 14 hand-rolled persistences).
_PERSIST = re.compile(r"localStorage\.setItem\(\s*[`'\"][a-z0-9_:]*(filter|view|sort|tab|pref|last)|whRememberView\b|whAutoRememberFilters\b|whAutoRememberTabs\b", re.I)
# X2 · interruption resilience: a page that WRITES via a substantial free-text/compose form (a <textarea> the
# user types a post/message/report/journal/log entry into) should autosave a DRAFT so a refresh / interruption
# (a field-tech's connectivity blip, a phone call) doesn't lose the in-progress work.
_WRITES = re.compile(r"\.from\([^)]*\)\s*\.\s*(insert|upsert)|\bdb\.rpc\(|functions\.invoke\(", re.I)
_COMPOSE = re.compile(r"<textarea(?![^>]*\b(readonly|disabled)\b)", re.I)
_DRAFT = re.compile(r"localStorage\.(setItem|getItem)\([^)]*draft|whRememberDraft\b|whAutoSaveDraft\b|saveDraft|restoreDraft|wh_draft", re.I)


# Y1b · offline write-QUEUE adoption. A FIELD-CAPTURE page (a worker types real work the platform must
# not lose in a brownout — a job entry, a parts txn, a PM completion, an FMEA mode, a schedule item)
# must route its offline writes through a queue that drains on reconnect. The queue exists + is
# centralized: offline-queue.js `whCreateQueue`/`.enqueue`, or logbook's bespoke getPendingEntries/
# syncOfflineQueue. CAPTURE_TARGETS is a CURATED, evidence-verified denominator (like G5's 16
# filterable pages) — NOT every write page: approvals/moderation/financial/role writes are Y1d
# ONLINE-ONLY-with-clarity by design (the generic drain has no optimistic-lock `.is()` guard, so a
# queued approval could forge attribution on a stale drain — the P6-C1 lock class). Classify by
# evidence before adding a page here. Forward-only ratchet: a NEW capture page without a queue, or
# un-wiring an existing one, drops the pct below baseline → FAIL.
CAPTURE_TARGETS = {
    "logbook.html",       # job entries (bespoke queue: getPendingEntries/syncOfflineQueue)
    "inventory.html",     # parts transactions (whCreateQueue wh_inventory_offline)
    "pm-scheduler.html",  # PM completions (whCreateQueue wh_pm_offline)
    "asset-hub.html",     # FMEA capture (whCreateQueue wh_assethub_offline; 2026-07-23)
    "dayplanner.html",    # schedule items add/edit/delete (whCreateQueue wh_dayplanner_offline; 2026-07-23)
    "community.html",     # posts/replies capture — NOT yet wired (DB-generated id + X2-draft-protected text; heavier build)
    "skillmatrix.html",   # skill_profiles self-claim capture — NOT yet wired (competence record; verify approval-coupling first)
}
_QUEUE_WIRED = re.compile(r"whCreateQueue\s*\(|\.enqueue\s*\(|getPendingEntries|syncOfflineQueue", re.I)

# JA1 · DEEP-LINK ARRIVAL FIDELITY (§12, discovered by the LIVE Playwright-MCP journey walk 2026-07-23).
# A cross-page hand-off that NAMES an entity (alert-hub's "Review & stage" -> asset-hub.html?tag=...) must,
# on the NOT-FOUND path, either REFLECT the request in the UI (prefill the filter/search so the list is
# SCOPED and its empty state is truthful) or ANNOUNCE the miss. Silently falling through to the full
# unfiltered list is the failure: the user asked for ONE asset, sees 30 unrelated ones, and has no signal
# their target was missed (they may act on the wrong row). REAL bug found+fixed live: asset-hub read
# ?tag= and exact-matched, but its miss path did nothing (30 rows, no message); inventory.html?q= was
# already CORRECT (prefills its search box) - that contrast is what makes this dim discriminating.
# NOTE the existing `deep-link-params` gate is BLIND to this: it only asserts a .get() reader EXISTS,
# never that arrival is honoured or the miss is announced. Heuristic v1 (regex): a page that reads an
# entity deep-link param must show a param-prefill assignment OR a miss announcement. Forward-ratchet.
# JA2 · RETURN-PROMISE KEPT (§12 flywheel loop 2, found by the LIVE first-run journey walk 2026-07-23).
# The shared #hive-gate interstitial tells a brand-new user "You'll be brought back here once you're set
# up" - but its CTA was a BARE hive.html with no return target, and hive.html read no return/next/from
# param and never checked document.referrer, so the promise was STRUCTURALLY IMPOSSIBLE to keep: the user
# finishes setup and is stranded on the hive board. A UI promise the journey cannot honour is worse than
# no promise. Fixed centrally: utils.js stamps ?return=<page> on every gate CTA, hive.html renders a
# validated "Continue to X" banner. This dim locks BOTH halves: a page that PROMISES a return must load
# the central stamper (or hard-code the param), and the destination must READ it.
_RETURN_PROMISE = re.compile(r"brought back here|bring you back|back here once|return you here|we'?ll bring you", re.I)
_GATE_TO_HIVE = re.compile(r"""href=["']hive\.html""", re.I)
_RETURN_WIRED = re.compile(r"""utils\.js|[?&]return=""", re.I)
# JA3 · BACK DISMISSES AN OPEN OVERLAY (§12 flywheel loop 8, LIVE buy/RFQ walk 2026-07-23). Opening a
# marketplace listing did not change the URL, and pressing BACK - the universal "close this" gesture, and the
# ONLY one on Android gesture/hardware nav - threw the buyer OUT of the marketplace, losing the listing AND
# their browse position. Platform grep confirmed ZERO history.pushState + ZERO popstate handlers anywhere, so
# NO overlay on ANY page was Back-dismissible. (replaceState, used for deep-link URL sync, adds no history
# entry, so Back still leaves the page.) Fixed centrally in utils.js: an overlay gaining .open pushes one
# history entry; popstate closes it instead of navigating; a page-initiated close consumes the entry so
# history stays balanced. This dim locks it: a page that ships .sheet-overlay/.modal-overlay must LOAD the
# shared helper (utils.js) - a page hand-rolling an overlay without it regresses to the eject-the-user bug.
# NOTE: no word-boundary escapes here ON PURPOSE. Written through a Python heredoc they became
# literal BACKSPACE () chars, which compiled fine and matched NOTHING - a silently toothless
# dim reporting 0/0 = "100%". The class names are distinctive without them. Same class as
# feedback_python_heredoc_eats_js_regex_boundaries: print repr(pattern) whenever a NEW dim reads 0/0.
_HAS_OVERLAY = re.compile(r"""class=["'][^"']*(sheet-overlay|modal-overlay)""", re.I)
_BACK_DISMISS_WIRED = re.compile(r"""utils\.js|whOverlayBackDismiss|addEventListener\(\s*['"]popstate['"]""", re.I)
_DEEPLINK_READ = re.compile(r"""\.get\(\s*['"](?:tag|q|node_id|asset_id|asset|listing|order|worker|code)['"]\s*\)""")
# A miss must be ANNOUNCED, or the request REFLECTED by prefilling a control with the PARAM-DERIVED
# value. v1 accepted any `.value = <ident>` anywhere in the window - fault injection showed a big page
# has many unrelated assignments, so stripping asset-hub's real prefill+message still "passed". The
# prefill clause now requires the RHS to be the variable the deep-link param was assigned to.
# Real miss-announcement phrasings in this codebase: "Could not find X", "Seller not found",
# "No current alert for X: showing all alerts". Broad enough to accept a genuine announcement,
# narrow enough that ordinary page copy does not satisfy it (verified by fault injection).
_MISS_ANNOUNCE = re.compile(
    r"""could\s*not\s*find|couldn'?t\s*find|no\s+match(?:es)?\s+for"""
    r"""|not\s+found|no\s+current\s+\w+\s+for|showing\s+all""", re.I)

# A user-visible SINK: the text actually surfaces (toast/dialog/DOM write/render return). `void`,
# `console.log`, a dead concat or a bare literal are NOT sinks - they reach nobody.
_SINK_CALL = re.compile(
    r"(showToast|whToast|toast|whAnnounce|announce|whPrompt|whConfirm|whAlert"
    r"|setStatus|showMessage|showEmpty|renderEmpty|setEmpty|showBanner|setText)$", re.I)
_SINK_ASSIGN = re.compile(r"(textContent|innerHTML|innerText|placeholder|ariaLabel)\s*=|(?<![\w.])return\b")


def _reaches_user(win: str, idx: int) -> bool:
    """True if win[idx] sits inside a call to a user-visible sink, or in a statement that writes the
    DOM / returns markup to a renderer. Walks OUT through enclosing calls (up to 4 levels) so
    `showToast('...' + esc(x) + '...')` still counts while `void ('...' + x)` does not."""
    pos = idx
    for _ in range(4):
        depth = 0
        i = pos - 1
        while i >= 0:                       # walk back to the unmatched '(' that encloses pos
            c = win[i]
            if c == ')':
                depth += 1
            elif c == '(':
                if depth == 0:
                    break
                depth -= 1
            i -= 1
        if i < 0:
            break
        if _SINK_CALL.search(win[max(0, i - 40): i].rstrip()):
            return True
        pos = i                             # step out one level and re-test
    # Inside a multi-line TEMPLATE LITERAL the enclosing `innerHTML = \`` sits many lines above the
    # match (seller-profile renders its whole not-found empty-state as markup), so a statement-scan
    # back to the nearest newline finds nothing. If the position is inside a template literal (odd
    # backtick parity), test the code that INTRODUCES that literal instead.
    if win.count('`', 0, idx) % 2 == 1:
        open_tick = win.rfind('`', 0, idx)
        if _SINK_ASSIGN.search(win[max(0, open_tick - 90): open_tick]):
            return True
    stmt = max(win.rfind(';', 0, idx), win.rfind('{', 0, idx), win.rfind('\n', 0, idx))
    return bool(_SINK_ASSIGN.search(win[stmt + 1: idx]))


_NONPROD = re.compile(r"backup|\.bak\b|-test\.|\.test\.|\.old\b|\.orig\b|copy", re.I)


def app_pages() -> list[Path]:
    # production surfaces only: skip the EXCLUDE consoles/artifacts AND backup/test/old copies (logbook.backup.html
    # etc.) that pollute the denominator — the "derive the denominator, don't count non-production" discipline.
    return [p for p in sorted(ROOT.glob("*.html")) if p.name not in EXCLUDE and not _NONPROD.search(p.name)]


def measure() -> dict:
    pages = app_pages()
    j3_tot = j3_ok = 0
    g5_tot = g5_ok = 0
    s4_tot = s4_bad = 0
    x2_tot = x2_ok = 0
    y1b_tot = y1b_ok = 0
    ja1_tot = ja1_ok = 0
    ja2_tot = ja2_ok = 0
    ja3_tot = ja3_ok = 0
    j3_gaps, g5_gaps, s4_gaps, x2_gaps, y1b_gaps = [], [], [], [], []
    ja1_gaps = []
    ja2_gaps = []
    ja3_gaps = []
    for p in pages:
        src = p.read_text(encoding="utf-8", errors="replace")
        # J3: pages with a destructive handler must use whConfirm
        if _DESTRUCTIVE.search(src):
            j3_tot += 1
            if _WHCONFIRM.search(src) or _UNDO_SAFE.search(src):
                j3_ok += 1
            else:
                j3_gaps.append(p.name)
            # S4: destructive-action page must use the SHARED confirm, not a raw window.confirm()
            s4_tot += 1
            if _RAWCONFIRM.search(src) and not _WHCONFIRM.search(src):
                s4_bad += 1
                s4_gaps.append(p.name)
        # G5: pages with a filter/sort control should persist the choice
        if _FILTER_CTL.search(src):
            g5_tot += 1
            if _PERSIST.search(src):
                g5_ok += 1
            else:
                g5_gaps.append(p.name)
        # X2: a write-page with a compose <textarea> should autosave a draft (interruption resilience)
        if _COMPOSE.search(src) and _WRITES.search(src):
            x2_tot += 1
            if _DRAFT.search(src):
                x2_ok += 1
            else:
                x2_gaps.append(p.name)
        # JA1: a page entered via an entity deep-link must reflect the request or announce the miss.
        # ★PROXIMITY-SCOPED (fixed 2026-07-23 by fault injection). v1 searched the WHOLE file for the
        # arrival evidence, and `.value = <ident>` occurs dozens of times on any big page - so JA1 read
        # 11/11 = "100%" while measuring almost nothing: stripping asset-hub's real prefill + miss
        # message did NOT drop it. The evidence must live NEAR the deep-link read to be evidence AT ALL.
        # ★STRIP COMMENTS BEFORE LOOKING FOR ARRIVAL EVIDENCE (4th time a comment fooled a scanner this
        # session). The fix comments I wrote on these very pages say "...must say plainly that we could
        # not find it", so the detector matched MY PROSE, not the code: deleting the real prefill and the
        # real toast still "passed". Evidence must come from executable code only.
        _code = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
        _code = re.sub(r"/\*.*?\*/", " ", _code, flags=re.S)
        _code = re.sub(r"(?m)^\s*//.*$", " ", _code)
        _dl = list(_DEEPLINK_READ.finditer(_code))
        if _dl:
            ja1_tot += 1
            # Evidence may sit right after the read (inline handling) OR near a USE of the variable the
            # param was assigned to - `const WORKER_VIEW = ...get('worker')` read at module scope but
            # handled far below in a loader is a legitimate, common shape. Track both, so the dim is
            # neither file-wide (meaningless) nor window-only (false negatives on that shape).
            # Windows are SYMMETRIC: the miss-message often sits BEFORE the variable use
            # (`We could not find a seller named "${escHtml(WORKER_VIEW)}"`), so an after-only
            # window produced false negatives on pages that DO handle the miss correctly.
            # Windows are SPANS over _code, not slices: the sink walk needs REAL surrounding context
            # (backtick parity, enclosing calls). A 2000-char slice can start mid-template-literal and
            # invert that parity, which flipped a correct page (seller-profile) to a false FAIL.
            def _win(i, back, fwd):
                return (max(0, i - back), min(len(_code), i + fwd))
            _spans = [_win(m.end(), 200, 2000) for m in _dl]
            for m in _dl:
                _pre = _code[max(0, m.start() - 200): m.start()]
                _var = re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=[^;]*$", _pre)
                if _var:
                    for u in re.finditer(r"\b" + re.escape(_var[-1]) + r"\b", _code[m.end():]):
                        _spans.append(_win(m.end() + u.start(), 400, 400))
            _windows = [_code[s:e] for s, e in _spans]
            _vars = []
            for m in _dl:
                _pre2 = _code[max(0, m.start() - 200): m.start()]
                _v = re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=[^;]*$", _pre2)
                if _v: _vars.append(_v[-1])
            # ★A STRING IS NOT AN ANNOUNCEMENT UNTIL IT REACHES A USER. Fault injection proved this:
            # replacing `showToast('Could not find "' + x + '": showing all PM assets')` with
            # `void ('' + x + '": showing all PM assets')` deletes the entire user-facing behaviour, yet
            # the literal survives in source, so a bare-string match still scored it PASS. Require the
            # matched text to sit inside a user-visible SINK (toast/dialog/DOM-write/return-to-render).
            _announced = any(
                _reaches_user(_code, s + m.start())
                for s, e in _spans for m in _MISS_ANNOUNCE.finditer(_code[s:e])
            )
            # PREFILL evidence: either the param VAR is assigned to a control's .value, or the read is
            # handed straight to a setter helper (logbook: `_setIf('search-input', _lq.get('q'))`) - the
            # value then never appears as `.value = var` at the call site, but the request IS reflected.
            # ★The helper clause must name a CONTROL. An earlier version accepted any call containing a
            # `.get(` - which `decodeURIComponent(urlParams.get('worker'))` satisfies, so EVERY page
            # passed: a rubber stamp. Fault injection caught it (3 of 4 removals went undetected).
            # A real prefill helper takes an element-id STRING first, then the param value:
            #   _setIf('search-input', _lq.get('q'))
            # Both clauses are WINDOWED. File-wide searching made this a rubber stamp twice over: a big
            # page always has SOME `.value =` and SOME `fn('id', x.get('y'))` somewhere. Evidence only
            # counts as arrival evidence if it sits near the deep-link read (or a use of its variable).
            _prefilled = any(
                re.search(r"\.value\s*=\s*" + re.escape(v) + r"\b", w)
                for v in _vars for w in _windows
            ) or any(
                re.search(r"""\w+\s*\(\s*['"][\w-]+['"]\s*,[^)]*\.get\s*\(""", w) for w in _windows
            )
            if _announced or _prefilled:
                ja1_ok += 1
            else:
                ja1_gaps.append(p.name)
        # JA2: a page that PROMISES a return after a gate detour must carry/inherit the return target
        if _RETURN_PROMISE.search(src) and _GATE_TO_HIVE.search(src):
            ja2_tot += 1
            if _RETURN_WIRED.search(src):
                ja2_ok += 1
            else:
                ja2_gaps.append(p.name)
        # JA3: a page shipping a shared overlay must load the central Back-dismiss helper
        if _HAS_OVERLAY.search(src):
            ja3_tot += 1
            if _BACK_DISMISS_WIRED.search(src):
                ja3_ok += 1
            else:
                ja3_gaps.append(p.name)
        # Y1b: a curated FIELD-CAPTURE page must route offline writes through a drain-on-reconnect queue
        if p.name in CAPTURE_TARGETS:
            y1b_tot += 1
            if _QUEUE_WIRED.search(src):
                y1b_ok += 1
            else:
                y1b_gaps.append(p.name)
    def pct(a, b):
        return round(100 * a / b, 1) if b else 100.0
    return {
        "pages": len(pages),
        "J3": {"total": j3_tot, "ok": j3_ok, "pct": pct(j3_ok, j3_tot), "gaps": j3_gaps},
        "G5": {"total": g5_tot, "ok": g5_ok, "pct": pct(g5_ok, g5_tot), "gaps": g5_gaps},
        "S4": {"total": s4_tot, "ok": s4_tot - s4_bad, "pct": pct(s4_tot - s4_bad, s4_tot), "gaps": s4_gaps},
        "X2": {"total": x2_tot, "ok": x2_ok, "pct": pct(x2_ok, x2_tot), "gaps": x2_gaps},
        "Y1b": {"total": y1b_tot, "ok": y1b_ok, "pct": pct(y1b_ok, y1b_tot), "gaps": y1b_gaps},
        "JA3": {"total": ja3_tot, "ok": ja3_ok, "pct": pct(ja3_ok, ja3_tot), "gaps": ja3_gaps},
        "JA2": {"total": ja2_tot, "ok": ja2_ok, "pct": pct(ja2_ok, ja2_tot), "gaps": ja2_gaps},
        "JA1": {"total": ja1_tot, "ok": ja1_ok, "pct": pct(ja1_ok, ja1_tot), "gaps": ja1_gaps},
    }


def self_test() -> bool:
    ok = True
    good = '<button onclick="deletePost(1)">x</button><script>whConfirm("sure?")</script>'
    bad = '<button onclick="deleteThing(1)">x</button>'
    if not (_DESTRUCTIVE.search(good) and _WHCONFIRM.search(good)):
        print(f"{R}selftest FAIL: good J3 not recognized{X}"); ok = False
    if not (_DESTRUCTIVE.search(bad) and not _WHCONFIRM.search(bad)):
        print(f"{R}selftest FAIL: bad J3 not caught{X}"); ok = False
    if not _PERSIST.search("localStorage.setItem('wh_asset_view', v)"):
        print(f"{R}selftest FAIL: G5 persist not recognized{X}"); ok = False
    if not _QUEUE_WIRED.search("window.whCreateQueue({db:'x',table:'t'})"):
        print(f"{R}selftest FAIL: Y1b queue-wire not recognized{X}"); ok = False
    if _QUEUE_WIRED.search("<script defer src=\"offline-queue.js\"></script>"):
        print(f"{R}selftest FAIL: Y1b false-positive on a mere script LOAD (must require an actual call){X}"); ok = False
    # JA1 is checked through _reaches_user, the clause fault injection proved load-bearing: the miss text
    # must reach a USER, not merely exist in source. Each case below is a regression this dim actually
    # missed at some point during its construction.
    ja_good = "const t = params.get('tag'); showToast('Could not find \"' + t + '\"');"
    ja_bad = "const t = params.get('tag'); if (hit) openDetail(hit.id);"
    ja_void = "const t = params.get('tag'); void ('' + t + '\": showing all assets');"   # dead string
    ja_console = "const t = params.get('tag'); console.log('could not find ' + t);"      # dev-only
    ja_tpl = "const t = p.get('worker');\nel.innerHTML = `<h3>Seller not found</h3>\n<p>We could not find ${t}</p>`;"
    ja_comment = "const t = params.get('tag');\n// we must say we could not find it\nopenDetail(t);"
    for label, sample, want in (
        ("plain toast", ja_good, True), ("template innerHTML", ja_tpl, True),
        ("silent drop", ja_bad, False), ("void'd dead string", ja_void, False),
        ("console.log only", ja_console, False), ("comment-only prose", ja_comment, False),
    ):
        code = re.sub(r"(?m)^\s*//.*$", " ", sample)
        hit = any(_reaches_user(code, m.start()) for m in _MISS_ANNOUNCE.finditer(code))
        if not _DEEPLINK_READ.search(sample):
            print(f"{R}selftest FAIL: JA1 sample '{label}' has no deep-link read{X}"); ok = False
        if hit != want:
            print(f"{R}selftest FAIL: JA1 '{label}' -> announced={hit}, expected {want}{X}"); ok = False
    j2_good = 'brought back here <a href="hive.html">go</a> <script src="utils.js">'
    j2_bad  = 'brought back here <a href="hive.html">go</a>'
    if not (_RETURN_PROMISE.search(j2_good) and _GATE_TO_HIVE.search(j2_good) and _RETURN_WIRED.search(j2_good)):
        print(f"{R}selftest FAIL: JA2 wired promise not recognized{X}"); ok = False
    if _RETURN_WIRED.search(j2_bad):
        print(f"{R}selftest FAIL: JA2 unwired promise not caught{X}"); ok = False
    print((G + "selftest PASS - journey-ux-dims has teeth." + X) if ok else (R + "selftest FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    m = measure()
    REPORT.write_text(json.dumps(m, indent=1), encoding="utf-8")
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    if "--accept" in sys.argv or not base:
        base = {k: m[k]["pct"] for k in ("J3", "G5", "S4", "X2", "Y1b", "JA1", "JA2", "JA3")}
        BASELINE.write_text(json.dumps(base, indent=1), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2)); return 0
    print(f"{B}journey-ux dims (J3 consequence · G5 memory · S4 behavioral · X2 interruption · Y1b offline-queue · JA1 arrival · JA2 return-promise · JA3 back-dismiss) — source-grep{X}")
    regressed = False
    for dim in ("J3", "G5", "S4", "X2", "Y1b", "JA1", "JA2", "JA3"):
        d = m[dim]; b = base.get(dim, d["pct"])
        tag = G + "OK" + X if d["pct"] >= b else R + "REGRESSED" + X
        if d["pct"] < b:
            regressed = True
        print(f"  {tag}  {dim}: {d['ok']}/{d['total']} = {d['pct']}% (baseline {b}%)" + (f"  gaps: {d['gaps'][:4]}" if d["gaps"] else ""))
    if regressed:
        print(f"{R}FAIL: a journey-ux dim dropped below baseline.{X}"); return 1
    print(f"{G}PASS - J3/G5/S4/X2/Y1b/JA1/JA2/JA3 held (report → journey_ux_dims_report.json).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
