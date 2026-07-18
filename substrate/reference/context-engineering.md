---
name: reference-context-engineering
type: reference
source: https://sourcegraph.com/blog/context-engineering + augmentcode.com/context-engine + martinfowler.com
source_sha: review-date-anchored
last_verified: 2026-07-13
supersedes: null
---

## reference · Context engineering for coding agents (why retrieval beats fan-out)

Distilled durable rules (read this instead of re-searching; it is why the PKS substrate exists).

- **Send only the slice the task touches — not broad file replays.** Augment's Context Engine solved
  tasks at the same rate as Claude Code with materially fewer tokens by doing exactly this. Fan-out
  that re-reads the whole platform every run is the anti-pattern.
- **More context ≠ better.** Agents perform WORSE with a 100K-token codebase summary than a 5K-token
  targeted retrieval on the same task. Critical rules buried in the middle of a big context get the
  least attention ("lost in the middle").
- **Pick the retrieval strategy per sub-problem.** The agent that orchestrates multiple retrieval
  strategies (path-keyed read · semantic retrieve · grep · symbol index) beats the one that defaults
  to a single paradigm (e.g. fan-out) for everything. Default to the cheapest that answers the
  question; escalate only when it can't.
- **Prompt caching is a 90%-off lever.** A stable, reused substrate benefits; fresh-per-agent fan-out
  does not (every subagent cold-starts). Without caching a task costs ~2.5x more.
- **Granularity: codebase-specific, example-driven, small.** Broad advice ("use consistent patterns")
  doesn't constrain behavior; a concrete per-page/per-table map does.

**Operational rule for WorkHive:** before any fan-out, ask "can a `substrate/` chunk (or a direct 1KB
path-read) answer this?" Fan-out only for novel one-shot breadth or adversarial-verify panels, and fold
its findings back into the substrate. See [[project_platform_knowledge_substrate]].

Sources: Sourcegraph (Context Engineering 2026), Augment Context Engine, Martin Fowler (Context
Engineering for Coding Agents), Packmind (large codebases).
