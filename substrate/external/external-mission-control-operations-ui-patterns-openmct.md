---
name: external-mission-control-operations-ui-patterns-openmct
type: reference
source: https://github.com/nasa/openmct
source_sha: 978703fd1f92a2fa
fetched_at: 2026-08-17T19:35:14Z
last_verified: 2026-08-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: mission control operations UI patterns openmct
---

## reference · Open MCT

- Open MCT is a NASA‑Ames mission‑control framework for visualizing telemetry on desktop and mobile browsers.  
- Source code: `https://github.com/nasa/openmct`.  
- npm package: `openmct` (latest version shown by npm badge).  
- License: Apache 2.0.  
- Documentation: `https://nasa.github.io/openmct/documentation/`.  
- Official site: `https://nasa.github.io/openmct/`.  

### Local development

1. `git clone https://github.com/nasa/openmct.git`  
2. (Optional) `nvm install` – installs the node version specified in `package.json`’s `engines`.  
3. `npm install` – installs dev dependencies.  
4. `npm start` – starts a dev server; access at `http://localhost:8080/`.  

- Build uses `npm` and `webpack`.  
- For projects that depend on Open MCT as a git repo, `ignore-scripts` is enabled; run `npm run build` manually.  

### Browser & Node support

- Supported browsers and Node versions are listed in the `browserslist` key of `package.json`.  
- Test against these environments; report issues via GitHub issues or Discussions.  

### Plugins

- A plugin is a reusable group of code, assets, and templates that can be added or removed as a unit.  
- Core Open MCT code is also organized as plugins.  
- Write plugins using the Open MCT API (`API.md`).  
- Legacy API (Angular 1.x) removed in v2.0.0; legacy support plugin: `https://github.com/nasa/openmct-legacy-plugin`.  
- Detect legacy usage by:  
  - Presence of `bundle.js`/`bundle.json`.  
  - Calls to `openmct.$injector()`, `openmct.$angular`, `openmct.legacyRegistry`, `openmct.legacyExtension`, or `openmct.legacyBundle`.  

### Testing

| Test type | Command | Notes |
|-----------|---------|-------|
| Unit | `npm test` | Jasmine/Karma; files ending in `Spec.js`. |
| e2e (Playwright) | `npm run test:e2e:ci` | Runs on every commit. |
| Visual | `npm run test:e2e:visual` | Visual regression with Percy. |
| Performance | `npm run test:perf` | Performance benchmarks. |
| Security | CodeQL workflow `codeql-analysis.yml` | Runs on each commit. |

- Test reports are published to CircleCI and code coverage to `https://app.codecov.io/gh/nasa/openmct`.  

### Hosting

- Open MCT is intended to run behind an HTTP server (Apache, Nginx, etc.).  
- Example quickstart repo: `https://github.com/scottbell/openmct-quickstart`.  

### Glossary (key terms)

- **plugin** – removable, reusable group of components.  
- **domain object** – any item that appears in the left‑hand tree.  
- **identifier** – `{ namespace, key }` tuple that uniquely identifies a domain object.  
- **composition** – array of IDs that describe child objects in a tree.  

Sources: https://github.com/nasa/openmct, https://nasa.github.io/openmct/documentation/, https://github.com/nasa/openmct-legacy-plugin, https://github.com/scottbell/openmct-quickstart
