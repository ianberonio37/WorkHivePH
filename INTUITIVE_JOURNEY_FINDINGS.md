# INTUITIVE_JOURNEY_FINDINGS.md — seed findings for the platform-wide deep intuitive-journey arc

**Created 2026-06-26 · Owner: Ian + Claude · Status: SEED (live-grounded) — formal framework/roadmap synthesizing in `wf_6a4c4eda` (skills + reputable UX sources).**

> **Ian's seed critique (2026-06-26):** *"persona walk still shallow… do a full diverse journey end to end, hands-on. Same as analytics — you dropped most of it, didn't check diagnostic/preventive/prescriptive. On the hive board, do you UNDERSTAND all of those, are the input fields working + relevant + non-redundant? In analytics → asset-hub → reliability ML, how do clickables affect those? There's 'Neighbors + edge' — what is this, relevant? needed? how does a user understand it? Those alerts — so many a user is overwhelmed, how does acting affect the whole analytics / other pages? You can't even press back to the previous page. Refine my thoughts, ask my skills, reputable sources, synthesize. I'm OK to revamp/refactor — nothing is firm — as long as it becomes INTUITIVE to all users."* + *"not only those mentioned, there are so many across my feature pages I haven't mentioned."*

The prior arcs proved each surface is *reachable / completable / low-click / pretty / individually-correct* (Arcs K/V/W/X, gates green). This arc asks the next question: **is the platform INTUITIVE end-to-end** — does a real (often novice) user UNDERSTAND each thing, NEED it, not get CONFUSED or OVERWHELMED, see what their clicks DO across surfaces, and always find their way (and BACK)? Method = a real **cognitive walkthrough, operated hands-on live** (not screenshot-judging), across **ALL ~42 feature pages** (every mode/panel/affordance), not just the named examples.

## The 6 intuitiveness lenses (Ian's critique → grounded method)
| # | Lens | The user-question | Method / source |
|---|---|---|---|
| **L1** | **Comprehension** | "Do I understand what this is + does?" (jargon, unexplained features) | Norman's Gulf of Evaluation; NN/g match-system-to-real-world; Cognitive-Walkthrough Q3 |
| **L2** | **Overwhelm / cognitive load** | "Is this too much at once? where do I start?" | Miller 7±2; progressive disclosure; NN/g aesthetic-minimalist; GDS one-thing |
| **L3** | **Relevance & redundancy** | "Is this needed, or duplicated elsewhere?" | IA critic verbs TRANSFER / STREAMLINE / REMOVE / RELABEL (`tools/ia_semantic_critic.py`) |
| **L4** | **Cross-surface effect** | "When I click this, what happens — and can I see its effect on other pages?" | Norman's Gulf of Execution + visibility-of-system-status (Nielsen #1) |
| **L5** | **Flow & wayfinding / BACK** | "Where am I, what's next, can I get back?" | Nielsen #3 user-control-&-freedom; wayfinding; web/mobile back-button expectation |
| **L6** | **Does it actually work** | "Is this affordance wired + relevant, or dead/redundant?" | hands-on operate every clickable + input (the `__UFAI.clickAudit/formAudit` gap) |

## Live-grounded findings (hands-on, Baguio supervisor, 2026-06-26)
| # | Surface | Lens | Finding (operated live) | Direction (Ian decides) |
|---|---|---|---|---|
| F1 | **analytics** | L2 + L1 | 4 modes (Descriptive/Diagnostic/Predictive/Prescriptive) × 5-8 panels = **~24 analytical surfaces**, each citing ISO/SAE/SMRP + a stats method (Spearman, SPC, RCM, Weibull). A novice can't tell what a mode is *for*, when to use it, or read the methods. (I'd judged only the 1st mode.) | per-mode "what this tells you / what to do" plain-language framing; a maturity-ladder explainer; defer the stats behind disclosure |
| F2 | **asset-hub detail** | L1 + L2 | **~12 sections** in one detail (Risk Profile, Reliability Print SAE JA1011, Live Telemetry MQTT/OPC-UA, Timeline, **Neighbors "+ Add edge"**, External systems, Marketplace, Ask Brain, Add failure mode, Set RCM strategy…). **"+ Add edge"** is graph-theory jargon a maintenance worker won't parse. | rename "edge" → plain ("link a related asset"); group/disclose the 12 sections; explain Neighbors' purpose or cut it |
| F3 | **back-navigation** | L5 | **Broken + platform-wide (confirmed):** asset-detail → browser-back → landed on *analytics* (not the asset list); pm-scheduler detail open didn't even change the URL. In-page screen-swaps + `replaceState` don't integrate with browser/hardware/gesture-back; only a per-page "Back" button works (must be re-learned each page; fails mobile-back muscle-memory). | pushState the screen-swaps so browser/gesture-back returns to the list; consistent back affordance |
| F4 | **alert-hub** | L3 + L2 | **65 alerts (60 high-sev).** Category chips (AMC/Risk/PM/Stock/Staging) triage somewhat, but the same **30 PM-overdue** appear here AND on pm-scheduler AND home — redundant re-aggregation; unclear how acting on one propagates to analytics/other pages. | does the hub ADD value or duplicate? define "act → effect" visibility; a "today's priority / start here" |
| F5 | **logbook** | L2 (+L1 positive) | "Log a Repair" = **18 fields**. Dense for a quick fault-log (friction/abandonment risk). BUT labels are **plain-language** ("What was wrong?", "What did you do?") = a comprehension *positive* to replicate elsewhere. | a quick-log vs full-log path; carry the plain-language labeling pattern to the jargon-heavy surfaces |

## Scope + method
- **Platform-wide:** all ~42 feature pages, both index states, every mode/panel/affordance — Ian: "so many across my feature pages I haven't mentioned." Nothing dropped.
- **Hands-on live** (Playwright MCP), operate every affordance + input, follow cross-surface effects, test browser/gesture BACK — a real cognitive walkthrough, not a screenshot referee. Fan out per-page once the framework is locked so coverage is exhaustive.
- **DEFECT (broken/dead/jargon-confusing) → fix; CRITIC (redundant/overwhelm/transfer/streamline) → propose for Ian's disposition** (engine proposes, owner disposes). Ian is open to revamp/refactor — intuitiveness for ALL users is the bar.

_The formal framework + per-surface ground-truth + phased revamp roadmap + the genuine forks are synthesizing in `wf_6a4c4eda`; this seed doc holds the live-grounded findings + lenses._
