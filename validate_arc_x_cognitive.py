"""
Arc X - Cognitive Load II : COGNITIVE-LOAD HARD GATE
=====================================================
The deterministic gate for Arc X (task-continuity & real-user cognitive load).
See COGNITIVE_LOAD_II_ROADMAP.md for the full 6-family / 14-type lens model and
the HARD-gate vs SOFT-judge contract (only deterministic proxies GATE here; soft
signals are warn-only and judged by Ian's eye, never auto-green).

LAYERS (activated phase by phase; each is a deterministic, low-false-positive proxy)
  L1  Real-login HIVE RESOLUTION (Issue #1, X0 validity fix)  [ACTIVE]
        The real index.html front-door login MUST resolve the signed-in user's
        active hive from their hive_members truth and populate the 4 wh_* keys,
        the way only the WorkHive Tester used to. Without this, a front-door user
        lands in solo-mode on the WRONG/empty dashboard, and a second user signing
        in on the same browser inherits the first user's tenant (a cross-tenant
        leak). This layer locks the fix statically so it can never silently
        regress (the bug every prior arc audit masked by reusing a Tester session).
  L2  Family A - Generic-landing hand-off (A1 deep-links)     [X1 - pending baseline]
        Entity-specific alert/tile/row copy must emit a deep-link param so the
        destination can pre-focus the named record (mirror utils.js renderRiskStrip).
        Ratcheted against arc_x_baseline.json once the sweep banks the baseline.

This file is teeth-proven: breaking any L1 wiring assertion drives RC1; restoring
it drives RC0 (demonstrated at build time, X0).

Usage:  python validate_arc_x_cognitive.py
Output: arc_x_cognitive_report.json   (RC1 on any HARD failure)
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

INDEX = "index.html"
BASELINE = "arc_x_baseline.json"
HIVE_KEYS = ("wh_active_hive_id", "wh_hive_id", "wh_hive_name", "wh_hive_role")

CHECKS = {
    "resolve_helper_defined":   "L1  index.html defines resolveActiveHiveContext (front-door hive resolver)",
    "resolve_uses_truth_view":  "L1  resolver reads canonical membership truth (v_worker_truth), not a raw table",
    "resolve_clears_first":     "L1  resolver clears the 4 hive keys BEFORE setting (no cross-tenant inheritance)",
    "resolve_sets_all_keys":    "L1  resolver writes all 4 hive keys on a resolved membership",
    "called_from_signin":       "L1  submitSignIn calls the resolver before rendering the dashboard",
    "called_from_signup":       "L1  submitSignUp calls the resolver before rendering the dashboard",
    "called_from_restore":      "L1  the ops-home reload/restore path resolves when keys are absent",
    "signout_clears_hive":      "L1  signOut clears all 4 hive keys (the clear half of the leak fix)",
    "a1_deeplinks_present":     "L2  A1: every entity-naming alert/tile/row/hero deep-links to the named record",
    "a1_readers_present":       "L2  A1: every deep-link destination has a reader that pre-focuses the record",
    "a2_action_focus_present":  "L2  A2: a deep-linked detail lands with the matching action focused (carry intent)",
    "a3_state_persistence_present": "L2  A3: list filter state is mirrored to the URL so it survives reload/back-nav",
    "c2_seed_labels_present":   "L3  C2: front-door auth/join inputs carry a persistent label (not placeholder-only)",
    "c2_family_labels_present": "L3  C2: the dynamic/utility inputs (analytics search, PM wizard row, validator-catalog filter) keep a persistent aria-label",
    "c1_pickers_present":       "L3  C1: recall-dependent entity inputs offer a picker (inventory part-number datalist) instead of cold recall",
    "c3_status_on_record_present": "L3  C3: every canonical record-card surface renders a status/last-action/timestamp element (external memory for status)",
    "b2_scent_labels_present":  "L4  B2: contentless link/button labels (View/Open) carry an aria-label naming the object (information scent)",
    "b3_dead_end_cta_present":  "L4  B3: first-run empty states that named an action keep a clickable next-step CTA (no dead-end)",
    "e3_confirm_present":       "L4  E3: destructive controls (verification-badge revoke, delete-contact) confirm before destroying saved data",
    "e2_error_announced_present": "L4  E2: inline validation errors are announced to assistive tech (role=alert / aria-live) so the user knows what went wrong",
}
CHECK_LABELS = CHECKS
CHECK_NAMES = list(CHECKS.keys())


def _window(content, anchor_regex, chars):
    """Return the substring starting at the first match of anchor_regex spanning
    `chars` characters, or None if the anchor is absent."""
    m = re.search(anchor_regex, content)
    if not m:
        return None
    return content[m.start(): m.start() + chars]


def check_l1_login_resolution(content):
    issues = []

    # --- the resolver helper itself -------------------------------------------
    helper = _window(content, r"function\s+resolveActiveHiveContext\s*\(", 2400)
    if helper is None:
        issues.append({"check": "resolve_helper_defined", "reason":
            "index.html must define resolveActiveHiveContext(db, displayName) - the "
            "front-door resolver that mirrors hive.html's canonical hive resolution. "
            "Without it the real login never populates the hive context (Issue #1)."})
        # The remaining helper-body checks cannot run without the helper; flag them.
        for c in ("resolve_uses_truth_view", "resolve_clears_first", "resolve_sets_all_keys"):
            issues.append({"check": c, "reason": "resolver helper not found - cannot verify its body."})
    else:
        if "v_worker_truth" not in helper:
            issues.append({"check": "resolve_uses_truth_view", "reason":
                "resolveActiveHiveContext must read v_worker_truth (the canonical membership "
                "view hive.html uses), so the front door resolves the SAME truth as every other path."})
        # clears-before-set: a removeItem of the keys must appear in the helper body
        if not re.search(r"removeItem", helper):
            issues.append({"check": "resolve_clears_first", "reason":
                "resolveActiveHiveContext must clear the hive keys (removeItem) up front so "
                "identity B never inherits identity A's hive (the cross-tenant leak)."})
        missing_sets = [k for k in HIVE_KEYS
                        if not re.search(r"setItem\(\s*['\"]" + re.escape(k) + r"['\"]", helper)]
        if missing_sets:
            issues.append({"check": "resolve_sets_all_keys", "reason":
                "resolveActiveHiveContext must setItem all 4 hive keys on a resolved "
                "membership; missing: " + ", ".join(missing_sets) + ". A partial write leaves "
                "downstream pages falling back to solo/worker defaults."})

    # --- wired into every identity-establishing site --------------------------
    signin = _window(content, r"async\s+function\s+submitSignIn\s*\(", 3600)
    if signin is None or "resolveActiveHiveContext(" not in signin:
        issues.append({"check": "called_from_signin", "reason":
            "submitSignIn must call resolveActiveHiveContext(db, displayName) after setting "
            "wh_last_worker and BEFORE flipping to the dashboard, or the front-door login "
            "renders the wrong/empty (solo-mode) view (Issue #1)."})

    signup = _window(content, r"async\s+function\s+submitSignUp\s*\(", 6000)
    if signup is None or "resolveActiveHiveContext(" not in signup:
        issues.append({"check": "called_from_signup", "reason":
            "submitSignUp must call resolveActiveHiveContext so a returning worker claiming "
            "their records lands on their real hive (and a brand-new account is cleanly solo)."})

    restore = _window(content, r"_showOpsHome\s*=\s*async", 1400)
    if restore is None or "resolveActiveHiveContext(" not in restore:
        issues.append({"check": "called_from_restore", "reason":
            "the ops-home restore path (_showOpsHome) must resolve the hive when wh_active_hive_id "
            "is absent (new device / cleared storage / a returning user from before this fix), "
            "otherwise a reload shows solo-mode on the wrong view."})

    # --- signOut clears the hive keys (the clear half of the leak fix) ---------
    signout = _window(content, r"async\s+function\s+signOut\s*\(", 700)
    if signout is None:
        issues.append({"check": "signout_clears_hive", "reason": "signOut handler not found in index.html."})
    else:
        missing_clear = [k for k in HIVE_KEYS if ("'" + k + "'") not in signout and ('"' + k + '"') not in signout]
        if missing_clear or "removeItem" not in signout:
            issues.append({"check": "signout_clears_hive", "reason":
                "signOut must removeItem every hive key so the next user on a shared device cannot "
                "inherit this user's tenant; missing: " + (", ".join(missing_clear) or "(removeItem call)") + "."})

    return issues


_FILE_CACHE = {}
def _src(path):
    if path not in _FILE_CACHE:
        # Read the RAW file (not read_file's bundle-augmented view) so per-file
        # signatures match the file they were written against.
        try:
            with open(path, encoding="utf-8") as f:
                _FILE_CACHE[path] = f.read()
        except OSError:
            _FILE_CACHE[path] = ""
    return _FILE_CACHE[path]


def check_l2_a1_deeplinks():
    """A1 generic-landing hand-off LOCK (presence guard). Every entity-naming emit
    site must keep its deep-link form, AND every destination must keep its reader
    that pre-focuses the named record (a deep-link param is useless if the
    destination ignores it). Each `assert_deeplinked` / `assert_present` regex is
    anchored to its specific site (unique nearby variable), so there are no false
    positives even when several sites share a destination. Any missing one = a
    regression = FAIL."""
    issues = []
    if not os.path.exists(BASELINE):
        issues.append({"check": "a1_deeplinks_present", "reason":
            f"{BASELINE} not found - the A1 deep-link capability map / baseline must be frozen."})
        issues.append({"check": "a1_readers_present", "skip": True,
                       "reason": "baseline missing - reader check skipped."})
        return issues

    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)

    # --- every entity-naming emit site must stay deep-linked ---
    missing_links = []
    for site in base.get("deeplink_emit_sites", []):
        rx = site.get("assert_deeplinked")
        if rx and not re.search(rx, _src(site["file"])):
            missing_links.append(f"{site['id']} ({site['file']})")
    if missing_links:
        issues.append({"check": "a1_deeplinks_present", "reason":
            "A1 REGRESSION - these entity-naming sites lost their deep-link to the named "
            "record (re-add the ?param, mirror renderRiskStrip): " + "; ".join(missing_links) + "."})

    # --- every destination must keep its pre-focus reader ---
    missing_readers = []
    for rd in base.get("deeplink_readers", []):
        rx = rd.get("assert_present")
        if rx and not re.search(rx, _src(rd["file"])):
            missing_readers.append(f"{rd['id']} ({rd['file']} {rd.get('param','')})")
    if missing_readers:
        issues.append({"check": "a1_readers_present", "reason":
            "A1 REGRESSION - these deep-link destinations lost the reader that pre-focuses "
            "the named record (an emitted ?param is useless without it): " + "; ".join(missing_readers) + "."})

    # --- A2: the carry-intent action-focus must stay wired ---
    missing_a2 = []
    for site in base.get("a2_action_focus", []):
        rx = site.get("assert_present")
        if rx and not re.search(rx, _src(site["file"])):
            missing_a2.append(f"{site['id']} ({site['file']})")
    if missing_a2:
        issues.append({"check": "a2_action_focus_present", "reason":
            "A2 REGRESSION - these lost the carry-intent action-focus (a deep-linked detail "
            "must land with the matching action scrolled-to + focused): " + "; ".join(missing_a2) + "."})

    # --- A3: list filter state must persist to the URL (survive reload/back-nav) ---
    missing_a3 = []
    for site in base.get("a3_state_persistence", []):
        rx = site.get("assert_present")
        if rx and not re.search(rx, _src(site["file"])):
            missing_a3.append(f"{site['id']} ({site['file']})")
    if missing_a3:
        issues.append({"check": "a3_state_persistence_present", "reason":
            "A3 REGRESSION - these lost list-state persistence (the live filter must mirror to "
            "the URL so it survives reload + back-nav): " + "; ".join(missing_a3) + "."})

    # --- C2: the front-door auth/join inputs must keep a persistent label ---
    c2 = base.get("c2_seed_labels", {})
    if c2.get("input_ids"):
        c2src = _src(c2.get("file", "index.html"))
        unlabeled = []
        for iid in c2["input_ids"]:
            m = re.search(r'<input\b[^>]*\bid="' + re.escape(iid) + r'"[^>]*>', c2src)
            tag = m.group(0) if m else ""
            if not tag or not re.search(r'\baria-label(ledby)?\s*=', tag):
                unlabeled.append(iid)
        if unlabeled:
            issues.append({"check": "c2_seed_labels_present", "reason":
                "C2 REGRESSION - these front-door inputs reverted to placeholder-as-label "
                "(add a persistent <label>/aria-label so the field name survives typing): "
                + ", ".join(unlabeled) + "."})

    # --- C2: the dynamic/utility inputs keep their persistent aria-label ---
    _presence_guard(base, "c2_family", "fixed_sites", "c2_family_labels_present", issues,
        "C2 REGRESSION - these inputs reverted to placeholder-only (re-add the aria-label): ")

    # --- C1: recall-dependent entity inputs keep their picker ---
    _presence_guard(base, "c1_recall", "fixed_sites", "c1_pickers_present", issues,
        "C1 REGRESSION - these recall-dependent entity inputs lost their picker/datalist "
        "(re-add list=/<datalist> so the user recognises instead of recalls): ")

    # --- C3: every canonical record-card surface keeps a status/last-action/timestamp element ---
    _presence_guard(base, "c3_status_on_record", "surfaces", "c3_status_on_record_present", issues,
        "C3 REGRESSION - these record-card surfaces dropped their status/last-action/timestamp "
        "element (the user now has to remember where the record stands): ")

    # --- B2: contentless link/button labels keep an aria-label naming the object ---
    _presence_guard(base, "b2_fixed", "fixed_sites", "b2_scent_labels_present", issues,
        "B2 REGRESSION - these labels lost the aria-label that names their target "
        "(a bare 'View'/'Open' has no information scent): ")

    # --- B3: first-run empty states that named an action keep their next-step CTA ---
    _presence_guard(base, "b3_fixed", "fixed_sites", "b3_dead_end_cta_present", issues,
        "B3 REGRESSION - these empty states lost the clickable next-step CTA "
        "(the copy names an action but strands the user with no way to start it): ")

    # --- E3: destructive controls keep their confirm before destroying saved data ---
    _presence_guard(base, "e3_fixed", "fixed_sites", "e3_confirm_present", issues,
        "E3 REGRESSION - these destructive controls lost their confirm() guard "
        "(a badge-revoke / contact-delete must not destroy saved data silently): ")

    # --- E2: inline validation errors stay announced to assistive tech ---
    _presence_guard(base, "e2_fixed", "fixed_sites", "e2_error_announced_present", issues,
        "E2 REGRESSION - these validation-error regions lost role=alert/aria-live "
        "(a screen-reader user no longer hears what went wrong): ")
    return issues


def _presence_guard(base, top_key, list_key, check_name, issues, prefix):
    """Generic presence-guard: each registry entry's `assert_present` regex must
    still match its file. Mirrors the A1/A2/A3 site-anchored lock."""
    node = base.get(top_key, {})
    entries = node.get(list_key, []) if isinstance(node, dict) else node
    missing = []
    for site in entries:
        rx = site.get("assert_present")
        f = site.get("file")
        if rx and f and not re.search(rx, _src(f)):
            missing.append(f'{site.get("id", "?")} ({f})')
    if missing:
        issues.append({"check": check_name, "reason": prefix + "; ".join(missing) + "."})


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nArc X - Cognitive Load II : HARD Gate (L1 hive resolution + L2 A1 deep-links)"))
    print("=" * 76)

    content = read_file(INDEX)
    if not content:
        print(f"  ERROR: {INDEX} not found")
        sys.exit(1)

    all_issues = check_l1_login_resolution(content)
    all_issues += check_l2_a1_deeplinks()

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)

    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed - front-door login resolves the hive "
              f"(Issue #1 locked) + A1 deep-link debt held at baseline.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "arc_x_cognitive",
        "phase":        "X0",
        "layer":        "L1 real-login hive resolution (Issue #1) + L2 A1 deep-link ratchet",
        "page":         INDEX,
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("arc_x_cognitive_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
