---
name: external-consumer-driven-contract-testing-integration-drift
type: reference
source: https://microsoft.github.io/code-with-engineering-playbook/automated-testing/cdc-testing/
source_sha: 22276f38625af25f
fetched_at: 2026-07-30T03:20:00Z
last_verified: 2026-07-30
ttl_days: 180
distilled_by: inline-research-v1
supersedes: null
topic: consumer-driven contract testing - the consumer's real code generates the contract, the provider proves compliance in CI, so client/API drift fails fast without slow end-to-end integration tests
---

## reference - consumer-driven contract testing (CDC)
* The consumer writes tests capturing what it actually needs; the provider runs those tests against its own
  code to prove it still satisfies them. The contract is generated from RUNNING CONSUMER CODE, which is
  what stops it drifting from what is implemented.
* It runs in CI on every change to EITHER side and fails fast when either drifts - described as the single
  most effective practice for keeping service integrations stable.
* Contracts are living, executable documentation: written docs inevitably drift, a contract is verified
  continuously. If API behaviour changes without the contract changing, tests fail.
* It replaces expensive, slow, brittle end-to-end integration tests for the narrow question "do these two
  still fit together", and lets both sides deploy independently.

### WHY THIS MATTERS FOR THE MARKETPLACE TEST BANK
`S5-edge` has FIVE cells against 57 edge functions, and the bank's layer board still reads 100% because
the rule is ">= 1 passing cell per layer" - a short-denominator 100%. The client/edge boundary is exactly
where CDC applies: `notify-push`, `supervisor-reset-password`, the service-triage gateway. We already
found the shape of the bug it prevents - `urgency='emergency'` was written by a caller against a CHECK
constraint that forbade it, a dead branch nobody noticed, which is a contract violation with no contract
to catch it. Note the platform already has adjacent gates (`edge-status-body`, `edge-fn-invoke-targets`),
so the honest addition is a CONTRACT per client-called function, not a second copy of those.
