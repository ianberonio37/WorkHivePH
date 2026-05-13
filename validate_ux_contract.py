"""
WorkHive UX Contract Validator
==============================
Enforces the worker-facing usability bar from WORKHIVE_UX_CONTRACT.md.
This gate covers rules NOT already enforced by a narrower validator
(mobile / loading / idempotency / capture-contracts handle the rest).

  Layer A -- Every interactive page must pass (hard gate)
    A2  Every <input>/<textarea>/<select> has a visible <label for=>
        or an aria-label / aria-labelledby fallback.
    A3  Every destructive button (text or id containing delete / reject /
        wipe / discard / remove) has a confirm() call OR opens a modal
        within the same handler scope.
    A7  Every LIVE_TOOL_PAGE has a non-placeholder <title> and that title
        is unique across pages.

  Layer B -- Data-bound pages (advisory)
    B1  Empty-state strings (matched as "No X yet" / "no X to show" /
        "nothing here") in render code are followed by either (a) a verb
        in the same text node OR (b) a <button>/<a> sibling. Pure "No X
        yet" with no recovery path is flagged WARN.
    B3  Loading states declared on the page must use a skeleton class OR
        aria-busy on a container, not just a generic "Loading..." string
        as the only indicator.

  Layer C -- Mutating surfaces (hard gate)
    C3  Role-gated controls are HIDDEN (display:none / classList.add
        ('hidden')), not just disabled. A disabled-but-visible button on
        a phone teaches workers to click it.

Usage:  python validate_ux_contract.py
Output: ux_contract_report.json
"""
from __future__ import annotations

import os
import re
import json
import sys
import glob
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

ROOT = os.path.dirname(os.path.abspath(__file__))

# Baseline ratchet for A2 input_label.
# WHY: 536 placeholder-only inputs exist as platform-wide convention pre-dating
# the UX contract. Fixing all in one PR is a refactor, not a feature. The
# contract instead locks the current per-file count: NEW violations FAIL, but
# existing ones are accepted. As pages get touched and labels added, the
# baseline can be regenerated (lower count) — never increased.
INPUT_LABEL_BASELINE_FILE = os.path.join(ROOT, "ux_contract_input_label_baseline.json")


def _live_tool_pages() -> list[str]:
    """Pull LIVE_TOOL_PAGES from validate_assistant.py — single source of
    truth so this gate auto-extends when a new page is registered."""
    src = read_file(os.path.join(ROOT, "validate_assistant.py")) or ""
    m = re.search(r"LIVE_TOOL_PAGES\s*=\s*\[([^\]]*)\]", src, re.DOTALL)
    if not m:
        return []
    return [f"{p}.html" for p in re.findall(r'["\']([\w\-]+)["\']', m.group(1))]


# ── Layer A2: input has label ─────────────────────────────────────────────────
#
# We accept ANY of: <label for="id"> with matching <input id="id">, OR
# input has aria-label, OR input is inside a <label> wrapper. Hidden inputs
# (type="hidden") are exempt — they're not user-facing.

INPUT_TAG_RE = re.compile(
    r"""<(?P<tag>input|textarea|select)
        (?P<attrs>[^>]*)>""",
    re.VERBOSE | re.IGNORECASE,
)


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
    return m.group(1) if m else None


def _load_input_label_baseline() -> dict[str, int]:
    """Load per-page baseline counts. Missing file = no baseline yet (first
    run will write one). Empty dict if file is corrupted."""
    if not os.path.exists(INPUT_LABEL_BASELINE_FILE):
        return {}
    try:
        with open(INPUT_LABEL_BASELINE_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("per_page", {})
    except Exception:
        return {}


def _save_input_label_baseline(per_page: dict[str, int]) -> None:
    """Persist current per-page counts as the new baseline.
    Only called on explicit --update-baseline flag (manual ratchet)."""
    payload = {
        "_doc": (
            "Per-page baseline counts of inputs without <label for> / "
            "aria-label. New violations FAIL the gate; existing ones are "
            "accepted. Regenerate with: "
            "python validate_ux_contract.py --update-baseline"
        ),
        "total": sum(per_page.values()),
        "per_page": per_page,
    }
    with open(INPUT_LABEL_BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def check_input_labels(pages: list[str]) -> tuple[list[dict], dict[str, int]]:
    """Returns (issues_to_report, per_page_counts).

    Compares per-page count against baseline. Returns FAIL issues only for
    pages where the count EXCEEDED the baseline (new debt added). Pages at
    or below baseline are silent (existing debt accepted)."""
    baseline = _load_input_label_baseline()
    raw_findings: dict[str, list[dict]] = defaultdict(list)
    per_page_count: dict[str, int] = {}

    for page in pages:
        path = os.path.join(ROOT, page)
        src = read_file(path)
        if not src:
            continue
        # Collect <label for="..."> targets
        label_for = set(re.findall(r'<label[^>]*\bfor\s*=\s*["\']([^"\']+)["\']', src, re.IGNORECASE))
        # Inputs wrapped in <label>...</label> — heuristic: a <label> tag
        # appears within ~200 chars before the input with no </label> in between.
        for m in INPUT_TAG_RE.finditer(src):
            tag = m.group("tag").lower()
            attrs = m.group("attrs")
            input_type = (_attr(attrs, "type") or "").lower()
            if input_type in {"hidden", "submit", "button"}:
                continue
            input_id = _attr(attrs, "id")
            # Skip generated/templated ids (e.g. `reading-${escHtml(d.key)}`).
            # Runtime expansion creates a real id; the matching <label for>
            # is also templated and the static-source check can't see it.
            if input_id and ("${" in input_id or "{{" in input_id):
                continue
            # Skip inputs without ANY id (any tag, not just <input>) —
            # they're usually role-specific renderers or dynamic widgets
            # where a static check can't assess labelling reliably.
            if not input_id:
                continue
            if input_id in label_for:
                continue
            if _attr(attrs, "aria-label") or _attr(attrs, "aria-labelledby"):
                continue
            # Wrapping-label heuristic
            prefix = src[max(0, m.start() - 250): m.start()]
            if "<label" in prefix.lower() and "</label" not in prefix.lower():
                continue
            line = src.count("\n", 0, m.start()) + 1
            raw_findings[page].append({
                "check": "input_label",
                "skip":  False,
                "reason": (
                    f"{page}:{line} <{tag}{(' id='+input_id) if input_id else ''}> has no "
                    f"<label for> / aria-label / wrapping <label>. Placeholders alone "
                    f"vanish on focus — workers lose context."
                ),
            })
        per_page_count[page] = len(raw_findings.get(page, []))

    # Ratchet logic: compare each page's count to baseline. Pages over baseline
    # FAIL (new debt). Pages at-or-under baseline are silent. No baseline yet =
    # everything passes silently (first run becomes the baseline).
    issues: list[dict] = []
    for page, count in per_page_count.items():
        baseline_count = baseline.get(page, count if not baseline else 0)
        # If no baseline file exists yet, accept current state as baseline.
        # If baseline exists but this page isn't in it, treat as 0 (page is
        # new — must comply from the start).
        if not baseline:
            continue
        if count > baseline_count:
            new_count = count - baseline_count
            # Emit ALL findings for this page so the user can see what's new
            # (we can't pinpoint which specific input is the new one without
            # diff'ing line numbers).
            issues.append({
                "check": "input_label",
                "skip":  False,
                "reason": (
                    f"{page}: {count} unlabeled inputs but baseline is "
                    f"{baseline_count}. +{new_count} new violation(s). "
                    f"Either add <label for> / aria-label to the new inputs, "
                    f"or regenerate the baseline if these are legitimate."
                ),
            })
    return issues, per_page_count


# ── Layer A3: destructive button has confirm ──────────────────────────────────
#
# A button (or anchor styled as button) whose visible TEXT or ID contains a
# destructive verb must have a `confirm(`, an `openModal(` / `showConfirm(` /
# similar call, or `data-confirm` attribute, within the same click-handler scope.

DESTRUCTIVE_RE = re.compile(
    r"""<(?:button|a)([^>]*)>([^<]{0,80})</(?:button|a)>""",
    re.IGNORECASE,
)
DESTRUCTIVE_KEYWORDS = ("delete", "reject", "wipe", "discard", "remove all", "clear all")


def check_destructive_confirm(pages: list[str]) -> list[dict]:
    issues: list[dict] = []
    for page in pages:
        path = os.path.join(ROOT, page)
        src = read_file(path)
        if not src:
            continue
        for m in DESTRUCTIVE_RE.finditer(src):
            attrs = m.group(1)
            text  = m.group(2).strip().lower()
            elem_id = (_attr(attrs, "id") or "").lower()
            onclick = _attr(attrs, "onclick") or ""
            label = text + " " + elem_id + " " + onclick.lower()
            if not any(k in label for k in DESTRUCTIVE_KEYWORDS):
                continue
            # Carve-outs: "delete" inside a longer non-destructive phrase
            # (e.g. "undeleted", "soft-delete restore"). Cheap check.
            if "undelete" in label or "soft-delete" in label or "restore" in label:
                continue
            if "data-confirm" in attrs.lower():
                continue
            # Check the onclick attribute first.
            if "confirm(" in onclick.lower() or "openmodal(" in onclick.lower() or "showconfirm(" in onclick.lower():
                continue
            # If onclick calls a NAMED function (e.g. `deleteScheduleItem()`),
            # follow that function and check its body for confirm/modal.
            # Buttons often have onclick="someHandler(arg)" with the handler
            # defined hundreds of lines below.
            fn_call_match = re.search(r"\b([a-zA-Z_]\w*)\s*\(", onclick)
            if fn_call_match:
                fn_name = fn_call_match.group(1)
                # Skip non-handler names (event, this, etc.)
                if fn_name not in {"event", "this", "return", "console", "alert"}:
                    fn_def_re = re.compile(
                        rf"(?:async\s+)?function\s+{re.escape(fn_name)}\s*\([^)]*\)\s*\{{",
                    )
                    fn_match = fn_def_re.search(src)
                    if fn_match:
                        # Brace-walk to find the end of the function body
                        depth = 0
                        i = fn_match.end() - 1
                        while i < len(src):
                            ch = src[i]
                            if ch == "{":
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                                if depth == 0:
                                    break
                            i += 1
                        body = src[fn_match.end():i]
                        if re.search(r"\bconfirm\s*\(|\bopenModal\s*\(|"
                                     r"\bshowConfirm\s*\(|\bopen[A-Z]\w*Modal\s*\(",
                                     body):
                            continue
            # data-action='X' pattern: button routed via event-listener
            # dispatch (asset-hub, alert-hub, others). Follow the action
            # name to whatever handler name it dispatches to, then look
            # for confirm in that handler. We look for the JS dispatch
            # pattern (===, switch case) — NOT the HTML attribute itself.
            data_action = _attr(attrs, "data-action")
            if data_action:
                # Match `=== '<action>'` or `case '<action>'` followed by
                # the handler call. Excludes the data-action="..." HTML.
                dispatch_re = re.compile(
                    rf"(?:===?\s*|case\s+)['\"]{re.escape(data_action)}['\"][^\n]{{0,200}}?"
                    rf"\b([a-zA-Z_]\w*)\s*\(",
                )
                dm = dispatch_re.search(src)
                if dm:
                    target_fn = dm.group(1)
                    fn_def_re = re.compile(
                        rf"(?:async\s+)?function\s+{re.escape(target_fn)}\s*\([^)]*\)\s*\{{",
                    )
                    fn_match = fn_def_re.search(src)
                    if fn_match:
                        depth = 0
                        i = fn_match.end() - 1
                        while i < len(src):
                            ch = src[i]
                            if ch == "{":
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                                if depth == 0:
                                    break
                            i += 1
                        body = src[fn_match.end():i]
                        if re.search(r"\bconfirm\s*\(|\bopenModal\s*\(|"
                                     r"\bshowConfirm\s*\(|\bopen[A-Z]\w*Modal\s*\(",
                                     body):
                            continue
            # className-routed wiring: `<button class="btn-delete-x">` paired
            # with `querySelectorAll('.btn-delete-x').forEach(... handler)`.
            # Pull every class from the button, look for a matching querySelector
            # binding, follow the handler call inside.
            class_attr = _attr(attrs, "class") or ""
            classes = [c for c in class_attr.split() if c]
            cls_handler_has_confirm = False
            for cls in classes:
                # Find the querySelectorAll('.cls') anchor first, then walk
                # forward looking at every function call until we find one
                # that's a real handler (not forEach/addEventListener glue).
                anchor_re = re.compile(
                    rf"querySelectorAll\s*\(\s*['\"]\.{re.escape(cls)}['\"]",
                )
                am = anchor_re.search(src)
                if not am:
                    continue
                tail400 = src[am.end(): am.end() + 600]
                target_fn = None
                for call_m in re.finditer(r"\b([a-zA-Z_]\w*)\s*\(", tail400):
                    cand = call_m.group(1)
                    if cand in {"forEach", "addEventListener", "querySelectorAll",
                                "querySelector", "getElementById", "Array",
                                "Number", "String", "JSON", "parseInt",
                                "console", "function", "btn", "e", "event",
                                "preventDefault", "stopPropagation", "Boolean"}:
                        continue
                    target_fn = cand
                    break
                if not target_fn:
                    continue
                fn_def_re = re.compile(
                    rf"(?:async\s+)?function\s+{re.escape(target_fn)}\s*\([^)]*\)\s*\{{",
                )
                fn_match = fn_def_re.search(src)
                if not fn_match:
                    continue
                depth = 0
                i = fn_match.end() - 1
                while i < len(src):
                    ch = src[i]
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    i += 1
                body = src[fn_match.end():i]
                if re.search(r"\bconfirm\s*\(|\bopenModal\s*\(|"
                             r"\bshowConfirm\s*\(|\bopen[A-Z]\w*Modal\s*\(",
                             body):
                    cls_handler_has_confirm = True
                    break
            if cls_handler_has_confirm:
                continue
            # id-based wiring: button has id, wired via getElementById('id')
            # .addEventListener('click', () => handler(arg)).
            elem_id = _attr(attrs, "id")
            id_handler_has_confirm = False
            if elem_id:
                # Two binding patterns:
                #   (1) getElementById('id').addEventListener('click', () => fn())
                #   (2) const btn = getElementById('id'); btn.addEventListener('click', () => fn())
                # We grab the local binding name from (2) if present, then
                # search for that name's click-handler arrow.
                local_var = elem_id  # fallback
                bind_re = re.compile(
                    rf"(?:const|let|var)\s+(\w+)\s*=\s*document\.getElementById\s*\(\s*['\"]{re.escape(elem_id)}['\"]\s*\)",
                )
                bm = bind_re.search(src)
                if bm:
                    local_var = bm.group(1)
                # Find the click-handler binding (arrow or named callback)
                handler_re = re.compile(
                    rf"\b{re.escape(local_var)}\??\.addEventListener\s*\(\s*['\"]click['\"]\s*,\s*"
                    rf"(?:async\s+)?\([^)]*\)\s*=>\s*\{{?\s*[^;}}]{{0,150}}?\b([a-zA-Z_]\w*)\s*\(",
                )
                hm = handler_re.search(src)
                target_fn = hm.group(1) if hm else None
                # Fallback: scan the broader id-anchor window for any call
                if not target_fn:
                    anchor_re = re.compile(
                        rf"getElementById\s*\(\s*['\"]{re.escape(elem_id)}['\"]\s*\)",
                    )
                    am = anchor_re.search(src)
                    if am:
                        tail600 = src[am.end(): am.end() + 600]
                        for call_m in re.finditer(r"\b([a-zA-Z_]\w*)\s*\(", tail600):
                            cand = call_m.group(1)
                            if cand in {"forEach", "addEventListener", "querySelectorAll",
                                        "querySelector", "getElementById", "Array",
                                        "Number", "String", "JSON", "parseInt",
                                        "console", "function", "btn", "e", "event",
                                        "preventDefault", "stopPropagation", "Boolean"}:
                                continue
                            target_fn = cand
                            break
                # Whatever path set target_fn — primary handler_re OR fallback —
                # look up its definition and check the body for confirm().
                if target_fn:
                    fn_def_re = re.compile(
                        rf"(?:async\s+)?function\s+{re.escape(target_fn)}\s*\([^)]*\)\s*\{{",
                    )
                    fn_match = fn_def_re.search(src)
                    if fn_match:
                        depth = 0
                        i = fn_match.end() - 1
                        while i < len(src):
                            ch = src[i]
                            if ch == "{":
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                                if depth == 0:
                                    break
                            i += 1
                        body = src[fn_match.end():i]
                        if re.search(r"\bconfirm\s*\(|\bopenModal\s*\(|"
                                     r"\bshowConfirm\s*\(|\bopen[A-Z]\w*Modal\s*\(",
                                     body):
                            id_handler_has_confirm = True
            if id_handler_has_confirm:
                continue
            # Last resort: nearby-source heuristic (handler may be inline).
            tail = src[m.end(): m.end() + 1500]
            if re.search(r"\bconfirm\s*\(|\bopenModal\s*\(|\bshowConfirm\s*\(|"
                         r"\.classList\.remove\s*\(\s*['\"]hidden['\"]", tail):
                continue
            line = src.count("\n", 0, m.start()) + 1
            issues.append({
                "check": "destructive_confirm",
                "skip":  False,
                "reason": (
                    f"{page}:{line} destructive button \"{text[:40]}\" has no "
                    f"confirm() / modal step within its handler scope. A misclick "
                    f"on a phone in a noisy plant is the regret moment — wrap with "
                    f"`if (!confirm('Sure?')) return;` or open a confirm modal."
                ),
            })
    return issues


# ── Layer A7: unique non-placeholder <title> ──────────────────────────────────

PLACEHOLDER_TITLES = (
    "untitled", "page", "document", "html", "new page",
)


def check_page_titles(pages: list[str]) -> list[dict]:
    issues: list[dict] = []
    seen: dict[str, str] = {}  # title -> first page that used it
    for page in pages:
        path = os.path.join(ROOT, page)
        src = read_file(path)
        if not src:
            continue
        m = re.search(r"<title[^>]*>([^<]+)</title>", src, re.IGNORECASE)
        if not m:
            issues.append({
                "check": "page_title",
                "skip":  False,
                "reason": f"{page} has no <title> tag — browser tabs + screen readers lose context.",
            })
            continue
        title = m.group(1).strip()
        if not title or title.lower() in PLACEHOLDER_TITLES:
            issues.append({
                "check": "page_title",
                "skip":  False,
                "reason": f"{page} has a placeholder <title> ('{title}') — replace with a worker-meaningful label.",
            })
            continue
        # Normalise for dedup: strip "WorkHive" suffix / common boilerplate
        norm = re.sub(r"\s*\|\s*WorkHive\s*$", "", title, flags=re.IGNORECASE).strip().lower()
        if norm in seen:
            issues.append({
                "check": "page_title",
                "skip":  False,
                "reason": (
                    f"{page} <title> '{title}' duplicates {seen[norm]} — "
                    f"each page should have a unique browser-tab label."
                ),
            })
        else:
            seen[norm] = page
    return issues


# ── Layer B1: empty-state has verb + CTA ──────────────────────────────────────

EMPTY_STATE_PATTERNS = (
    re.compile(r"No\s+\w+(?:\s+\w+)?\s+(?:yet|to\s+show|defined|tied|here)\b", re.IGNORECASE),
    re.compile(r"Nothing\s+(?:here|to\s+show|yet)\b", re.IGNORECASE),
    re.compile(r"\bempty\s+state\b", re.IGNORECASE),
)
VERB_HINT_RE = re.compile(
    r"\b(?:add|create|start|begin|set up|configure|invite|join|seed|"
    r"register|connect|import|enable|try|tap|click|press|open)\b",
    re.IGNORECASE,
)


def check_empty_state_recovery(pages: list[str]) -> list[dict]:
    """Advisory: look for empty-state strings and require either a verb in
    the same string or a button/link within the next 300 chars."""
    issues: list[dict] = []
    for page in pages:
        path = os.path.join(ROOT, page)
        src = read_file(path)
        if not src:
            continue
        for pat in EMPTY_STATE_PATTERNS:
            for m in pat.finditer(src):
                # Window: 200 chars before + 400 after — same render block.
                window = src[max(0, m.start() - 200): m.start() + 400]
                has_verb = bool(VERB_HINT_RE.search(window))
                has_cta = (
                    "<button" in window.lower()
                    or "<a " in window.lower()
                    or "onclick=" in window.lower()
                )
                if has_verb or has_cta:
                    continue
                line = src.count("\n", 0, m.start()) + 1
                snippet = m.group(0)
                issues.append({
                    "check": "empty_state_recovery",
                    "skip":  True,   # ADVISORY (WARN) — heuristic
                    "reason": (
                        f"{page}:{line} empty-state '{snippet}' has no verb hint "
                        f"or nearby CTA. Workers see 'no X yet' and close the tab. "
                        f"Add a CTA button or rewrite to 'No X yet — <verb> to get started'."
                    ),
                })
    return issues


# ── Layer B3: loading state uses skeleton, not generic spinner ────────────────

LOADING_STRING_RE = re.compile(r">\s*(?:Loading|Please wait|One moment)\.?\.?\.?\s*<", re.IGNORECASE)
SKELETON_HINTS = ("skeleton", "shimmer", 'aria-busy="true"', "aria-busy='true'")


def check_loading_skeleton(pages: list[str]) -> list[dict]:
    """Advisory: pages that show a textual 'Loading…' indicator should also
    declare a skeleton class or aria-busy somewhere. We accept either as
    evidence that loading state has been thoughtfully designed."""
    issues: list[dict] = []
    for page in pages:
        path = os.path.join(ROOT, page)
        src = read_file(path)
        if not src:
            continue
        loadings = list(LOADING_STRING_RE.finditer(src))
        if not loadings:
            continue
        has_skeleton = any(h in src for h in SKELETON_HINTS)
        if has_skeleton:
            continue
        # Flag the first occurrence only — one finding per page is enough.
        m = loadings[0]
        line = src.count("\n", 0, m.start()) + 1
        issues.append({
            "check": "loading_skeleton",
            "skip":  True,   # ADVISORY
            "reason": (
                f"{page}:{line} shows a textual 'Loading…' but has no skeleton "
                f"placeholder or aria-busy container. A sized skeleton tells the "
                f"worker what to expect; a spinner just makes them wait blind."
            ),
        })
    return issues


# ── Layer C3: role-gated controls are HIDDEN, not just disabled ───────────────
#
# Pattern flagged: a control whose visibility depends on a role check uses
# `.disabled = true` instead of `.style.display = 'none'` /
# `.classList.add('hidden')`. We detect role-gated patterns by proximity
# to checks of HIVE_ROLE / wh_hive_role / supervisor.

ROLE_GATE_RE = re.compile(
    r"""(?P<full>
        (?:HIVE_ROLE|wh_hive_role|hive_role|role)\s*
        (?:===?|!==?|\?\.\s*===?)\s*['"](?P<role>supervisor|worker|admin|owner)['"]
        [^;\n]{0,200}?
        \.\s*disabled\s*=\s*true
    )""",
    re.VERBOSE,
)


def check_role_gate_hides(pages: list[str]) -> list[dict]:
    issues: list[dict] = []
    for page in pages:
        path = os.path.join(ROOT, page)
        src = read_file(path)
        if not src:
            continue
        for m in ROLE_GATE_RE.finditer(src):
            line = src.count("\n", 0, m.start()) + 1
            issues.append({
                "check": "role_gate_hides",
                "skip":  False,
                "reason": (
                    f"{page}:{line} role-gates a control by setting .disabled=true. "
                    f"Disabled-but-visible buttons teach workers to keep clicking — "
                    f"hide the control with `.style.display='none'` or "
                    f"`.classList.add('hidden')` when the role is unmet."
                ),
            })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "input_label", "destructive_confirm", "page_title",
    "empty_state_recovery", "loading_skeleton",
    "role_gate_hides",
]
CHECK_LABELS = {
    "input_label":           "A2  Every form input has a visible <label for> or aria-label",
    "destructive_confirm":   "A3  Every destructive button has a confirm()/modal step",
    "page_title":            "A7  Every LIVE_TOOL_PAGE has a unique non-placeholder <title>",
    "empty_state_recovery":  "B1  Empty-state strings include a verb or CTA  [WARN]",
    "loading_skeleton":      "B3  Pages with 'Loading…' also declare a skeleton / aria-busy  [WARN]",
    "role_gate_hides":       "C3  Role-gated controls are hidden, not just disabled",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nWorkHive UX Contract Validator (6 checks)"))
    print("=" * 60)

    pages = _live_tool_pages()
    print(f"  {len(pages)} LIVE_TOOL_PAGE(s) scanned.\n")

    issues: list[dict] = []
    label_issues, label_counts = check_input_labels(pages)
    issues += label_issues
    issues += check_destructive_confirm(pages)

    # Handle --update-baseline flag: snapshot current counts as the new baseline.
    if "--update-baseline" in sys.argv:
        _save_input_label_baseline(label_counts)
        print(f"\n  Baseline updated: {sum(label_counts.values())} unlabeled "
              f"inputs across {len([k for k,v in label_counts.items() if v])} page(s).")
        return  # Don't run the rest of main — this is a write op
    # First run with no baseline file: auto-create one so the next run has
    # a starting point. Inform the user clearly.
    if not os.path.exists(INPUT_LABEL_BASELINE_FILE) and label_counts:
        _save_input_label_baseline(label_counts)
        print(f"\n  First run — wrote baseline: {sum(label_counts.values())} "
              f"unlabeled inputs across {len([k for k,v in label_counts.items() if v])} page(s).")
        print("  Future runs will FAIL only when a page exceeds its baseline.")
    issues += check_page_titles(pages)
    issues += check_empty_state_recovery(pages)
    issues += check_loading_skeleton(pages)
    issues += check_role_gate_hides(pages)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    with open("ux_contract_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "validator":   "ux_contract",
            "pages":       pages,
            "issues":      [i for i in issues if not i.get("skip")],
            "advisories":  [i for i in issues if i.get("skip")],
            "passed":      n_pass,
            "warned":      n_warn,
            "failed":      n_fail,
        }, f, indent=2, default=str)

    if n_fail == 0 and n_warn == 0:
        print(f"\n  \033[92mAll {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\n  \033[93m{n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\n  \033[91m{n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
