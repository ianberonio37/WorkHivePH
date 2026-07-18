---
name: doc-COMPANION_WIRING_PROBE_STUDY
type: doc
source: file:COMPANION_WIRING_PROBE_STUDY.md
source_sha: 09fbcee478703702
last_verified: 2026-07-13
supersedes: null
---
## doc · COMPANION_WIRING_PROBE_STUDY

> **Comprehensive study (2026-06-12).** The existing [COMPANION_PROBE_TAXONOMY.md](COMPANION_PROBE_TAXONOMY.md)

**Sections:** Companion WIRING Probe Study — testing every function inside the AI · 0. The honest headline — what we are NOT testing today · 1. The complete wiring map (what MUST be probed) · 1a. The gateway pipeline — ~26 cross-cutting stages, in order (`ai-gateway/index.ts`) · 1b. The model chain (`ai-chain.ts`) · 1c. The routed agent paths (each is its own wiring) · 1d. The 27 shared primitives · 2. THE WIRING-AXIS PROBE FAMILIES (the expansion: J–N) · J. Pipeline-stage coverage (the gateway spine) → dim `pipeline` · K. Memory-layer coverage (all 7 layers, each via an agent that wires it) → dim `memory` · L. Cross-agent path coverage (drive the agents the launcher can't) → dim `agent`/`rag` · M. Model-chain resilience (fault injection) → dim `cost`/ops · N. Persona-contract wiring (the persona IS the spec) → dim `persona` · O. Persona-Knowledge Layer (L08) wiring → dim `rag`/`persona`/`memory` · 3. Coverage gap map (wiring axis) · 4. Build plan (highest-leverage first) · 5. Decisions needed (Ian) · 7. BUILD ROADMAP — sequenced so we don't drift · Phase W0 — Foundation: make wiring coverage measurable  *(no probes yet; prevents drift)*  ✅ DONE 2026-06-12 · Phase W1 — Cross-agent reach (Family L)  *(biggest unlock, no gateway code)*  ✅ DONE 2026-06-12 · Phase W2 — DB-effect persistence probes (K2/K9/K10, J9)  *(deterministic, proven method)*  🟡 PARTIAL 2026-06-12 · Phase W3 — Structural injection probes (J1, K3, K5, K8)  *(the rigorous core; touches the gateway)*  ✅ DONE 2026-06-12 · Phase W4 — Model-chain fault injection (Family M)  *(ops lane, offline)*  ✅ DONE 2026-06-12 · Phase W5 — Remaining pipeline + persona wiring (Family J rest, N, K11)  ✅ DONE 2026-06-12 · Phases W6–W8 — Persona Knowledge Layer (L08): BUILT + PROVEN  ✅ DONE 2026-06-12 · Phase W7 — Persona Knowledge Layer (L08): Retrieve + Wire  *(build part 2; touches the gateway)* · Phase W8 — Persona Knowledge Layer: live probe Family O (Playwright MCP) · Phase W9 — Full live battery sweep  *(the capstone Ian asked for)*  ✅ WIRING SWEPT TO 55/62 — 2026-06-12 · Phases W10–W13 — PERSONA KNOWLEDGE: ENRICH + KEEP FRESH (un-bind the personas from the platform)  📋 PLANNED 2026-06-12 · Phase W10 — CHANNELS + drop-folder  *(the loaders — make the pipe accept anything, CI-ready)*  ✅ DONE 2026-06-12

(Deep source: `file:COMPANION_WIRING_PROBE_STUDY.md` — retrieve this TOC to know WHICH section to read.)
