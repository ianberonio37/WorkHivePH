---
name: doc-WORKHIVE_UX_CONTRACT
type: doc
source: file:WORKHIVE_UX_CONTRACT.md
source_sha: f4adf240f33452e0
last_verified: 2026-07-13
supersedes: null
---
## doc · WORKHIVE_UX_CONTRACT

**Purpose.** Every change to a worker-facing surface must pass this contract before merge. The contract is split into three layers by strictness. Layer A and Layer C are hard gates (FAIL blocks the co

**Sections:** WorkHive UX Contract · Why this exists · Layer A — Every interactive page must pass (hard gate) · Layer B — Data-bound pages (advisory → promoted as each stabilises) · Layer C — Mutating surfaces (hard gate, in addition to A + B) · What "scaffold" means here · Tradeoffs the contract accepts · Adding a new rule

(Deep source: `file:WORKHIVE_UX_CONTRACT.md` — retrieve this TOC to know WHICH section to read.)
