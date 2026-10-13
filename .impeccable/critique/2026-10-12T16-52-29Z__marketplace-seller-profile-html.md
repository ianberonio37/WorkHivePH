---
target: marketplace-seller-profile.html (design lens W45957, Oscar Ramos viewing Bryan Garcia)
total_score: 39
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\marketplace-seller-profile.html"
target_fingerprint: "sha256:ed6cd93bd0be852cfd9b3e1c3c0500424bf2ec1ea08cbc4edea802cf7495606f"
target_path: "C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\marketplace-seller-profile.html"
timestamp: 2026-10-12T16-52-29Z
slug: marketplace-seller-profile-html
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: marketplace-seller-profile.html (Bryan Garcia's profile) as Oscar Ramos - 2026-10-13, design lens W45957

Mode: Operate (a buyer deciding whether to trust and contact a seller). Walked through the Playwright MCP at phone-390
and desktop-1280, signed in through the wall, on ?worker=Bryan Garcia; the failure path was forced on a throwaway page.
Every finding below was verified live before it counted.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 3 | 4 | "5.0★ (2)" above "1 review" with the reason only in a screen-reader span - now the header says both counts |
| 2 | Match System / Real World | 4 | 4 | PRC and TESDA certifications verified by an admin, ID verified, contact is free and WorkHive takes no fee |
| 3 | User Control and Freedom | 4 | 4 | back to the marketplace, listing filters, view in forum |
| 4 | Consistency and Standards | 3 | 4 | a light cyan, two greys and a near-navy that are no platform token - now the tokens |
| 5 | Error Prevention | 4 | 4 | the rating counts verified purchases only - unverified reviews cannot move it |
| 6 | Recognition Rather Than Recall | 4 | 4 | trust badges together under the name; the figures' source stated under the tiles |
| 7 | Flexibility and Efficiency | 4 | 4 | View Listings jumps to the list; Parts / Training / Jobs filters |
| 8 | Aesthetic and Minimalist Design | 3 | 3 | calm and grouped; a listing with no photo still gets a 200 px camera placeholder |
| 9 | Error Recovery | 3 | 4 | a failed replies read showed "0" replied and a dash - now "Not loaded" in both |
| 10 | Help and Documentation | 4 | 4 | the page explains contact, fees, reply times and the 10% credit in plain words |
| **Total** | | **36/40** | **39/40** | Good -> Excellent |

## Design Specificity Verdict
Authored for a Philippine trades marketplace: PRC and TESDA certifications sit beside "Verified by admin", the badge row
separates ID verification from certification from community trust, and the page tells a buyer that contact is free,
WorkHive takes no fee, and a part number plus a photo gets the fastest reply.

Deterministic scan (Assessment B): clean - no claim needed. Walk: 0 overlap, 0 controls under 44 px, 0 low-contrast
readings, smallest text 12 px, 0 heading skips, no spill, at both widths; off-token colour reads 14 -> 6 (the bronze tier
is a categorical scale like community's medals; one grey review text remains).

## What's Working
- The rating is the canonical verified-purchase average, not a recount of whatever reviews loaded.
- Trust is decomposed: ID, certification and community standing are separate claims with separate sources.
- The figures say where they come from ("this seller's listings, replies and verified purchases").

## Priority Issues (all fixed in this walk, verified live)
- [P2] **Two counts that looked like a contradiction.** The rating reads "5.0★ (2)" - two verified purchases rated - and
  the Reviews header read "1 review", the reviews written. Both true; the reason lived only in a screen-reader span, so a
  buyer comparing them saw the profile disagree with itself. Where they differ the header now says "1 written review - 2
  verified ratings". (/impeccable clarify)
- [P2] **"Avg Reply" was a bare green dash** - read as good or as broken - and a failed replies read was indistinguishable
  from none: the read ignored its returned error, so a refusal painted "0 replied". The read now throws on error; with no
  reply yet the cell says "None yet" in neutral text, and a failed read says "Not loaded" in both cells. Forced on a
  throwaway page with the replies read returning 500: "Not loaded" / "Not loaded". (/impeccable harden)
- [P3] **Off-token colours**: the verified badge's #8fdcf0, the count and chip greys #8b97a4, the call to action's #0f1923
  text. Now --wh-blue-text, --wh-text-muted, --wh-navy.

## Persona Red Flags
- **Buyer checking a seller before driving to meet him**: "(2)" and "1 review" side by side, and a dash where the reply
  time should be. Fixed.

## Minor Observations
- "Member since 2 months ago" above a review 104 days old - seeded data, but the profile shows both.
- A listing without a photo keeps a large camera placeholder.
- The page background is #0f1923, the deep navy several pages share without a token.

## Questions to Consider
- Should "Member since" name what it counts (since joining the marketplace) so an older review cannot contradict it?
- Should a listing without a photo collapse its image area instead of drawing a 200 px placeholder?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
