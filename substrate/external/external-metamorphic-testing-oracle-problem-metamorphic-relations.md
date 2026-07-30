---
name: external-metamorphic-testing-oracle-problem-metamorphic-relations
type: reference
source: https://en.wikipedia.org/wiki/Metamorphic_testing
source_sha: 7eb46612babb7f75
fetched_at: 2026-07-30T03:20:00Z
last_verified: 2026-07-30
ttl_days: 180
distilled_by: inline-research-v1
supersedes: null
topic: metamorphic testing - metamorphic relations substitute for a test oracle when the expected output is unknown or expensive; verify RELATIONS across multiple executions instead of one absolute value
---

## reference - metamorphic testing (the oracle problem)
* A metamorphic relation (MR) is defined as a **necessary property of the intended functionality that
  MUST involve MULTIPLE EXECUTIONS of the software** - so correctness is checked between runs, not against
  a single known-correct answer.
* The oracle problem: there is no mechanism to verify the output for a given input, or applying one is too
  expensive. MT sidesteps it - you never need to know the right answer, only a relation the right answers
  must obey.
* Worked example (numeric): `sin(pi - x) == sin(x)`. Run x = 1.234, then the FOLLOW-UP x = pi - 1.234, and
  check the two outputs against each other. The correct value of either is never needed.
* Worked example (SEARCH / RANKING / FILTERING - the shape a marketplace has): a search returning 1,671
  results, then filtered by price or star rating, **"should return a subset of the previous results."** A
  violation is a failure, with no expected result set written down anywhere.
* MRs are explicitly **not limited to numerical inputs or equality relations**, which is what makes them
  applicable to permissions, ranking, filtering and AI output.
* MT is dual-purpose: it GENERATES the follow-up test case and VERIFIES the result.

### WHY THIS MATTERS FOR THE MARKETPLACE TEST BANK
Our oracle mix is 194 `refusal` of 247 cells and exactly **one** `eval`. Every place we could not state an
exact expected value, we either skipped it or graded it with a rubric. MRs give those surfaces a real
oracle:
* marketplace search/filter: any filter must return a SUBSET of the unfiltered result set (pure MT).
* rank stability: re-running the same query with an unchanged corpus must return the same order.
* permission monotonicity: a member's visible set must be a SUBSET of a supervisor's on the same hive.
* triage AI: paraphrasing the problem text must not change the chosen CATEGORY (the vocabulary is the
  invariant, not the wording) - an MR where an exact-match assertion tests the model's mood.
* credit ledger: verifying two top-ups in either ORDER must reach the same balance (commutativity).
