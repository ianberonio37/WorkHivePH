# Workflow: The Flywheel — the spine every unit of work runs on

**Objective.** Turn any single unit of work (a feature, a fix, a redesign slice, an audit finding)
into something *shipped, verified, locked, taught, and remembered* — via a fixed sequence of spokes
with a gate between each. No spoke is skipped; no spoke advances on a red gate. This is our
Hardening Loop expressed as Anthropic's **prompt-chaining** pattern (sequential steps, gate-checked
handoffs).

**Governs.** Every mode of `make_a_change.md` and every fix that falls out of `audit_to_synthesis.md`.

---

## The spokes (in order) — each has an EXIT-GATE

| # | Spoke | What happens | Exit-gate (don't advance until…) | Tool / skill |
|---|---|---|---|---|
| 1 | **Skill-first** | Read the relevant `SKILL.md`(s) for the domains the task touches | you've read them and noted the checklist items | `~/.claude/skills/<name>/SKILL.md` |
| 2 | **Do the work** | Make the change (see the mode in `make_a_change.md`) | the change is written | Edit / Write |
| 3 | **Verify** | Prove it works at runtime — verify the **DB row / behaviour, not the toast** | the real state is observed (row, edge-fn invoke, live db-client round-trip) | `functions.invoke`/curl locally; `window.db` round-trip; Playwright MCP |
| 4 | **Lock** | Crystallize the fix so it can't regress: add/extend a validator, run the gate, close the sentinel coverage gap | `run_platform_checks.py --fast` is green **and** a validator covers the fix | `tools/validate_*.py`; `run_platform_checks.py`; `/sentinel-review` |
| 5 | **Teach** | Write the lesson to **all** relevant skills (cross-skill, each from its own angle) | every skill the lesson touches is updated | Skill Self-Improvement Loop |
| 6 | **Persist + ratchet** | Write the `NEXT:` trajectory + new fact to Memento **AND update the roadmap's measured %-cell for the phase just moved** — the board must never lag reality | the handoff carries the next unit **and the roadmap %-cell is current** | `memento_handoff_write.py`; memory; the `*_ROADMAP.md` %-board |
| 7 | **Next (via the compass)** | Pick the next unit by **re-reading the CURRENT roadmap %-board** and driving its LOWEST-scoring in-scope cell; re-enter at spoke 1 | — | the `*_ROADMAP.md` %-board + Momentum Doctrine |

---

## Rules

- **A red gate is a stop *inside* the spoke, not a reason to hand back.** Fix the gate, then advance.
- **Verify the state, not the notification.** A "Saved" toast is not proof; re-query the row and its
  FK. (Precedent: the logbook `asset_node_id=null` that a green toast hid.)
- **Lock before you teach.** A lesson with no validator is a lesson that will be re-learned. The
  validator is the durable memory; the skill note is the human-readable one.
- **Persist is a ~30-second checkpoint, not a turn-end.** Write the handoff, then go to spoke 7.
- **The chain is the control flow.** You are at exactly one spoke at a time; the gate is what moves
  you forward. This is what "gate-green is part of DONE" means operationally.
- **★ The roadmap-%-board is the anti-drift COMPASS (Ian, 2026-07-17).** Two failure modes it kills:
  (a) *forgetting to update a %-cell* after moving a phase → the board silently drifts stale and stops
  reflecting reality; (b) *as a session lengthens, drifting* to lesser / tangential work instead of
  driving the board toward 100%. Fix both structurally: (1) updating the measured %-cell is PART of
  the Persist spoke — never leave it stale; (2) at ANY "what next / should I stop / is this worth it /
  which item" doubt, **POINT TO the current roadmap %-board and drive its LOWEST-scoring in-scope
  cell.** When in doubt, the roadmap decides — not the tangent in front of you. (Operational form of
  the Momentum Doctrine's "read the WHOLE roadmap through Memento before deciding.")

## Grounding

- Anthropic *Building Effective Agents* — Prompt Chaining (sequential, gated steps).
- `substrate/` — the Hardening Loop, `feedback_gate_green_is_part_of_done`,
  `feedback_deep_mcp_walk_every_page`, the Self-Improvement Loop docs.
