# Sensor and CMMS gateway operations (for industrial plants)

> How to operate the edge gateway that bridges OT sensors (OPC-UA, MQTT) and your existing CMMS (SAP, Maximo) to WorkHive. Covers daily health checks, sensor inventory, cybersecurity boundaries, and the OT/IT operating model.

Source: https://workhiveph.com/learn/sensor-cmms-gateway-operations/

Plant Connections · OT/IT bridge

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 17 May 2026
·
8 min read

**Short answer:** The Plant Connections gateway is the operational layer that bridges your plant's OT network (PLCs, SCADA, IoT sensors via OPC-UA or MQTT) and your IT network (WorkHive, SAP, Maximo). Daily operations need three things: a 5-minute health check on the edge gateway, a current sensor inventory with health status, and a documented OT/IT cybersecurity boundary that the IT and reliability teams both signed off on. Plants that operate the gateway well get reliable Stage 3 PdM; plants that treat it as an install-and-forget device get silent data outages that show up as missing alerts.

Who this is for

- OT and automation engineers
- IT cybersecurity teams
- Plant managers overseeing PdM
- Reliability engineers consuming sensor data
- Integration consultants and SIs
- Sensor vendors and edge platform providers
- New OT/IT graduates joining plants

Operate the Plant Connections gateway daily, not install-and-forget. Three things keep it reliable: a 5-minute edge-gateway health check each shift, a current sensor inventory with health status, and an OT/IT cybersecurity boundary (built on ISA/IEC 62443) that IT and reliability both signed off. Skip the check and gateway problems surface 6 to 18 hours late, as missing alerts.

## What the Plant Connections gateway does

The edge gateway is a small server (physical or virtual) running on the plant network that:

- Reads sensor data from your OT systems via OPC-UA (for PLCs and SCADA) or MQTT (for IoT sensors)
- Reads work orders, asset master, and PM schedule from your CMMS (SAP PM, IBM Maximo, others) via REST or SOAP API
- Pushes condition summaries and operational data to WorkHive cloud over secure HTTPS
- Pushes WorkHive completion data back to the CMMS for finance and asset register sync

The gateway runs on-premise so sensitive plant data never leaves your network unencrypted. Only the condition-data summaries WorkHive needs are transmitted. This matters for Philippine plants with cybersecurity policies that restrict direct cloud access from the OT network.

## Daily 5-minute gateway health check

The OT engineer opens the Plant Connections console at start of shift and verifies five things:

1. **Gateway uptime.** Has the edge process been running continuously since last reboot? Restart events are logged.
2. **OPC-UA connection.** Are all subscribed nodes responding within their expected sample period?
3. **MQTT broker.** Are all subscribed topics receiving messages at the expected cadence?
4. **CMMS API connection.** Last successful sync timestamp; any failed sync attempts in the last 24 hours?
5. **WorkHive cloud push.** Last successful push timestamp; any backlogged messages waiting?

5 minutes per shift, end of story. Plants that skip this check find out about gateway problems when alerts stop firing, which is usually 6 to 18 hours late.

## Sensor inventory and health rotation

Every sensor in the plant goes in the Plant Connections sensor inventory with:

- Tag (OPC-UA node ID or MQTT topic)
- Asset link (which Asset Hub asset this sensor belongs to)
- Measurement type (vibration, temperature, pressure, etc.)
- Expected sample period and value range
- Last reading received timestamp
- Calibration due date
- Battery status (for wireless sensors)

The dashboard surfaces sensors that have not reported within the expected period (likely failed or batteries dying), sensors reporting outside expected range (likely miscalibrated or environmental change), and sensors due for calibration in the next 30 days. The OT engineer rotates through the action list weekly.

## OT/IT cybersecurity boundary

The gateway sits on the OT/IT boundary. Three rules that work in Philippine plants:

- **OT-initiated outbound only.** The gateway pushes to WorkHive cloud; WorkHive cloud does not push to the gateway. No inbound connection from the internet to the OT network.
- **TLS everywhere.** OPC-UA security mode SignAndEncrypt, MQTT over TLS, HTTPS to WorkHive. No plaintext on any leg.
- **Air-gap optionality.** Plants with strict policies can run the gateway in offline mode that batches data and uploads during scheduled windows from a DMZ host. Latency goes up; security goes up.

The IT cybersecurity team and the reliability team both sign off on the boundary architecture during commissioning. Annual review keeps it current as threats and standards evolve.

## OT/IT operating model that works

The most common failure pattern in Philippine plants is unclear ownership of the gateway. The reliability engineer thinks IT owns it because it talks to the cloud; IT thinks the OT team owns it because it sits on the OT network. After 3 months, nobody runs the daily health check and the gateway silently fails.

The model that works:

- **OT team owns operational health** of the gateway (daily check, restart procedures, sensor inventory updates)
- **IT cybersecurity team owns the boundary** (firewall rules, TLS certificates, audit log review)
- **Reliability engineer owns the data quality** (are sensors calibrated, are thresholds tuned, are alerts being acted on)
- **Plant manager owns the cross-team coordination** via a monthly 30-minute review with all three

The tool this guide is about

#### WorkHive Plant Connections is the OT/IT operations console

Daily health dashboard for the edge gateway, current sensor inventory with status, OPC-UA and MQTT subscription management, CMMS sync log, secure outbound-only architecture. Supervisor-only access by default; OT and IT teams get scoped views. Free at the worker tier; multi-site gateway fleet management unlocks at Stage 4.

No hive yet? [Join WorkHive](https://workhiveph.com/#join) first (free, takes 30 seconds).

## Frequently asked questions

### What is the Plant Connections gateway?

A small server (physical or virtual) running on the plant network that bridges OT (PLCs, SCADA via OPC-UA; IoT sensors via MQTT) and IT (CMMS via API; WorkHive cloud via HTTPS). It runs on-premise so sensitive plant data never leaves the plant unencrypted; only condition summaries get pushed to WorkHive cloud. This matters for plants with cybersecurity policies that restrict direct OT-to-cloud access.

### How often should I check gateway health?

Daily, 5 minutes, at start of shift. Verify gateway uptime, OPC-UA connection, MQTT broker, CMMS API sync, and WorkHive cloud push. Plants that skip this check find out about problems when alerts stop firing, typically 6 to 18 hours late. Daily check catches the same problems within 8 hours.

### Who owns the gateway in the plant organisation?

Split ownership that works: OT team owns operational health (daily check, restarts, sensor inventory), IT cybersecurity owns the boundary (firewall, TLS, audit log), reliability engineer owns data quality (calibration, threshold tuning, alert acting), plant manager owns cross-team coordination via monthly 30-min review. Single-owner models (all to OT or all to IT) tend to fail because the skills do not overlap.

### What are the cybersecurity rules for the gateway?

Three rules: (1) OT-initiated outbound only (no inbound from internet to OT network); (2) TLS everywhere (OPC-UA SignAndEncrypt, MQTT over TLS, HTTPS to WorkHive); (3) air-gap optionality for strict-policy plants (batched upload from DMZ host during scheduled windows). IT cybersecurity and reliability teams both sign off during commissioning and review annually.

### What sensors and protocols are supported?

OPC-UA for traditional industrial automation (Siemens, Rockwell, Schneider PLCs and SCADA). MQTT for newer IoT sensors (wireless vibration, temperature, ultrasonic, energy meters). Edge gateway runtime options include AVEVA Edge, Ignition Edge, and Node-RED depending on stack preference. REST/SOAP for CMMS systems (SAP PM OData, IBM Maximo MIF, Hippo, Fiix, others). Custom integrations via the generic REST connector.

### What happens when the gateway loses internet?

The gateway continues reading sensor and CMMS data locally and buffers it. Buffer size depends on disk space (typically 7 to 30 days). When internet is restored, the gateway pushes the backlog to WorkHive cloud in time order; the cloud accepts the late timestamps. This matters for plants with intermittent Globe/Smart/PLDT connectivity at remote sites.

## Sources

- OPC Foundation, **OPC Unified Architecture Specification**, Parts 1 through 14.
- OASIS, **MQTT Version 5.0** specification.
- ISA / IEC 62443, **Industrial Automation and Control Systems Security**. Reference for OT cybersecurity architecture.
- WorkHive platform positioning, "Four Gaps One Hive" with Plant Connections as the Stage 3 OT/IT bridge. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [CMMS Integration](https://workhiveph.com/learn/connecting-workhive-to-sap-maximo-cmms/) · [Predictive on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 26f67bc698204a9b -->
