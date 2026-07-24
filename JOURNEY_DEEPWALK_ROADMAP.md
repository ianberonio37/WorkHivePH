# Journey Deepwalk Roadmap — every production page, end to end

**Ian's mandate (2026-07-24):** *"everything, journey each of my production pages end to end, because
my platform is beneficial to my users. you have to segregate first the type of journeys using phases
and percentage completion, so that you won't be lost using anti-drift."*

This is the anti-drift compass for the exhaustive live-MCP journey sweep. It is the **Engine-A driver**
of the dimension-expansion flywheel ([[DIMENSION_EXPANSION_FLYWHEEL.md]] §2: the live journey seeds
every harvest). The **measured** state lives in `journey_deepwalk_state.json`; the % is computed by
`tools/journey_deepwalk_scoreboard.py` (the roadmap-% = anti-drift-compass pattern — never vibe the
completion). Run it for the live scoreboard + the single deterministic NEXT journey:

```
python tools/journey_deepwalk_scoreboard.py          # the board + NEXT
python tools/journey_deepwalk_scoreboard.py --next    # just the next journey (machine-readable)
```

## The 5 phases every journey walks

| Phase | Meaning |
|---|---|
| **G · Ground** | Map the journey's real steps + surfaces (from the page + skills/Memento) before touching the browser. |
| **W · Walk** | Live-MCP deepwalk **end to end** as a real user, at the real viewport (desktop + mobile). |
| **O · Observe** | Record every friction/idea the walk surfaces — the raw material. **Measure** each (don't assume). |
| **H · Harvest** | For a REAL, non-owned friction → `night_crawler --query "<friction>"` (bag-check first). A CLEAN journey harvests nothing — that is a valid result, not a gap. |
| **R · Resolve** | The friction becomes: a new dim (triple-locked + fault-injected), a killed candidate (with proof), a shipped fix, or "clean — no action". |

A journey is **complete only when all 5 phases are `done`** (`partial` = 0.5, `todo` = 0.0). The
compass will not let a half-walked journey be skipped — it returns the partial phase as NEXT.

## The 12 journey TYPES (segregated by job-to-be-done)

| Type | Journeys | Why it matters |
|---|---|---|
| **T1 · Onboarding / first-run / auth** | index, hive first-run | the first minutes decide if the platform is beneficial at all |
| **T2 · Capture / data-entry** | logbook✓, inventory, pm-scheduler, voice-journal, skillmatrix, community | the core value: field reality into the hive without loss |
| **T3 · Review / approval / moderation** | asset-hub✓, alert-hub, audit-log, marketplace-admin | the trust + accountability spine (AI-vs-human authorship, role-gates) |
| **T4 · Analysis / insight** | analytics, asset-hub Q+A, shift-brain, ph-intelligence | where AI output + chart truth are read as fact |
| **T5 · Report / export / send** | report-sender✓, analytics-report, project-report | a document LEAVES the platform (provenance on a forwardable artefact) |
| **T6 · Planning / scheduling** | dayplanner, project-manager | multi-resolution, stateful flows where in-motion friction hides |
| **T7 · Calculation** | engineering-design | the most complex stateful form (discipline→calc→inputs→BOM/SOW) |
| **T8 · Commerce** | marketplace, marketplace-seller, seller-profile | trust signals, disclosure, multi-step contact |
| **T9 · Configuration / integration** | integrations, plant-connections | setup where a wrong step silently breaks downstream data |
| **T10 · Social / gamification / assistant** | public-feed, achievements, assistant | engagement + the always-on AI companion |
| **T11 · Admin / founder console** | founder-console, platform-actions | cross-hive oversight (service-role, aggregates) |
| **T12 · Cross-page hand-off** | alert→asset→logbook, asset→pm, analytics→report | the TRUE multi-surface tasks — where context dies between pages (the JA class came from here) |

✓ = already walked + complete this session (logbook capture, asset-hub approval, report-sender send).

## How this drives the flywheel

1. `journey_deepwalk_scoreboard.py --next` names the journey + phase.
2. Walk it live (Engine A) → observe + **measure** friction.
3. Real, non-owned friction → harvest (Engine B) → §3 prove non-redundancy → build/kill/fix.
4. Update `journey_deepwalk_state.json` (mark phases done, add a `note`), re-run the compass.
5. The compass % rises deterministically; the sweep cannot drift or double-back.

**Done = the ROADMAP done, not one journey.** Overall 100% means all 35 journeys × 5 phases are
`done`. A green single journey is necessary, never sufficient (the ★★★ one-metric-≠-roadmap rule).
