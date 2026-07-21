---
name: external-eslint-rule-severity-levels-ratchet-warn-error-o
type: reference
source: https://eslint.org/docs/latest/use/configure/rules
source_sha: 5d90555634d7a9d9
fetched_at: 2026-07-21T07:20:30Z
last_verified: 2026-07-21
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: eslint rule severity levels ratchet warn error off configuration as data
---

## reference · eslint rule severity levels ratchet warn error off configuration as data

* Set rule severity to `"off"` or `0` to turn the rule off.
* Set rule severity to `"warn"` or `1` to turn the rule on as a warning (doesn't affect exit code).
* Set rule severity to `"error"` or `2` to turn the rule on as an error (exit code is 1 when triggered).
* Rules are typically set to `"error"` to enforce compliance during continuous integration testing, pre-commit checks, and pull request merging.
* Set severity to `"warn"` to report rule violations without enforcing compliance.
* Use configuration comments to configure rules inside a file: `/* eslint <rule>: "<severity>", <rule>: "<severity>" */`.
* Use numeric equivalents for rule severity: `/* eslint <rule>: 0, <rule>: 2 */`.
* Specify additional options for rules using array literal syntax: `/* eslint <rule>: ["<severity>", "<option>"], <rule>: "<severity>" */`.
* Include descriptions in configuration comments to explain why the comment is necessary.
* Use the `reportUnusedInlineConfigs` setting to report unused `eslint` inline config comments.
* Set `reportUnusedInlineConfigs` to `"error"` to report unused inline config comments.
* Use the `rules` key in a configuration file to configure rules: `rules: { <rule>: "<severity>", <rule>: "<severity>" }`.
* Specify additional options for rules using array literal syntax in a configuration file: `rules: { <rule>: ["<severity>", "<option>"], <rule>: "<severity>" }`.

Sources: https://eslint.org/docs/latest/use/configure/rules
