---
name: external-nng-confirmation-dialog-consequence-proportional
type: reference
source: https://www.nngroup.com/articles/confirmation-dialog/
source_sha: nng-confirmation-dialog
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: NN/g confirmation dialogs — confirm only high-consequence/irreversible actions, state the CONSEQUENCE specifically, proportional protection, action-specific buttons, undo > confirmation — the measurable core of rubric dim J3 (consequence transparency & action confidence)
---

## reference · NN/g confirmation dialogs — consequence + proportionality (J3)

The measurable core of UFAI **J3 · Consequence transparency & action confidence** (extends class J beyond
J1 prevent-slips / J2 undo).

* **Confirm only HIGH-consequence / irreversible actions.** Over-confirming routine reversible actions
  causes habituation ("cry wolf") — users auto-click and then ignore the ONE that mattered. So confirmation
  must be **proportional to risk**.
* **State the CONSEQUENCE specifically, not an abstract "Are you sure?"** Name the items / counts / amounts
  and the irreversible effect: "Delete 3 work orders — this can't be undone" · "This notifies 12 members."
  The user must understand WHAT will happen before acting.
* **Action-specific buttons** — "Delete file" / "Keep file", never "OK / Cancel" (which lean on the user
  remembering what they just asked).
* **Proportional protection** — low risk: a simple confirm (or none + undo); high risk: an unusual response
  (type the name, a second approver). Reserve heavy friction for the rarest, most dangerous ops.
* **Undo > confirmation** for reversible actions — a post-action receipt with a one-click undo beats a
  pre-action dialog (less anxiety, real recovery). Pairs J2.

**Testable rule (J3):** a consequential action (delete/approve/send/bulk) shows a consequence PREVIEW
(what/how-many/who), a confirm proportional to risk, and a post-action RECEIPT (what happened + undo where
reversible); optimistic UI must be HONEST (never "Saved" before commit — pairs Y1 offline). FAIL on: a bare
"Are you sure?", an OK/Cancel with no consequence, or a silent consequential action with no receipt.

Sources: https://www.nngroup.com/articles/confirmation-dialog/
