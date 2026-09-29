# Joining and growing your WorkHive hive (your team's private workspace)

> How a WorkHive hive works: solo mode for individual workers, joining an existing plant hive, supervisor approval, how the two roles differ from the four nav view modes, and data isolation between hives.

Source: https://workhiveph.com/learn/joining-and-growing-your-hive/

Hive · Team workspace guide

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 24 Aug 2026
·
7 min read

**Short answer:** A WorkHive hive is your plant's isolated workspace containing assets, logbook, PM schedules, people, and history. Workers can use WorkHive in solo mode (private to them) or join a plant hive (supervisor-approved). A hive has two roles, worker and supervisor, and separately the navigation offers four view modes that change which tools you see rather than what you may do. Data isolation is enforced at the database row level; nothing leaks between hives. A group running several plants runs several hives: one per plant: because corporate roll-up across them is roadmap, not product.

Who this is for

- New workers signing up to WorkHive
- Plant managers setting up a hive
- Supervisors approving new members
- Engineers joining multiple sites
- Contractors with scoped access needs
- OFW-track workers in solo mode
- New graduates building portfolios

## What a hive is, in concrete terms

The hive is WorkHive's team workspace: a private space for one plant's team. One plant equals one hive. Inside the hive:

- **People:** every worker who has joined this hive with their role and skill matrix
- **Assets:** the canonical asset register in Asset Hub
- **History:** all logbook entries, PM completions, fault notifications, parts consumption
- **Schedules:** PM plans, shift handovers, day planner blocks
- **Knowledge:** AI Assistant context trained on this hive's data

Workers in Hive A cannot see Hive B's data. Period. No path through the UI, no path through the API, no path through the AI assistant. This is the foundation that lets a Cabuyao chocolate factory and a Cebu food plant both use the same WorkHive platform without ever leaking data to each other.

## Solo mode: WorkHive without a plant

Many workers do not have a plant hive yet. They might be:

- A freelance maintenance engineer between contracts
- An OFW-track new graduate building a portfolio for the Saudi or UAE market
- A contractor whose client has not adopted WorkHive yet
- A student learning industrial maintenance during practicum
- A worker whose plant is still on paper and they want to start digital personally

Solo mode is for them. Sign up with a username and password - no email needed - and get the full WorkHive toolset (Logbook, Engineering Design, Skill Matrix, AI Assistant, Day Planner) scoped to a personal hive of one. Solo data stays private; nobody else sees it. Joining a plant hive later does not move any of it: there is no import step, and no choice to make. Your solo hive stays yours and keeps its entries; the plant hive is a second membership alongside it. Your skill badges are held against your name rather than against either hive, so those show up wherever you are.

This is one of the under-told values of WorkHive: it works as a personal professional toolkit, not only as a plant tool.

## How to join an existing plant hive

Three steps:

1. **Sign in or create an account.** Username plus password, no email needed; takes about 30 seconds.
2. **Enter the hive code.** Your supervisor gives it to you. There is no public directory of plants to browse: deliberately, because a searchable list of which plants use which software is not yours to publish.
3. **Request to join.** You join as a worker; there is no role to pick. The supervisor sees the request and approves it, and can promote you afterwards if your job calls for it.

After approval, the worker gets immediate access to the hive's tools. Existing logbook entries become searchable; PM assignments start appearing in their queue.

## Two roles, and four ways to view the same nav

This trips people up because the words overlap, so take them separately.

**There are two ROLES: worker and supervisor.** That is the whole list. Creating a hive makes you its supervisor. Everyone who joins is a worker until a supervisor promotes them. A supervisor can approve and reject join requests, remove members, publish a shift plan, recompute risk scores, and read the full audit log; a worker does the maintenance work and records it.

**Separately, the navigation has four VIEW MODES** — All, Field, Supervisor and Engineer: which filter which tools you see so a technician is not scrolling past integration settings to reach the logbook. Switching to Engineer view does not grant you anything; it is a lens on the same menu, and anyone can switch it.

Two gates are worth separating from both: the full audit log is supervisor-only, and the AI Quality dashboard is gated by the hive's maturity stair rather than by anyone's role: a hive earns it, a person is not granted it.

The tool this guide is about

### WorkHive Hive is your plant's workspace

The Hive dashboard is the supervisor's home for the plant team: who is in the hive, who is requesting to join, current PM compliance, open issues, and adoption score. Set up your hive once and every other WorkHive tool inherits the membership and roles. Free at the worker tier. One plant is one hive today; grouping several sites under one roll-up is on the roadmap rather than in the product, so plan a multi-site rollout as separate hives for now.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Data isolation between hives

Multi-tenancy in industrial software is hard because the consequences of leakage are severe. A competitor seeing your fault history, a supplier seeing your consumption forecast, a contractor seeing your cost data: any of these is grounds for losing the platform's trust.

WorkHive enforces isolation at three layers:

- **Automatic per-hive data isolation:** every query the app makes is scoped to your hive's ID on the database server itself, so one hive can never read another's records. There is no "view all" backdoor.
- **API token scope:** integration tokens are bound to a single hive. A leaked token for Hive A cannot retrieve Hive B's data.
- **AI assistant context:** the AI's vector store and retrieval index are partitioned per hive. The AI literally cannot answer a question with another hive's data because it cannot read it.

Cross-hive access exists but only via explicit, scoped, named permissions: a contractor whose work spans multiple plants, a supplier on consignment stock across a network. Default is total isolation.

## Running several plants

Filipino conglomerates often run 3 to 20 plants across the country. The pattern that works:

- **Each plant is its own hive.** Day-to-day operations stay autonomous; each plant's supervisor manages their own membership and PM schedule.
- **There is no group layer yet.** A corporate roll-up across child hives: one dashboard showing PM compliance, MTBF, MTTR and OEE for every plant: is on the roadmap and not in the product, so a director wanting the comparison today collects it per plant. Worth knowing before you plan a rollout around it.
- **Per-plant benchmarking** becomes natural. Plant A's PM compliance is 87 percent; Plant B's is 62 percent. The corporate team can see the gap and dispatch help.

**The bigger picture:** The hive is not just a workspace; it is the trust boundary. Plants adopt WorkHive because the boundary is real and enforced at the database. Workers join hives because their skill badges are held against their own name and survive leaving; the plant's records stay with the plant, which is the same boundary read from the other side. Both halves of the trust equation are needed for a free industrial platform to work in the Philippines, where data sensitivity is high and trust in cloud SaaS is still being earned.

## Frequently asked questions

### What is a WorkHive hive?

A hive is your plant's isolated workspace in WorkHive. Each hive contains its own assets, logbook entries, PM schedules, skill matrix, and people. Workers from one hive cannot see another hive's data without explicit cross-hive permission. The hive is the unit of multi-tenancy: one plant equals one hive (or a group of hives for multi-site operations).

### Can I use WorkHive solo, without a plant hive?

Yes. Solo mode lets an individual worker (a freelance maintenance engineer, an OFW-track new graduate building a portfolio, a contractor between gigs) use the full WorkHive toolset (Logbook, Engineering Design, Skill Matrix, AI Assistant, Day Planner) without joining any plant. Solo data stays private to that worker. Joining a hive later adds a membership rather than moving anything: the solo hive keeps its own entries, and there is no import step to decide about.

### How does joining a plant hive work?

Three steps: (1) the worker creates an account or signs in; (2) the worker enters the plant's hive code - there is no public directory of plants to search - and requests to join; (3) the plant's supervisor approves the request. Everyone joins as a worker; a supervisor can promote someone afterwards. The new joiner gets immediate access to the hive's data and tools.

### What roles exist within a hive?

Two: worker and supervisor. Creating a hive makes you its supervisor; everyone who joins is a worker until a supervisor promotes them. Supervisors approve join requests, remove members, publish shift plans, recompute risk scores and read the full audit log. Separately - and this is the part that causes confusion - the navigation has four VIEW MODES (All, Field, Supervisor, Engineer) that filter which tools you see. Switching to Engineer view grants nothing; anyone can switch it. The AI Quality dashboard is gated by the hive's maturity stair rather than by any role.

### How is plant data kept private from other hives?

Data isolation is enforced at the database row level itself. Every query the WorkHive app makes is automatically scoped to the joined hive's data. There is no path through the UI or the API for a worker in Hive A to see Hive B's data. Contractors and suppliers who need cross-hive access get explicit scoped permissions; nothing else crosses the boundary.

### What about multi-site operations (a company with several plants)?

Each site is its own hive. The parent company can create a hive group that lets the corporate maintenance director see roll-up KPIs across all child hives without seeing operational detail. Each child hive remains independent for day-to-day operations. This is the pattern for Filipino conglomerates running 3 to 20 plants across the country who want benchmarking without violating per-site autonomy.

## Sources

- Supabase, **Row Level Security documentation**. The PostgreSQL feature WorkHive uses to enforce hive isolation at the database layer.
- WorkHive platform positioning, "Four Gaps One Hive" with the hive as the per-plant boundary. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [Digital logbook rollout](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/) · [Skill matrix](https://workhiveph.com/learn/skill-matrix-for-maintenance-technicians/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: d52630bd63ebfb7d -->
