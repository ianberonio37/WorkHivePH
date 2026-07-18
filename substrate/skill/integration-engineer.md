---
name: skill-integration-engineer
type: skill
source: skill:integration-engineer
source_sha: 8c5a1d7c6680ffe3
last_verified: 2026-07-13
supersedes: null
---
## skill · integration-engineer

SAP PM, IBM Maximo, CMMS/ERP connectors, OPC-UA/MQTT IoT protocols, REST/webhook framework, SSO/SAML, and data import from legacy systems. Triggers on "integration", "SAP", "Maximo", "CMMS", "ERP", "O

**Sections:** Integration Engineer Agent · Your Responsibilities · How to Operate · This Platform's Integration Context · SAP PM Integration Pattern · MQTT Pattern (IoT Sensor Data) · SSO/SAML Pattern · Webhook Framework (Custom Integrations) · Data Import Tool (Legacy Migration) · Output Format · An inbound INGEST endpoint must authenticate its CALLER — a machine has no auth_uid, so membership-check is the wrong control (2026-06-15, Gateway Pillar I) · The config_id / hive_id CONFUSION BOLA — verifying membership on `body.hive_id` is worthless if the operation targets a different key (CMMS Integrations PDDA, 2026-07-10) · HMAC webhooks: a SIGNED timestamp is NOT replay protection until you CHECK its freshness (2026-07-10) · A CMMS import that writes `logbook` MUST supply `logbook.id` — and a swallowed insert error hides the silent-drop (2026-07-10) · Push the CMMS's OWN status code, implement EVERY webhook event the contract promises, and mark a failed push durably (CMMS Integrations PDDA drive-to-100%, 2026-07-10)

(Deep source: `skill:integration-engineer` — retrieve this TOC to know WHICH section to read.)
