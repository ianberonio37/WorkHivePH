---
name: skill-inventory-validator
type: skill
source: skill:inventory-validator
source_sha: a7fe725ec154c6f9
last_verified: 2026-07-13
supersedes: null
---
## skill · inventory-validator

Static analysis of `inventory.html` and `hive.html` covering the seven critical correctness

**Sections:** Inventory Validator Skill · What This Is · When to Run · What It Checks · [1] Status Transition Logic · [2] Use/Restock Guards (pending AND rejected) · [3] Transaction on Every qty_on_hand Change · [4] qty_after in addTransaction · [5] hive_id on Save Payload · [6] Use Blocked When qty > qty_on_hand · [7] Supervisor Approval/Rejection Writes (hive.html) · Baseline Result (April 2026) · Note on Hive vs Solo Mode · Balance↔ledger seesaw — qty_on_hand MUST == the newest inventory_transactions.qty_after (2026-07-08, ARC DI §10.5) · The ledger reconciles but was NOT tamper-safe — hive-scope the txn WRITE (Inventory PDDA, 2026-07-12, CONFIRMED EXPLOIT) · Reuse (compose from the canonical item) + asset↔part BOM (Inventory PDDA, 2026-07-12)

(Deep source: `skill:inventory-validator` — retrieve this TOC to know WHICH section to read.)
