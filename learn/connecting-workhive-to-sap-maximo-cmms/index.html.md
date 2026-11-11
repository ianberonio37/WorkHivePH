# Connecting WorkHive to SAP, IBM Maximo, and other CMMS

> How to connect a free worker-facing logbook layer to your existing SAP, IBM Maximo, or other paid CMMS. Integration patterns, data mapping, OPC-UA and MQTT for sensors, and the common gotchas.

Source: https://workhiveph.com/learn/connecting-workhive-to-sap-maximo-cmms/

Integrations · SAP, Maximo, OPC-UA, MQTT

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 11 Nov 2026
·
9 min read

**Short answer:** WorkHive runs beside your SAP PM, IBM Maximo or other paid CMMS. It is the layer workers use to record the work. Four patterns work. Push sends job completions to the ERP. Pull brings in work orders on a schedule. Two-way runs both. A CSV batch loads assets, PMs, parts and history. Sensor data flows in via OPC-UA or MQTT through a local edge gateway. The most common mistake is to connect too early. Wait for 90 days of steady WorkHive Logbook data. The next mistake is to treat it as an IT project, not a change in how maintenance runs.
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

Most Philippine plants that have SAP PM or IBM Maximo did not get the floor adoption they paid for. The reason is always the same.

The ERP screens were built for office desks, but technicians work on the floor. After 6 months of frustration, the floor goes back to paper. The plant now has both the ERP cost and the paper problem.

WorkHive does not try to replace SAP or Maximo. Those systems handle buying, finance and master data. They also keep formal work-order accounts. They do it better than a free tool ever will. What WorkHive replaces is the paper that the floor went back to. The architecture:

- **SAP / Maximo:** the official record. It holds assets, work orders, the parts list and finance.
- **WorkHive:** the system of engagement for technicians, supervisors, engineers, contractors. The Logbook, PM completions and fault history. Also handovers, the skill matrix and the AI assistant.
- **Integration layer:** moves data between them. Finance gets what it needs, and the floor gets a tool it will actually use.

That means tools that fit how the plant really works, not the sales pitch. A May 2026 [Chronicle analysis of ERP failures](https://thechronicle.com.ph/why-many-imported-erp-systems-fail-in-the-philippines/) agrees. Its advice: "prioritize localized, appropriately-scaled solutions".

## The 4 integration patterns

| Pattern | Direction | Typical use | Complexity |
| --- | --- | --- | --- |
| **1. One-way push** | WorkHive → ERP | Work-order completion: the machine, who did it, the hours and the close time | Low (1 month) |
| **2. One-way pull** | ERP → WorkHive | Work orders, fetched on a schedule (assets and PMs come in by CSV) | Low to Medium (1 to 2 months) |
| **3. Two-way sync** | Bidirectional | Pull work orders and push completions on the same link | High (3 to 6 months) |
| **4. Batch CSV** | Manual / scheduled | Plants without API access, monthly reconciliation only | Very Low (days) |

Most plants here start with Pattern 1 or 2, because the value comes fast. Technicians close work orders in WorkHive, and the completion shows up in SAP. Nobody retypes it. Pattern 3 is the long-term goal but takes 6 months of stable Pattern 1 + 2 operation first.

## SAP PM and IBM Maximo specifics

### SAP PM

WorkHive reads SAP PM through an **OData** endpoint you configure. It polls on a schedule and fetches only records that changed since the last good run. So a large plant does not re-read its whole work-order history each time.

**Authentication is a bearer token.** You give WorkHive an endpoint URL and a token. It sends the token as a Bearer header. There is no OAuth or basic-auth flow to set up. That is less flexible than full ERP middleware, but far less work to stand up. Whatever your SAP gateway issues that token as, that is what you paste in.

**WorkHive does not ship a fixed list of SAP objects.** It is worth being plain here, because most guides promise the opposite. You map the fields yourself. Use the CMMS (computerized maintenance management system) Integration page.

You say which SAP field is the asset ID, which is the work-order status and which is the completion date. WorkHive then translates statuses and maintenance types through that map. Every plant sets up SAP its own way, so a fixed object list would only guess at yours.

Typical setup: your SAP team opens the OData service. It also issues a token. You then build the map and test it on a small slice. Only then do you turn on the schedule. Budget a few weeks of testing. Use Test Connection, which fetches a first page and writes nothing.

### IBM Maximo

WorkHive reads Maximo over OSLC, Maximo's own linked-data interface. It works like the SAP path. You set the endpoint and a bearer token, it polls for changes, and you control the field map. Ask your Maximo admin to open the OSLC resources you want to pull. Ask for a token for a service account too.

The same caution applies: WorkHive does not ship a fixed list of Maximo objects. You choose what to pull and say which field means what.

### Other CMMS

Everything else goes through the generic REST connector. Your CMMS (maintenance software) needs an HTTP endpoint that returns records. It must also take a bearer token. Then you set it up like SAP or Maximo, with your own field map on top.

That covers the common mid-size systems. WorkHive does not claim a custom connector for each one. There is one connector, and it is general. If your system has no API at all, use the CSV import. It exists for that case, and it is the fastest thing in this guide to get working.

## Sensor data via OPC-UA and MQTT

At Stage 3 (Predictive-Ready), WorkHive takes in sensor data. It reads PLCs, SCADA and IoT sensors. It uses two standard protocols:

- **OPC-UA** for traditional industrial automation (Siemens, Rockwell, Schneider PLCs and SCADA). A local edge gateway reads from your OPC-UA server. It sends condition data to WorkHive over secure HTTPS. Node-RED with industrial nodes is a free, open-source choice. Ignition Edge and AVEVA Edge are paid ones.
- **MQTT** for newer wireless sensors: vibration, temperature, ultrasound and energy meters. The same edge gateway listens to MQTT topics and passes the data on to WorkHive.

The edge gateway runs on site. Plant data never leaves your network unencrypted. You choose which readings the gateway sends. That matters if your security rules keep the OT network off the cloud.

The tool this guide is about

### WorkHive CMMS Integration is the connector layer

WorkHive's CMMS Integration syncs live with SAP PM and IBM Maximo. It also syncs with any REST system. It also imports history from CSV. Sensor data comes in over OPC-UA and MQTT through an edge gateway at the plant. The CSV import has a step where you match columns on screen. REST live sync uses field maps you set. The Plant Connections page is for supervisors only.

It shows live link health, sync status and data problems. Free at the worker tier. On sign-in, raise SSO early if your IT team wants to manage these accounts in one place. You cannot switch it on yourself, and it is not tied to a stage. An operator sets it up during enterprise onboarding. Your hive's Plant Connections page then shows its status. It shows the provider, and whether everyone must use it.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Data mapping: where most integrations break

The technical connector is the easy part. The data mapping is the hard part. The pattern that breaks Philippine plant integrations:

- **Inconsistent asset codes.** SAP knows it as "PMP-101-A". The maintenance team calls it "Pump 1 ng Line 1". The supervisor's spreadsheet has "P1L1A". Without one agreed code per asset, the link cannot match work orders to assets.
- **Stale SAP master data.** The plant retired the asset in 2022, but it is still active in SAP. The link pushes a completion for an asset that does not exist. The bad data then spoils the SAP register.
- **Missing functional locations.** SAP requires every work order to belong to a FunctionalLocation. If WorkHive does not have that field captured, the SAP integration fails on every push.
- **Different status enumerations.** WorkHive has 5 work-order states (OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED). SAP has 12. Without a mapping table, status updates round-trip to unexpected values.

The fix comes first: spend 1 to 2 weeks cleaning the asset master before you connect. Then write a mapping sheet that both teams sign off.

## Contractors and outside work, without ERP seats

Plants with a lot of outside work ask about this first. So here is where it really stands today.

**What works today.** You log outside work as a contractor project. Its jobs point at the same asset IDs your own PMs use. So a vendor's overhaul lands in the asset's timeline. It sits beside your team's work, not in an email.

When you close the job, WorkHive sends the completion back to SAP. That works once you connect SAP. It ends the retyping that makes contractor reports late. None of that requires giving anyone an ERP seat, which is the expensive part you were trying to avoid.

**What does not exist yet, stated plainly.** No contractor login is limited to its own work orders. No supplier view is limited to its own parts. A hive member sees the whole hive. Anyone you invite sees its assets and records.

The only higher role is supervisor. So if a vendor must not see the rest of your plant, do not invite them. Have your planner log the finished job against the asset. It takes a minute and keeps the line real.

Limited outside accounts are a fair thing to press any vendor on. This guide will describe WorkHive's when WorkHive has one.

## 90-day stable data, then connect

The most important rule: do not connect until WorkHive has run 90 days of clean Logbook use. The reason is that integration amplifies data quality, in both directions. Clean WorkHive data improves SAP. Messy WorkHive data corrupts SAP. The SAP team blames the link. The maintenance team blames the SAP team. Then the project gets cancelled.

The recommended sequence:

1. **Months 1 to 3:** WorkHive Logbook + PM Scheduler only. No integration. Validate data quality.
2. **Month 4:** Enable one-way push of work-order completion only. Monitor SAP register for 30 days.
3. **Month 5:** Add the scheduled pull of work orders from SAP. Load the asset master by CSV. Check the mapping for 30 days.
4. **Months 6 to 9:** tune the field map. Re-import assets and PMs by CSV when your master data changes.
5. **Months 10+:** Two-way sync where the value justifies the complexity.

**The bigger picture:** CMMS integration is not a technology project. It is a maintenance operations change wrapped in a technical layer. Plants that keep that order get stable links. Plants that treat it as an IT project ship a connector nobody uses. Build the floor habit in WorkHive first, then connect it to the systems of record. Never the other way around.

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

<!-- md-twin source-sha: 3162064708975fde -->
