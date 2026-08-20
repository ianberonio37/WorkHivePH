---
name: external-linear-style-tracker-keyboard-first-command-pale
type: reference
source: https://github.com/hcengineering/platform
source_sha: 28eac1fd621615a2
fetched_at: 2026-08-17T19:36:31Z
last_verified: 2026-08-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: linear-style tracker keyboard-first command palette huly
---

## reference · linear-style tracker keyboard-first command palette huly

- Hosted Huly service will shut down **July 20** (year unspecified); export and migrate data before that date.  
- Self‑hosted Huly deployments are **not** affected by the hosted service shutdown.  
- Contact for migration help: **artem@hardcoreeng.com**; community Slack: https://link.huly.io/slack.  
- Repository includes ready‑made apps: **Chat, Project Management, CRM, HRM, ATS**.  
- Production version tags start with **`v`** (e.g., `v0.7.310`, `v0.7.307`, `v0.6.501`); use for stable production/self‑hosted installs.  
- Development version tags start with **`s`** (e.g., `s0.7.313`, `s0.7.292`, `s0.7.288`); for testing only, may contain experimental changes.  
- **Node.js v20.11.0** is the required runtime.  
- **Docker** and **Docker Compose** are required; verify with `docker --version` and `docker compose version`.  
- If using **nvm**, run `nvm use` after cloning to match the repo’s Node version.  
- Branch workflow:  
  - `main` = production releases.  
  - `staging` = pre‑release testing (stable enough for testing, not production).  
  - `develop` = active development and default for contributions.  
  - Merge flow: `develop → staging → main`.  
- Submodule
