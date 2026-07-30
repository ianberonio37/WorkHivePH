---
name: external-mutation-testing-does-the-suite-have-teeth
type: reference
source: https://web.eecs.umich.edu/~weimerw/2022-481F/readings/mutation-testing.pdf
source_sha: 698fef1868b5d275
fetched_at: 2026-07-30T03:20:00Z
last_verified: 2026-07-30
ttl_days: 180
distilled_by: inline-research-v1
supersedes: null
topic: mutation testing - inject faults and measure how many the suite DETECTS; mutation score is the direct measure of whether assertions have teeth, and it is uncorrelated with line coverage
---

## reference - mutation testing (measuring whether tests have teeth)
* Mutation testing seeds small faults (MUTANTS) into the code and asks whether the suite NOTICES. It
  measures whether tests detect bugs, not merely whether they execute lines.
* `mutation score = (non-equivalent mutants - surviving mutants) / non-equivalent mutants`. It is
  described as the measure of *confidence* in a suite, reflecting its fault-revelation ability.
* THE FINDING THAT MATTERS: **a suite with 100% line coverage can still score below 50%** when assertions
  are weak or missing. Coverage says the code ran; the mutation score says someone would have noticed if
  it had run WRONG.
* A surviving mutant is a specific, actionable defect report about the SUITE: here is a behaviour change
  no assertion objected to.
* Equivalent mutants (semantically identical to the original) must be excluded or they depress the score
  without indicating a real gap.

### WHY THIS MATTERS FOR THE MARKETPLACE TEST BANK
This is the discipline for the failure mode that recurred all through the 2026-07-30 session: gates that
were green while proving nothing. We hand-rolled the idea repeatedly and called it "teeth" - restoring a
vulnerable guard inside a rolled-back transaction to confirm the exploit returns; planting a defect in a
gate's self-test and requiring detection; a `--selftest` that feeds a broken worker to a matcher. Every
one of those is a hand-built, one-off mutant. Mutation testing is the same idea done SYSTEMATICALLY, with
a SCORE instead of an anecdote - and our own history says why we need the score: `service-idempotency`
carries a comment that a partial UNIQUE index *"can be narrowed to uselessness without dropping the
index, so presence alone is not proof"*, which is precisely a surviving mutant described in prose.
