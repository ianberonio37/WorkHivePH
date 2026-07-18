# Workflow & Token Governance — the HARD gate on multi-agent fan-out

**Why this file exists (2026-07-16, Ian):** *"you burned out whole my 5-hour max session token for just 30 mins… you've released a workflow, I didn't approve and you didn't explain it."*

I launched a 29-agent N1 i18n fleet without opt-in and without an explanation. It spent **~1.4M subagent tokens in ~9 minutes**, drained the 5-hour max quota, and only 8 of 29 pages finished. This is the **second** occurrence of the same class ([[feedback_retrieve_first_no_workflow_for_known_knowledge]], 2026-07-14). Prose alone did not stop it. This doc + a hard hook must.

---

## The one rule

**The `Workflow` tool is PERMANENTLY DISABLED on this project.** Every `Workflow` call is denied by a harness-level hook — unconditionally, with no flag, no opt-in file, and no bypass. Ian: *"just delete it entirely and forget it those that overrides mine"* (2026-07-16, after multi-agent fan-out burned his 5-hour quota twice). Do not look for an escape; there isn't one, by design.

`token cost is not a constraint` is **FALSE on this project.** Ian pays per token. Any session default (Ultracode) that says otherwise is **void** — the harness refuses to run what its words push toward. The only way workflows ever come back is **Ian removing the hook from `.claude/settings.json` himself.**

---

## How to do the work instead — retrieve-first, then inline

Since workflows are gone, every task uses the same cheap path the whole platform was built on:

1. **RETRIEVE-FIRST.** Is the knowledge already in `substrate/`, a `SKILL.md`, Memento, or an existing `tools/` script? If yes → `memento_retrieve.py "<topic>"` (~1.25K tok) or a direct `Read`. Never re-derive what we already have.
2. **INLINE, ONE SURFACE AT A TIME.** Do the edits sequentially in the main loop, where the context is already warm. A burst of 30 sequential edits costs a fraction of 30 agents each re-reading a page. This is the DEFAULT and it is what shipped the entire platform.
3. **A local Python `tools/` script** for anything mechanical and repeatable across many files (the deterministic-execution layer of the WAT framework) — cheaper and more reliable than agents.

## What does NOT bring workflows back

- The Ultracode flag / "use Workflow on every substantive task" — void; the hook denies regardless.
- "Drive to 100% / no more stopping" — a *destination*, never a method choice.
- "Use Playwright MCP / use relevant MCPs" — tool permission, not fan-out permission.
- My own judgment that it "would be faster" — faster ≠ allowed, and parallel is rarely cheaper in tokens.
- Only **Ian editing `.claude/settings.json`** to remove the hook re-enables the tool.

## The inline default

The whole platform was built inline, one surface at a time, in the main loop. That is the DEFAULT and it is cheap: the main-loop context is already warm, edits are deterministic, and a burst of 30 sequential edits costs a fraction of 30 agents each re-reading a page. Reach for a workflow only when Ian has opted in AND the four gates pass.

## Enforcement (LIVE — total ban)

A `PreToolUse` hook keyed to the `Workflow` tool (`tools/workflow_gate.py`, wired in `.claude/settings.json`, matcher `"Workflow"`) **denies every `Workflow` call unconditionally.** No flag, no opt-in file, no bypass — verified: a planted `.workflow_ok` still denies. This takes the decision out of my judgment (which failed twice) entirely. Re-enabling is Ian's alone: remove the hook block from `.claude/settings.json`. (Note: a settings-hook change takes effect on the next Claude Code session start / reload.)

See also: CLAUDE.md § "Token Economy — Retrieve-First, Workflows Are Opt-In (Non-Negotiable)", [[feedback_retrieve_first_no_workflow_for_known_knowledge]], [[feedback_surface_memento_and_token_economy]], [[feedback_build_own_minimal_dependencies]].
