# Connecting WorkHive to SAP, IBM Maximo, and other CMMS

> How to connect a free worker-facing logbook layer to your existing SAP, IBM Maximo, or other paid CMMS. Integration patterns, data mapping, OPC-UA and MQTT for sensors, and the common gotchas.

Source: https://workhiveph.com/learn/connecting-workhive-to-sap-maximo-cmms/

Integrations · SAP, Maximo, OPC-UA, MQTT

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 24 Aug 2026
·
9 min read

**Short answer:** WorkHive runs underneath your existing SAP PM, IBM Maximo, or other paid CMMS as the worker-facing capture layer. Four integration patterns are supported: one-way push (work-order completion to ERP), one-way pull (asset master from ERP), two-way sync, and batch CSV. Sensor data flows in via OPC-UA or MQTT through a local edge gateway. The most common mistake is integrating before you have 90 days of stable WorkHive Logbook data; the second most common is treating it as an IT project instead of a maintenance operations change.
 Wait for those **90 days** before you connect SAP PM or IBM Maximo.

Who this is for

- Maintenance and reliability engineers
- IT and OT systems teams
- Plant managers planning ERP modernization
- SAP / Maximo administrators
- Integration consultants and SI partners
- Contractors needing work-order access
- Suppliers on consignment-stock models

## WorkHive runs under your CMMS, not against it

Most Philippine plants that have SAP PM or IBM Maximo did not get the floor adoption they paid for. The reason is consistent: the ERP UI was designed for office desktops, the technicians work on the floor, and after 6 months of frustration the floor goes back to paper. The plant now has both the ERP cost and the paper problem.

WorkHive does not try to replace SAP or Maximo. Those systems do procurement, finance, master data, and formal work-order accounting better than a free tool ever will. What WorkHive replaces is the paper that the floor went back to. The architecture:

- **SAP / Maximo:** the system of record for assets, work orders, parts catalogue, and finance.
- **WorkHive:** the system of engagement for technicians, supervisors, engineers, contractors. Logbook entries, PM completion, fault history, shift handovers, skill matrix, AI assistant.
- **Integration layer:** moves the data between them so finance has what it needs and the floor has what they will actually use.

This is the pattern the [Chronicle's May 2026 analysis of ERP failures](https://thechronicle.com.ph/why-many-imported-erp-systems-fail-in-the-philippines/) recommends: "prioritize localized, appropriately-scaled solutions" that respect the operating reality, not the marketing slide.

## The 4 integration patterns

| Pattern | Direction | Typical use | Complexity |
| --- | --- | --- | --- |
| **1. One-way push** | WorkHive → ERP | Work-order completion, parts consumed, fault entries | Low (1 month) |
| **2. One-way pull** | ERP → WorkHive | Asset master, planned PM schedule, open work orders | Low to Medium (1 to 2 months) |
| **3. Two-way sync** | Bidirectional | Full work-order lifecycle, status round-trip, parts inventory | High (3 to 6 months) |
| **4. Batch CSV** | Manual / scheduled | Plants without API access, monthly reconciliation only | Very Low (days) |

Most Philippine plants start with Pattern 1 or 2 because they get value fast: the technicians close work orders in WorkHive and the completion appears in SAP without anyone retyping. Pattern 3 is the long-term goal but takes 6 months of stable Pattern 1 + 2 operation first.

## SAP PM and IBM Maximo specifics

### SAP PM

WorkHive reads SAP PM through an **OData** endpoint you configure. It polls on a schedule and fetches only records changed since the last successful run, so a large plant is not re-reading its whole work-order history every cycle.

**Authentication is a bearer token.** You give WorkHive an endpoint URL and a token; it sends that token as an `Authorization: Bearer` header. There is no OAuth dance and no basic-auth flow to configure, which is less flexible than a full ERP middleware and considerably less work to stand up. Whatever your SAP gateway issues that token as, that is what you paste in.

**WorkHive does not ship a fixed list of SAP objects.** This is worth being plain about, because integration guides usually promise the opposite: you map the fields yourself in the Plant Connections console - which SAP field is the asset identifier, which is the work-order status, which is the completion date - and WorkHive translates statuses and maintenance types through that mapping. Every plant's SAP is configured differently, so a shipped object list would be a guess about yours.

Typical setup: your SAP team exposes the OData service and issues a token, then the mapping is built and tested against a small slice before the schedule is turned on. Budget a few weeks of testing, and use the dry-run option, which fetches a first page without writing anything.

### IBM Maximo

Maximo is read over **OSLC**, Maximo's own linked-data interface, with the same shape as the SAP path: an endpoint you configure, a bearer token, delta polling, and field mapping you control. Ask your Maximo administrator to expose the OSLC resources for the objects you want to pull and to issue a token for a service account.

The same caution applies: WorkHive does not ship a fixed list of Maximo objects. You choose what to pull and say which field means what.

### Other CMMS

Everything else goes through the **generic REST** connector: if your CMMS exposes an HTTP endpoint that returns records and accepts a bearer token, it can be configured the same way as SAP or Maximo, with your own field mapping on top. That covers the common mid-market systems without WorkHive claiming a bespoke connector for each - there is one connector, and it is general. If your system has no API at all, the CSV import path exists precisely for that case and is the fastest thing in this guide to get working.

## Sensor data via OPC-UA and MQTT

For Stage 3 (Predictive-Ready), WorkHive consumes sensor data from PLCs, SCADA, and IoT sensors through two industry-standard protocols:

- **OPC-UA** for traditional industrial automation (Siemens, Rockwell, Schneider PLCs and SCADA). A local edge gateway (open-source options: AVEVA Edge, Ignition Edge, Node-RED with industrial nodes) reads from your OPC-UA server and pushes condition data to WorkHive via secure HTTPS.
- **MQTT** for newer IoT sensor networks (wireless vibration, temperature, ultrasonic, energy meters). Same edge gateway pattern; the gateway subscribes to MQTT topics and forwards to WorkHive.

The edge gateway runs on-premise so sensitive plant data never leaves your network unencrypted. Only the condition-data summaries WorkHive needs are transmitted. This matters for plants with cybersecurity policies that restrict direct cloud access from the OT network.

The tool this guide is about

### WorkHive CMMS Integration is the connector layer

The CMMS Integration surface in WorkHive includes SAP PM, IBM Maximo, and generic REST live-sync, plus CSV history import, plus OPC-UA and MQTT for sensor data via a plant edge gateway. The CSV importer includes a visual column-mapping step; REST live-sync uses configurable field maps. The Plant Connections operations console (supervisor-only) shows live integration health, sync status, and any data-quality issues. Free at the worker tier. On sign-in, raise SSO early if your IT department expects to manage these accounts centrally: it is not something you switch on yourself and it is not tied to a maturity stage: an operator provisions it during enterprise onboarding, and your hive’s Plant Connections page shows whether it is configured, which provider, and whether it is enforced or optional.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Data mapping: where most integrations break

The technical connector is the easy part. The data mapping is the hard part. The pattern that breaks Philippine plant integrations:

- **Inconsistent asset codes.** SAP knows it as "PMP-101-A". The maintenance team calls it "Pump 1 ng Line 1". The supervisor's spreadsheet has "P1L1A". Without a single canonical code, the integration cannot match work orders to assets.
- **Stale SAP master data.** The asset was decommissioned in 2022 but is still active in SAP. Integration pushes work-order completion for a non-existent asset and the data corrupts the SAP register.
- **Missing functional locations.** SAP requires every work order to belong to a FunctionalLocation. If WorkHive does not have that field captured, the SAP integration fails on every push.
- **Different status enumerations.** WorkHive has 5 work-order states (OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED). SAP has 12. Without a mapping table, status updates round-trip to unexpected values.

The fix is upfront: 1 to 2 weeks of asset-master cleanup before any integration, plus a documented mapping spreadsheet that both teams sign off on.

## Contractors and outside work, without ERP seats

Plants with heavy external participation ask about this first, so here is where it genuinely stands rather than where a roadmap would like it to be.

**What works today.** Outside work is recorded as a *contractor* project, and the jobs under it point at the same asset IDs your own PMs use - so a vendor's overhaul lands in the asset's timeline beside your team's work instead of in an email. When the job is closed, the completion is pushed back to SAP automatically, which removes the retyping that makes contractor reports late. None of that requires giving anyone an ERP seat, which is the expensive part you were trying to avoid.

**What does not exist yet, stated plainly.** There is no contractor login scoped to only their own work orders, and no supplier view scoped to only their SKUs. Hive membership is whole-hive: anyone you invite can see the hive's assets and records, and the only elevated role is supervisor. So if a vendor must not see the rest of your plant, do not invite them - have your planner record the completion against the asset, which is a minute of typing and keeps the boundary real.

Scoped external accounts are a genuinely valuable pattern and a fair thing to press any vendor on. This guide will describe WorkHive's when WorkHive has one.

## 90-day stable data, then connect

The single most important rule: do not integrate until WorkHive has 90 days of clean Logbook operation. The reason is that integration amplifies data quality, in both directions. Clean WorkHive data improves SAP. Messy WorkHive data corrupts SAP. The SAP team blames the integration; the maintenance team blames the SAP team; the integration project gets cancelled.

The recommended sequence:

1. **Months 1 to 3:** WorkHive Logbook + PM Scheduler only. No integration. Validate data quality.
2. **Month 4:** Enable one-way push of work-order completion only. Monitor SAP register for 30 days.
3. **Month 5:** Add one-way pull of asset master from SAP. Verify mapping for 30 days.
4. **Months 6 to 9:** Add fault notification push, parts consumption push, PM schedule pull.
5. **Months 10+:** Two-way sync where the value justifies the complexity.

**The bigger picture:** CMMS integration is not a technology project. It is a maintenance operations change wrapped in a technical layer. Plants that respect that order get stable integrations; plants that treat it as an IT project ship a connector that nobody uses. Build the floor habit in WorkHive first, then connect it to the systems of record. Never the other way around.

## Frequently asked questions

### Does WorkHive replace SAP PM or IBM Maximo?

No. WorkHive runs underneath them as the worker-facing capture layer. SAP and Maximo handle procurement, finance, master data, and formal work orders. Your technicians do not actually use them on the floor in real time because the UI is slow and was designed for office desktops. WorkHive captures the daily floor reality (logbook entries, PM completion, parts use, fault history) and pushes it back to SAP or Maximo so the finance team and asset register stay current. You keep the ERP investment; the workers get a tool they will actually use.

### What integration patterns does WorkHive support?

Four patterns: (1) one-way push from WorkHive to ERP (work-order completion, parts consumed, fault entries); (2) one-way pull from ERP to WorkHive (asset master data, planned PM schedules, open work orders); (3) two-way sync (work orders flow both ways, status updates round-trip); (4) batch CSV export and import for plants without API access. Most plants start with pattern 1 or 2 and graduate to pattern 3 after 6 months of stable data flow.

### What about sensor data from PLCs and SCADA?

WorkHive Integrations supports OPC-UA (the industry standard for PLC and SCADA data) and MQTT (the industry standard for IoT sensor data). A local edge gateway at the plant reads from your OPC-UA or MQTT source and pushes condition data to WorkHive via secure HTTPS. The edge gateway is open-source; vendors include AVEVA Edge, Ignition Edge, and Node-RED depending on stack preference. No expensive proprietary historian required for Stage 3 PdM.

### How long does a typical SAP integration take?

Realistic timeline for a Philippine plant: 4 to 8 weeks for a one-way work-order completion push (Phase 1). 3 to 6 months for full two-way sync including asset master data pull (Phase 2). The bottleneck is usually the SAP team's availability and the data-mapping spreadsheet, not WorkHive's connector. Plants that have a clean SAP asset register integrate fast; plants with messy master data spend most of the project cleaning up SAP before connecting anything.

### Can contractors and suppliers use WorkHive through the integration?

Yes, with role-based access. Contractors get a limited-scope login that lets them log their work on the assigned assets and submit completion proof. The work-order flows from your SAP to WorkHive, the contractor completes it on WorkHive, and the completion flows back to SAP for invoicing. Suppliers can view consumption forecasts for the parts they supply (consignment stock model) without seeing other hive data. This is one of the highest-value use cases for plants with heavy contractor or consignment operations.

### What is the most common integration mistake?

Trying to integrate everything before the WorkHive side has 90 days of stable data. The result is that bad WorkHive data corrupts the SAP asset register, and the SAP team blames the integration. The correct sequence: 90 days of clean WorkHive Logbook operation first, then enable one-way push, then verify data quality for 30 days, then enable the next pattern. Plants that follow this sequence have stable integrations; plants that go fast usually have to roll back and restart.

## Sources

- Jenni Munar, **"Why Many Imported ERP Systems Fail in the Philippines"**, The Daily Chronicle, 7 May 2026. [thechronicle.com.ph](https://thechronicle.com.ph/why-many-imported-erp-systems-fail-in-the-philippines/)
- SAP, **SAP Asset Management OData Services**. Your own gateway documentation decides which services are exposed and what they are called.
- IBM, **Maximo OSLC integration documentation** - the interface WorkHive reads Maximo through.
- OPC Foundation, **OPC Unified Architecture Specification**, Parts 1 through 14.
- OASIS, **MQTT Version 5.0** specification.
- WorkHive platform positioning, "Four Gaps One Hive" with Integration as a Stage 3+ accelerator. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [Digital logbook rollout](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/) · [PdM on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 4e37a4fa2aa1f5e6 -->
