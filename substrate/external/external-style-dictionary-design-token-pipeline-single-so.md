---
name: external-style-dictionary-design-token-pipeline-single-so
type: reference
source: https://styledictionary.com/getting-started/using_the_cli/
source_sha: c535a715b8f8915e
fetched_at: 2026-07-16T11:45:00Z
last_verified: 2026-07-16
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: style-dictionary design token pipeline single source of truth
---

## reference · style-dictionary design token pipeline single source of truth

* Install Style Dictionary as a dev dependency using `npm install --save-dev style-dictionary`.
* Use the CLI by running `style-dictionary [command] [options]`.
* The CLI provides four basic commands:
  * `build`: Builds a Style Dictionary package from the current directory.
  * `clean`: Removes files specified in the config of the Style Dictionary package of the current directory.
  * `init`: Generates a starter Style Dictionary.
  * `version`: Get the version of Style Dictionary.
* `build` command options:
  * `-c`, `--config`: Set the path to the configuration file. Defaults to `./config.json`.
  * `-p`, `--platform`: Only build a specific platform. If not supplied, builds all platforms found in the configuration file.
  * `-s`, `--silent`: Silence all logging, except for fatal errors.
  * `-v`, `--verbose`: Enable verbose logging for reference errors, token collisions, and filtered tokens with outputReferences.
  * `-n`, `--no-warn`: Disable warnings from being logged.
* `clean` command options:
  * `-c`, `--config`: Set the path to the configuration file. Defaults to `./config.json`.
  * `-p`, `--platform`: Only clean a specific platform. If not supplied, cleans all platforms found in the configuration file.
  * `-s`, `--silent`: Silence all logging, except for fatal errors.
  * `-v`, `--verbose`: Enable verbose logging for reference errors, token collisions, and filtered tokens with outputReferences.
  * `-n`, `--no-warn`: Disable warnings from being logged.
* `init` command usage: `style-dictionary init <example-type>`, where `<example-type>` is one of `basic` or `complete`.

Sources: https://styledictionary.com/getting-started/using_the_cli/
