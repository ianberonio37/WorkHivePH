# Orchestrate and Route: break the work down, pick the model per task

Ian, 2026-11-15: "we have to solidify and establish this as a framework and workflow the Task breakdown and model
routing." This is the standing way any multi-step request is run. It sits at FRAMEWORK.md Step 0 (Triage / Router).

## Objective
Finish the whole specification at full quality for the fewest tokens: each task goes to the cheapest model that can
do it reliably, and the main session stays responsible for coordination, review and final verification.

## Step 1: Break down (main session, before any execution)
For every request with more than one unit of work, write a table and show it to Ian before executing:

| # | Task | Depends on | Model | Why this model | Done when |
|---|---|---|---|---|---|

- Tasks are small and independently checkable; "Done when" is a command or an observable result.
- Dependencies are explicit. Data-writing walks and edits to the same file never run at the same time.
- The table is shown once at the start, then kept current in replies (state column), not re-printed in full.
- Showing the table is not a stop: execution starts in the same turn (Momentum Doctrine).

## Step 2: Route each task
Judge complexity, reasoning needed, risk and blast radius, then pick:

| Model | Use for | Examples here |
|---|---|---|
| **Haiku** (`gate-runner`, or `Agent` with `model: haiku`) | Simple, repetitive, well-defined; mechanical runs with long output | gate sets, provers, stamps, sweeps, appending set text to skills |
| **Sonnet** (`Agent` with `model: sonnet`) | Standard implementation, refactors, tests, moderate debugging, pattern-following edits across files | wiring a new wave into the registry tools by copying the GJ pattern |
| **Opus** (main session) | General coding, coordination, integration, claim audits, roadmap and runbook writing, commits | the census, the seeder, the runbook correction |
| **Fable** (`Agent` with `model: fable`) | Architecture, hard debugging, ambiguous requirements, system-wide risk | reviewing a change to the registry shape, the stop guard's bind, a cross-layer red |

Rules:
- Never send Fable work that Sonnet or Haiku can do reliably. Escalate one step only when complexity, risk or a
  failed attempt justifies it, and say why in the table.
- A short command is cheaper inline than a hand-off: delegate only when the output or the work is large.
- When GitHub Copilot has quota, product code goes to Copilot through a brief (`.tmp/copilot/NN_*.md`, sent with
  `code chat -m agent -r -a <brief> -a .github/copilot-instructions.md`). Check `agenthost.log` for `quota` right after
  each hand-off. When Copilot is out, the brief is implemented by the model the table assigns.

## Step 3: Execute
- **One helper at a time** (CLAUDE.md model routing). No fan-out; the Workflow tool stays disabled.
- A helper may run in the background while the main session works on files that helper does not read or write.
- Before loading the 75 MB registry or starting a browser run, check free memory. Run a heavy read under a watchdog
  that kills it below 250 MB rather than starve a running walk.
- After a session restart, list running `node.exe` provers first: a task marked "stopped" can still be running.
- Every helper brief names its working directory, exact commands, what to report, and "do not edit or fix" for
  mechanical runs.

## Step 4: Integrate and verify (main session only)
- Read every helper result; review every diff (`git status`, and any file the task did not name).
- Run the acceptance for each task ("Done when"). Judgment, fixes to a red gate, and commits stay in the main session.
- Update the table's state, the roadmap and memory; then move to the next task in the same turn.

## Edge cases
- Copilot quota exhausted: ask Ian once who codes (2026-11-14 answer: Claude codes from the brief until it resets).
- A helper stops "waiting on its own background work": its process may still be running; do not start a second copy.
- Low memory: pivot to tasks that need no browser or registry load; never call it a ceiling.
