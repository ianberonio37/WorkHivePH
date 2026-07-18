---
name: doc-DATA_DB_UFAI_ROADMAP
type: doc
source: file:DATA_DB_UFAI_ROADMAP.md
source_sha: 4a128e9dd4eb808e
last_verified: 2026-07-13
supersedes: null
---
## doc · DATA_DB_UFAI_ROADMAP

_Spine doc for the Data/DB arc. Same method as Arc D (frontend) / Arc E (edge backend) /

**Sections:** DATA / DATABASE LAYER — UFAI MATURITY ROADMAP (Arc G) · §0 — Why this layer, in one paragraph · §1 — Sub-layers (rows) × current baseline % → target % (denominator mined live, 2026-06-20) · §2 — Per-lens VERIFIED floors (declared up front, honest live bar) · §3 — Phasing (G0 → G5) · §4 — Keystone fixes the arc will surface (the build, not just the score) · §5 — Honest ceilings (named up front, not discovered late) · §6 — Scoreboard (G0 measured baseline, `tools/data_db_ufai_sweep.py --accept`, 2026-06-20) · ★ G1 keystone — cross-tenant DEFINER IDOR class: found → fixed → verified → gated (2026-06-20) · ★★ G2 — RLS is DEFEATED on 9 core hive-private tables (the auth-migration enforcement gap, 2026-06-20) · ★★ G2 keystone — 37/38 truth views BYPASSED RLS (read-path isolation was OFF platform-wide, 2026-06-20) · ★ Per-OBJECT depth — the sweep deepened from 6 sub-layer cells to 488 individual objects (2026-06-20) · ★ Per-object finding: `worker_achievements` was anon-readable platform-wide (the personal-class blind spot) · ★ G3 (U) RPC return-shape gate + G5 Accept (ratchet locked) (2026-06-20) · ★ G2 live-isolation harness made type-agnostic (false "discover-error" fixed) (2026-06-20)

(Deep source: `file:DATA_DB_UFAI_ROADMAP.md` — retrieve this TOC to know WHICH section to read.)
