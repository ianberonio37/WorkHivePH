---
name: reference-doc-freshness
type: reference
source: github.com/jbrockSTL/doc-drift + dosu.dev freshness score + docs-as-code
source_sha: review-date-anchored
last_verified: 2026-07-13
supersedes: null
---

## reference · Documentation freshness / drift-as-code (why the substrate can't rot)

Distilled durable rules (governs `tools/validate_substrate_freshness.py` + the anti-regression discipline).

- **The root cause of stale docs: "code goes through review/CI/merge gates; docs go through nothing."**
  Fix = treat the knowledge layer AS CODE — version it, gate it, fail CI on drift.
- **Source-anchor every derived doc.** Anchor a distilled chunk to the code it describes (a content
  hash, or AST/tree-sitter fingerprint). When the anchored source changes, the drift check FAILs in CI
  at the moment of change — not months later when someone trips over it. This is the PKS `source_sha`.
- **Freshness is a deterministic signal + a gray-zone judgment.** A 0-100 freshness score from
  last-update date + source-commit recency + broken-link checks handles the deterministic part; an LLM
  layer only for the ambiguous cases. For the PKS, the deterministic hash-match is enough for
  derived chunks; hand-authored references use a `last_verified` review-date anchor instead.
- **Fix is re-derive, not hand-patch.** When drift fires, regenerate the single stale unit
  (O(changed-files)), never hand-edit the chunk to match — that reintroduces drift.
- **Silent truncation / silent pass is the enemy.** A freshness gate must FAIL loudly on drift (like a
  code regression), never warn-and-continue. The PKS gate exits non-zero + names each stale chunk + the
  fix command.

**WorkHive mapping:** derived chunks (page/table-rls/rpc/edge-fn/skill/doc) → `source_sha` hash gate
(`substrate-freshness` in run_platform_checks); hand-authored references → `last_verified` review date.
Sources: doc-drift (GitHub, AST fingerprint), Dosu (freshness score in CI), Falconer (docs as code).
See [[project_platform_knowledge_substrate]] [[reference-context-engineering]].
