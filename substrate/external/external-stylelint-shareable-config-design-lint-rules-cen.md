---
name: external-stylelint-shareable-config-design-lint-rules-cen
type: reference
source: https://stylelint.io/user-guide/configure
source_sha: 5c99a4d79b461c6c
fetched_at: 2026-07-21T07:20:25Z
last_verified: 2026-07-21
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: stylelint shareable config design lint rules centralization extends
---

## reference · stylelint configuration
* Stylelint expects a configuration object that can be defined in various files, including `stylelint.config.js`, `stylelint.config.mjs`, `stylelint.config.cjs`, `.stylelintrc.js`, `.stylelintrc.mjs`, `.stylelintrc.cjs`, `.stylelintrc`, `.stylelintrc.yml`, `.stylelintrc.yaml`, `.stylelintrc.json`, or in the `stylelint` property of `package.json`.
* The configuration object has a `rules` property that determines what the linter looks for and complains about.
* Rule configurations can be `null` (to turn the rule off), a single value (the primary option), or an array with two values (`[primary option, secondary options]`).
* Some rules accept regular expressions (regex) in the `"/regex/"` format.
* The `disableFix` secondary option can be used to disable autofix on a per-rule basis.
* The `message` secondary option can be used to deliver a custom message when a rule is violated.
* The `url` secondary option can be used to provide a custom link to external docs.
* The `reportDisables` secondary option can be used to report any `stylelint-disable` comments for a rule.
* The `severity` secondary option can be used to adjust the severity of a rule, with available values being `"warning"` and `"error"`.
* The `languageOptions` property can be used to customize the syntax and specify the directionality.
* The `syntax` property can be used to extend or modify the default CSS syntax, including `atRules`, `cssWideKeywords`, `properties`, `types`, and `units`.
* At-rules can be customized by defining their expected prelude and descriptors.
* Custom global keywords can be added to the list of CSS-wide keywords.
* The syntax for specific properties can be extended or modified.
* The syntax for specific types can be extended or modified.
* Unit categories can be extended with custom units.
Sources: https://stylelint.io/user-guide/configure
