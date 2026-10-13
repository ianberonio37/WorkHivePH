---
target: plant-connections.html (design lens W45985, as Hector Salvador)
total_score: 39
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\plant-connections.html"
target_fingerprint: "sha256:e6b6a3f4a97037792d4d1dac721fa247e420478a39f65f3b242f9c1c84bc7efc"
target_path: "C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\plant-connections.html"
timestamp: 2026-10-12T17-05-21Z
slug: plant-connections-html
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: plant-connections.html as Hector Salvador (supervisor) - 2026-10-13, design lens W45985

Mode: Operate (a supervisor checking whether the plant's systems and sensors are connected and healthy). Walked through
the Playwright MCP at phone-390 and desktop-1280, signed in through the wall; every finding below was verified live.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 4 | 4 | four tiles each name what is missing: never synced, 0 sensors, no traffic, defaults only |
| 2 | Match System / Real World | 3 | 3 | "1 system - synced never synced" fixed; "Anomaly Engine 2.0" still an internal version name |
| 3 | User Control and Freedom | 4 | 4 | refresh, the CMMS / Plant-IoT switch, details on demand |
| 4 | Consistency and Standards | 3 | 4 | the page asked for Poppins and never loaded it - the only system-font page among its neighbours |
| 5 | Error Prevention | 4 | 4 | "Supervisor only" said up front |
| 6 | Recognition Rather Than Recall | 4 | 4 | each tile names its source and state in words |
| 7 | Flexibility and Efficiency | 3 | 4 | the next step sent the supervisor to a guide and to CMMS Integration with no link - now buttons |
| 8 | Aesthetic and Minimalist Design | 4 | 4 | one verdict, four tiles, one next step, details folded |
| 9 | Error Recovery | 4 | 4 | each failure branch says where to look (401 auth, 429 rate limit) |
| 10 | Help and Documentation | 3 | 4 | the gateway guide existed and was named, not linked |
| **Total** | | **36/40** | **39/40** | Good -> Excellent |

## Design Specificity Verdict
Authored for a plant: OPC-UA / MQTT gateways, sensor topics, CMMS sync freshness, PDPA retention windows and SSO review are
the page's own vocabulary, and the next step changes with the plant's actual state (no CMMS, stale sync, failing API, no
sensors, SSO pending).

Deterministic scan (Assessment B): clean - no claim needed. Walk: 0 overlap, 0 controls under 44 px, 0 low-contrast
readings, smallest text 12 px, 0 heading skips, no spill, 0 off-token colour reads, at both widths.

## What's Working
- The verdict is a watch list in words ("no sensors mapped - compliance defaults"), not a colour alone.
- The next step is chosen by severity (breakage, then missing wiring, then nudges).
- A missing sensor feed says what still works: the anomaly engine runs on logbook and PM signals.

## Priority Issues (all fixed in this walk, verified live)
- [P2] **The next step named places it did not link.** "Open CMMS Integration" and "The Sensor and CMMS Gateway Operations
  guide sets up the bridge" were sentences only - the guide exists (learn/sensor-cmms-gateway-operations, the page's own
  learn_links entry). Those two branches now carry the platform's Action Brief button: "Open the gateway guide ->" (44
  px, the guide answers 200) and "Open CMMS Integration ->".
- [P2] **"1 system - synced never synced"**: the freshness label already said "never synced" and the line prefixed it with
  "synced". Now "1 system - never synced".
- [P3] **The page never loaded its typeface**: it named Poppins and had no font link, so it rendered in the system font
  beside pages in Poppins. Now the platform's own link (display=optional, so a slow font cannot shift the layout).

## Persona Red Flags
- **Supervisor told to set up the bridge**: given the guide's name and no way to open it. Fixed.

## Minor Observations
- "Anomaly Engine 2.0" is an internal version number on a supervisor's page.
- The seeded integration is named "Generic REST (Local Mock)".
- ai-quality, agentic-rag-observability and status also load no Poppins (status perhaps on purpose: a status page should
  render without third-party fonts).

## Questions to Consider
- Should the three other pages without Poppins load it too, or should status keep the system font deliberately?
- Should "Anomaly Engine 2.0" read as what it does ("the anomaly engine")?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
