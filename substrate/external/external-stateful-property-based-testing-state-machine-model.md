---
name: external-stateful-property-based-testing-state-machine-model
type: reference
source: https://propertesting.com/book_state_machine_properties.html
source_sha: f8f39e66a5b17867
fetched_at: 2026-07-30T03:20:00Z
last_verified: 2026-07-30
ttl_days: 180
distilled_by: inline-research-v1
supersedes: null
topic: stateful property-based testing - a model plus generated COMMAND SEQUENCES; preconditions gate legality, postconditions check the real system, next_state advances the model, and shrinking minimises the counterexample
---

## reference - stateful property-based testing (state-machine model)
* The MODEL is a deliberately simplified abstraction of expected behaviour: a state structure, an initial
  state, and functions that transform it per operation. It runs in TWO phases - abstract/symbolic then
  concrete - while the real system executes only in the concrete phase.
* Four callbacks, each with one job:
  - **command generation** - produce symbolic calls with argument generators;
  - **precondition** - *"define whether a given symbolic call would make sense to apply according to the
    current model state"*;
  - **postcondition** - verify the REAL result matches what the model expected;
  - **next_state** - *"Assuming the postcondition for a call was true, update the model accordingly for
    the test to proceed."*
* ILLEGAL sequences are handled by the precondition during abstract execution: generation restarts at the
  current state level, so invalid transitions are rejected BEFORE reaching the real system. That prevents
  false negatives - the harness never accuses the product of refusing something it should refuse.
* Why generated beats hand-written: hand-written tests cover LINEAR paths; generation explores state
  combinations across several dimensions at once and finds emergent bugs from interactions a human would
  not construct (the canonical shape: "corrupts after exactly 5 pushes then 3 pops").
* SHRINKING removes commands from a failing sequence, keeping only removals that preserve the failure,
  until a minimal counterexample remains - so a 40-command failure reduces to the 3 that matter.
* Concurrency: with a model in hand, race conditions are tested by LINEARISABILITY - it is enough to find
  one sequential interleaving through the concurrent history that respects the sequential model.

### WHY THIS MATTERS FOR THE MARKETPLACE TEST BANK
Our sneak-paths are FOUR hand-named kinds (replay, concurrency, out-of-order, session-switch), one cell
per transition. That is a human's list of ways to misuse a state machine. A generated sequence over the
same guard would explore orderings we never enumerated - and we already have every ingredient: the
authorised transition set IS the model (`legal_origins()` derives it from the bank), the guard IS the
system under test, and the rolled-back psql probe IS the concrete execution. The precondition insight is
the one that matters most for us: it is exactly the bug my out-of-order probe had, where planting "two
states earlier" demanded a refusal the guard rightly does not give.
