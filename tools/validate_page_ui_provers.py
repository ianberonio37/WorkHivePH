#!/usr/bin/env python3
"""
validate_page_ui_provers.py — the gate wrapper for the PAGE TESTBANK's four BROWSER provers.

The CJ/CK/CM oracles cannot be settled from source. Each of these four needs a real signed-in page:

  viewport_overflow  CJ w390/w641/w1280 + tap_target_44 — measures the browser's own scale factor and
                     DIVIDES by it before reporting a width, because the MCP browser runs at 1.5x and
                     an unscaled read invented 142 of 398 "offenders". Splits true offenders from
                     ancestor-clipped ones, and refuses to report a width it could not verify.
  component_states   CK component_loading/skeleton/busy — arms its recorder in addInitScript BEFORE
                     first paint (arming at `interactive` lost the first 650ms and banked "no loading
                     state" for components that had one), runs a positive control per page, and
                     re-checks stuck candidates after +9s so SLOW is not reported as STUCK.
  number_labelled    CM what_is_this_number — every leaf whose whole text is a number needs a label
                     within 4 ancestors, with a non-vacuity control injecting a bare 4242 that MUST
                     come back unlabelled, and a readiness check so a half-painted page is reported
                     rather than counted.
  safe_area          CJ safe_area — reads the AUTHORED css over CDP (CSS.getMatchedStylesForNode),
                     because headless computes env(safe-area-inset-*) to 0px and a computed read
                     cannot tell "declared" from "absent". Matches the inset DIRECTION to the edge.

ONE wrapper, four registrations: the gate ids stay separate so a failure names the oracle that broke,
without four copies of the same subprocess plumbing drifting apart.

Skips cleanly (exit 0) when node or the local stack is absent, matching validate_arc_u_focus_trap.py —
these are local-only live gates. A real regression is exit 1.
"""
import argparse
import io
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

PROVERS = {
    "viewport_overflow": ("prove_viewport_overflow.mjs", "viewport_overflow_report.json",
                          "CJ layout: no unclipped horizontal overflow at 390/641/1280, "
                          "every effective tap target >= 44px"),
    "component_states":  ("prove_component_states.mjs", "component_states_report.json",
                          "CK state: no component stuck in loading/skeleton, controls fire"),
    "number_labelled":   ("prove_number_labelled.mjs", "number_labelled_report.json",
                          "CM comprehension: every rendered number carries a label naming it"),
    "safe_area":         ("prove_safe_area.mjs", "safe_area_report.json",
                          "CJ safe-area: edge-pinned chrome declares the inset for ITS OWN edge"),
    "back_out":          ("prove_back_out.mjs", "back_out_report.json",
                          "CO recovery: the in-app way out lands where wayfinding.js's contract says, "
                          "proven on BOTH the referrer branch and the parent-map branch"),
    "session_died":      ("prove_session_died.mjs", "session_died_report.json",
                          "CO recovery: a dead session is never presented as signed-in data — the "
                          "page redirects, prompts, or explains, but never renders confident zeros"),
    "why_refused":       ("prove_why_refused.mjs", "why_refused_report.json",
                          "CM comprehension: a 42501 read refusal is explained by NAMING permission — never "
                          "blamed on identity, never left as a bare generic error or silence"),
    "dialog_back_out":   ("prove_dialog_back_out.mjs", "dialog_back_out_report.json",
                          "CO recovery for TAB/SECTION views: with the view OPEN, the page-level way out is "
                          "still present and still lands where wayfinding.js says"),
    "dialog_session_died": ("prove_dialog_session_died.mjs", "dialog_session_died_report.json",
                          "CO recovery at V2/V3: with the session killed, no dialog/tab/section opens and "
                          "presents stale figures as real — unreachable counts, and is the honest answer"),
    "modal_escape":      ("prove_modal_escape_adoption.mjs", "modal_escape_adoption_report.json",
                          "CO recovery, ADOPTION half: every V2/V3 dialog view has a keyboard way out, "
                          "and the ones that hand-roll it instead of using whModalA11y are recorded"),
    "dialog_layout":     ("prove_dialog_layout.mjs", "dialog_layout_report.json",
                          "CJ layout INSIDE the opened V2/V3 dialogs: no unclipped overflow at 390 and "
                          "every effective tap target >= 44px, on the same ruler V1 used"),
    # The two CONTRAST provers, which existed and were invokable from NOWHERE -- built, working,
    # registered in no suite and no PROVERS map, so they enforced nothing. Same orphan shape as
    # validate_em_dash.py. They drive the platform's OWN two calibrated lenses (live-state-runner's
    # composited APCA + axe's WCAG) rather than adding a third implementation, which is why the
    # 78 owed contrast rows are settleable at all.
    # REGISTERED and PROVEN (2026-08-20). This note used to read "NOT YET ADDED to
    # run_platform_checks ... prove them, THEN register" -- and by the time anyone read it BOTH
    # halves were false: they were already registered (run_platform_checks.py:546 / :555) and the
    # teeth had simply never been run. Trusting it cost a duplicate registration before the
    # registry was checked, which is the standing lesson: the PROSE goes stale, the REGISTRY is
    # the truth. Teeth now measured: page_contrast 26/26 pages and view_contrast 43/43 views
    # caught the planted violator on BOTH lenses; clean runs are 0 failing on each.
    "page_contrast":     ("prove_page_contrast.mjs", "page_contrast_report.json",
                          "CL ui-visual: BOTH contrast oracles on every production page, populated. "
                          "Drives live-state-runner's composited APCA and axe's WCAG side by side; "
                          "writes no contrast maths of its own"),
    "view_contrast":     ("prove_view_contrast.mjs", "view_contrast_report.json",
                          "CL ui-visual inside the opened V2/V3 dialogs, 43 targets across 22 pages"),
    "dialog_a11y":       ("prove_dialog_a11y.mjs", "dialog_a11y_report.json",
                          "CL ui-visual inside the opened V2/V3 dialogs: every control has an accessible "
                          "name, focus is visible (driven by Tab, not el.focus), nothing moves under "
                          "prefers-reduced-motion; contrast NOT claimed and those rows stay owed"),
    "modal_escape_live": ("prove_modal_escape_live.mjs", "modal_escape_live_report.json",
                          "CO recovery, BEHAVIOUR half: Escape actually closes each dialog and focus "
                          "returns to the opener wherever a real opener element was clicked"),
    "failure_injection": ("prove_failure_injection.mjs", "failure_injection_report.json",
                          "CC failure-injection on the 20 pages the marketplace spec never reaches: a "
                          "failed read must render a FAILURE, never an EMPTINESS or a silent shrink. "
                          "500/401/timeout/offline, injected before the supabase client is constructed "
                          "so the patch cannot be a late no-op, and hit-counted so a zero-hit page is "
                          "UNGRADED rather than judged"),
    "quota_legible":     ("prove_quota_legible.mjs", "quota_legible_report.json",
                          "CM what_does_it_cost, the QUOTA half: a rate limit must be reported AS a rate "
                          "limit. Model quota is invisible until you hit it, so the constraint is INDUCED "
                          "— every AI/orchestrator invoke is answered 429 and the surface is read. Locks a "
                          "class found three times: assistant collapsed every gateway failure into one "
                          "null and said 'retry on a faster connection'; shift-brain matched 429 with a "
                          "network-error regex and told a supervisor to run 'npx supabase functions "
                          "serve'; report-sender carried a comment asserting invoke() parses the body on a "
                          "non-2xx, which it does not, so the toast fell through to 'check connection'. "
                          "All three sent someone chasing bandwidth while the connection was fine and the "
                          "service was busy. Messages are sampled ACROSS the window (they are ~1s toasts) "
                          "and controls are clicked in-page (some are hidden), because both shortcuts "
                          "previously produced a false 'the surface said nothing'. A page whose action "
                          "draws no invoke is UNGRADED, never failed"),
    "reward_explained":  ("prove_reward_explained.mjs", "reward_explained_report.json",
                          "CM comprehension: a reward figure (XP, level, tier) carries its CRITERIA in its "
                          "OWN card — what earns it, or the threshold it sits at. A page with no reward on "
                          "screen is not applicable and stays owed, never failed"),
    "domain_truth":      ("prove_domain_truth.mjs", "domain_truth_report.json",
                          "CI domain-truth: the ENGINEERING claims — a metric names its standard and its "
                          "basis, a partial figure is labelled partial, a reorder names its threshold. "
                          "Patterns harvested from live renders only, never invented, and every check "
                          "ships a planted satisfying/violating pair so one that cannot fire is caught "
                          "before it banks a green"),
    "journey":           ("prove_journey.mjs", "journey_report.json",
                          "CN ux-journey J1/J2: a first-timer reaches value without a dead end, and a "
                          "returning person is not made to redo setup — walked as each page's OWN "
                          "grounded persona, where an onboarding screen shown over a FAILED read counts "
                          "as a failure rather than as value"),
}


# Provers that read SOURCE only — no browser, no page server, so they must run even when the stack is
# down. Everything else here needs a signed-in live page.
STATIC = {"modal_escape"}

# ★ A TIMEOUT SHORTER THAN THE WORK IS A GATE THAT CAN ONLY FAIL. The shared 900s ceiling was set for
# provers that walk a page once. `failure_injection` walks TWENTY pages through a healthy control plus
# SEVEN injected modes, and each walk deliberately out-waits the platform's own timeouts — 11s for the
# hang mode, 8.5s for the slow mode, 5s otherwise. That is ~90s per page and ~30 MINUTES for the sweep,
# so the gate reported "exceeded 900s — a hung browser is a broken gate, not a pass" on a prover that
# was working correctly and had never once fit in its budget. Measured 2026-08-14, after the run that
# produced 140 graded cells completed fine when invoked directly.
# The distinction the message draws is the right one — a HUNG browser must fail — so the fix is to
# budget each prover for the work it actually does, not to remove the ceiling.
TIMEOUT_S = {
    "failure_injection": 2700,
    # Six pages, each held at 429 and then sampled across an 8s window rather than read at its end —
    # the sampling is the point, so the budget has to cover it.
    "quota_legible": 900,
}
DEFAULT_TIMEOUT_S = 900


def stack_up() -> bool:
    """Flask :5000 serves the pages; without it every prover measures a connection error."""
    try:
        with socket.create_connection(("127.0.0.1", 5000), timeout=2):
            return True
    except OSError:
        return False


def edge_up() -> bool:
    """
    ★ A DEAD EDGE RUNTIME CONTAMINATES A 30-MINUTE SWEEP SILENTLY, AND THE PAGES BLAME THEMSELVES.

    Measured 2026-08-15: `supabase_edge_runtime_workhive` exited (255) mid-run. analytics fell from
    4138 chars to 1211 and rendered "name resolution failed · Network problem: check your connection"
    and "Analytics unavailable" — which is the page behaving CORRECTLY about a broken dependency, and
    is indistinguishable from a page defect to any oracle reading the screen. Every edge-backed page
    (analytics, shift-brain, assistant, hive, logbook, asset-hub, project-report) would have been
    graded against a stack that was not running, and a sweep taken then is not a slow reading — it is
    a WRONG one, banked as evidence.

    This platform already has the lesson twice ("name resolution failed was a STOPPED container";
    "verify the INSTRUMENT before the page"), and both times the move was `docker start`. So the check
    belongs in the harness, before the 30 minutes are spent, not in my memory afterwards.

    Deliberately a SKIP, not a FAIL: a missing local dependency is not a product regression, and
    failing here would train people to ignore the gate. It says exactly what to run.
    """
    try:
        with socket.create_connection(("127.0.0.1", 54321), timeout=2):
            return True
    except OSError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prover", required=True, choices=sorted(PROVERS))
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    script, report, what = PROVERS[a.prover]
    probe = ROOT / "tools" / script

    print("\n" + "=" * 72)
    print(f"  PAGE TESTBANK browser prover — {a.prover}")
    print(f"  {what}")
    print("=" * 72)

    if shutil.which("node") is None:
        print(f"  SKIP: node not on PATH — {a.prover} not evaluated (local-only live gate).")
        return 0
    if not probe.exists():
        print(f"  FAIL: tools/{script} missing — the prover was removed while its gate stayed registered.")
        return 1

    # ★ A PROVER WHOSE SOURCE CONTAINS CONTROL BYTES CANNOT BE TRUSTED TO FAIL, so it is not allowed to
    # report a pass. Measured 2026-08-14: an intended `\b` word boundary in prove_failure_injection.mjs
    # became a literal BACKSPACE (0x08) while the file was being written through nested quoting layers
    # (bash heredoc -> Python -> JS -> regex). The detector became
    #     /<BS>(null|undefined)<BS>/i
    # which matches a control character beside the word and therefore CANNOT FIRE — so fail_null_field
    # reported "no raw null reached the screen" on every page while checking nothing.
    # Nothing catches this otherwise: `node --check` parses it happily, the byte does not render in an
    # editor, and the output is a clean sweep of greens. A false RED gets triaged; a false GREEN gets
    # banked and believed. So the check lives HERE, in the one wrapper all 15 provers pass through, rather
    # than in each prover's own head — the same reason dialog_targets.mjs is read by four provers instead
    # of remembered four times.
    _raw = probe.read_bytes()
    _ctrl = sorted({b for b in _raw if b < 9 or 10 < b < 13 or 13 < b < 32})
    if _ctrl:
        print(f"  FAIL: tools/{script} contains control byte(s) {_ctrl} — an escape was eaten by whatever "
              f"wrote the file (a `\\b` becoming 0x08 is the usual one). The regex it landed in cannot "
              f"fire, so this prover would report passes it never tested. Refusing to run it.")
        return 1
    # STATIC provers read source and need no page server. Gating them on the stack would SKIP a check
    # that could have run — a skip reads as "fine" and is how a partition silently leaves the denominator.
    if a.prover not in STATIC and not stack_up():
        print(f"  SKIP: local page server 127.0.0.1:5000 is down — {a.prover} not evaluated.")
        return 0
    # The edge gateway must be reachable BEFORE the sweep starts, or edge-backed pages are graded
    # against a stack that is not running and every one of them looks broken. See edge_up().
    if a.prover not in STATIC and not edge_up():
        print(f"  SKIP: the Supabase edge gateway 127.0.0.1:54321 is unreachable — {a.prover} not\n"
              "        evaluated. Edge-backed pages would render their (correct) 'name resolution\n"
              "        failed' handling, and the walk would grade that as a page defect.\n"
              "        Fix: docker start supabase_edge_runtime_workhive")
        return 0

    budget = TIMEOUT_S.get(a.prover, DEFAULT_TIMEOUT_S)
    try:
        r = subprocess.run(["node", str(probe), "--gate"], cwd=str(ROOT), timeout=budget,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print(f"  FAIL: {script} exceeded {budget}s — a hung browser is a broken gate, not a pass.")
        return 1

    tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-14:]
    for ln in tail:
        print("  " + ln.rstrip())
    if r.returncode != 0 and (r.stderr or "").strip():
        print("  stderr: " + (r.stderr or "").strip()[:400])

    if not (ROOT / report).exists():
        print(f"  FAIL: {report} was not written — the prover did not complete a measurement.")
        return 1
    print(f"  {'PASS' if r.returncode == 0 else 'FAIL'} — {a.prover} (report: {report})")
    return 1 if r.returncode != 0 else 0


if __name__ == "__main__":
    sys.exit(main())
