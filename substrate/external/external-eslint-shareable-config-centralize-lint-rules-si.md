---
name: external-eslint-shareable-config-centralize-lint-rules-si
type: reference
source: https://eslint.org/docs/latest/extend/shareable-configs
source_sha: e75821f31dad7ae1
fetched_at: 2026-07-21T07:20:19Z
last_verified: 2026-07-21
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: eslint shareable config centralize lint rules single source of truth consumers
---

## reference · eslint shareable config
* To share ESLint configuration, create a shareable config, which is an npm package that exports a configuration object or array.
* Name the package with a convention such as `eslint-config-` or `@scope/eslint-config` to make it easier to identify.
* Export the shareable config from the module's main entry point file, typically `index.js`.
* Export an array of config objects or a single config object, but ensure documentation clearly shows how to use the shareable config.
* Publish the shareable config to npm and use the `eslint` and `eslintconfig` keywords in the `package.json` file.
* Declare the dependency on ESLint in the `package.json` using the `peerDependencies` field with the lowest required ESLint version, e.g., `"eslint": ">= 9"`.
* Specify plugins or custom parsers as `dependencies` in the `package.json`.
* To use a shareable config, import it in an `eslint.config.js` file and add it to the exported array using `extends`.
* Override settings from the shareable config by adding them directly to the `eslint.config.js` file after importing the shareable config.
* Share multiple configs by exporting additional configs from the same npm package and referencing them in the `eslint.config.js` file.
* Always include a default export for the package to avoid confusion.
Sources: https://eslint.org/docs/latest/extend/shareable-configs
