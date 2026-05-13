# WorkHive UX Contract

**Purpose.** Every change to a worker-facing surface must pass this contract before merge. The contract is split into three layers by strictness. Layer A and Layer C are hard gates (FAIL blocks the commit per the standing rule). Layer B is advisory (WARN) until each rule stabilises, then promoted.

The contract pulls together work already done in narrow validators (`validate_mobile.py`, `validate_loading_state.py`, `validate_idempotency.py`, `validate_capture_contracts.py`, etc.). The new gate `validate_ux_contract.py` enforces the rules NOT covered by an existing gate, and re-uses the existing ones for everything else.

---

## Why this exists

Workers in a Philippine plant adopt or abandon platforms within two shifts. The decision is rarely about features — it's about whether the surface gets out of the way. A page with a half-finished empty state, a destructive button with no confirm, or a form that fails silently teaches the worker "this tool is not for me." The contract is the minimum bar that keeps workers from making that conclusion.

You said it as: usability, functionality, adaptability, internal control. The 15 rules below are those four concerns made objective enough for a Python validator to enforce.

---

## Layer A — Every interactive page must pass (hard gate)

| ID | Rule | Why | Check method | Enforced by |
|---|---|---|---|---|
| A1 | Every list/feed surface declares all 4 view states: loading skeleton, empty + CTA, error + recovery, populated | Workers stuck staring at a spinner are workers about to close the tab | static: grep render function for the 4 states | `validate_ux_contract.py` (new) |
| A2 | Every form input has a visible `<label for=>` (placeholder alone is not enough) | Placeholders disappear on focus; workers lose track of which field they're in | static: every `<input>` has a matching `<label for>` or `aria-label` | `validate_ux_contract.py` (new) |
| A3 | Every destructive button (delete / reject / wipe / discard) has a `confirm()` or modal step | A misclick on a 44×44 button on a phone in a noisy plant is the regret-creation moment | static: handlers binding "delete"/"reject"/"wipe" buttons must call `confirm` or open a modal | `validate_ux_contract.py` (new) |
| A4 | Every async action ≥500ms shows a loading indicator | "Did it work?" is the worst user state | static + runtime | `validate_loading_state.py` (existing) |
| A5 | Every page renders without horizontal scroll at 375×667 viewport | Phones are the field instrument | static + runtime visual | `validate_mobile.py` (existing) |
| A6 | Every interactive element has ≥44×44px tap target on mobile | Industrial gloves, sweat, motion | static | `validate_mobile.py` (existing) |
| A7 | Every page has a unique non-placeholder `<title>` matching its nav-hub label | Browser-tab navigation, screen-reader announcement | static | `validate_ux_contract.py` (new) |

---

## Layer B — Data-bound pages (advisory → promoted as each stabilises)

| ID | Rule | Why | Check method | Enforced by |
|---|---|---|---|---|
| B1 | Empty state explains what was expected AND offers next action | "No items yet" is failure; "No items yet — add your first asset to get started [+ Add Asset]" is recovery | static: empty-state node string-length ≥30 AND contains a verb OR has a `<button>` / `<a>` sibling | `validate_ux_contract.py` (new, advisory) |
| B2 | Error toast names what failed AND suggests retry / recovery | "Error" is failure; "Could not save — connection lost. Retry?" is recovery | static: toast strings containing "error" / "failed" must also contain a verb or "retry"/"again"/"try" | `validate_ux_contract.py` (new, advisory) |
| B3 | Loading state shows a realistic skeleton, not a generic "Loading..." string | A skeleton sized to the expected layout is a comfort; a spinner is a wait | static: pages with a loading state must have either `.skeleton` CSS class OR `aria-busy="true"` on the container | `validate_ux_contract.py` (new, advisory) |
| B4 | Every saved write produces confirming feedback within 2s (toast, inline message, or state flip) | The Logbook silent-failure regression class — the user has to know it persisted | runtime: Playwright interaction-lock spec | `validate_seed_consumer_contract.py` L2 + spec files |

---

## Layer C — Mutating surfaces (hard gate, in addition to A + B)

| ID | Rule | Why | Check method | Enforced by |
|---|---|---|---|---|
| C1 | Every write logs to `audit_log` or equivalent | Manufacturing compliance needs "who did what when" for SAFER + IATF audits | static: every `.insert/.update/.delete` followed by audit write within same function | `validate_audit_log_completeness.py` (existing) |
| C2 | Every external-system POST carries `Idempotency-Key` header | Retries / network drops in plant Wi-Fi double-charge / double-create otherwise | static | `validate_idempotency.py` (existing) |
| C3 | Every role-gated control is HIDDEN (not just disabled) when role unmet | Disabled-but-visible buttons teach workers to click them; security-by-obscurity isn't, but UX-by-hiding is real | static: `if (role !== X) btn.style.display = 'none'` pattern, NOT `btn.disabled = true` | `validate_ux_contract.py` (new) |
| C4 | Every multi-step flow can be cancelled at any step without orphan rows | Stage-1 worker creates a draft, abandons it, draft sits in DB forever | static: multi-step writers must use either a single transactional write OR a "scratch row" with TTL | `validate_ux_contract.py` (new, advisory at first) |

---

## What "scaffold" means here

Two preventive levers reinforce the validator:

1. **Wizards generate compliant code by default.** The HTML Page Wizard in WorkHive Tester should emit the 4 view states, a `<label for>` for every input it generates, and an `if (role !== expected) hide()` block. So newly-scaffolded pages can't violate A1 / A2 / C3 unless someone strips the scaffolding.
2. **Reusable primitives in `utils.js`.** Functions like `renderEmptyState(container, msg, ctaLabel, onClick)`, `renderSkeleton(container, n)`, `confirmDestructive(message)` — using them satisfies the rule by construction.

The validator is the safety net for hand-coded paths that bypass both.

---

## Tradeoffs the contract accepts

- **False positives on Layer B.** "Empty state has a verb" is a heuristic. Some good empty states will fail it; some bad ones will pass. That's why Layer B is advisory until each rule's signal/noise ratio is good enough to promote.
- **No aesthetic checks.** This contract is functional, not visual. Whether a button is "the right shade of orange" stays a designer call.
- **No accessibility audit.** A11y is its own discipline; the contract enforces the basics (label-for, aria-busy, focus order via tap-target rule) but the full WCAG audit lives in `validate_accessibility.py` (not yet built).
- **No localisation.** Filipino + English mix is the WorkHive convention. Future i18n is a separate contract.

---

## Adding a new rule

1. Write the rule statement in this doc with rationale + check method.
2. Decide layer: A (mechanical, high signal → hard gate), C (mutating-surface specific → hard gate), B (heuristic → advisory).
3. Implement the check in `validate_ux_contract.py` if no existing validator covers it.
4. Run the gate against current platform; allowlist legitimate exceptions; ratchet baseline.
5. After 3 sessions with 0 FAIL, promote B rules to A (hard gate).

This is a living document. Edits land via PR like code.
