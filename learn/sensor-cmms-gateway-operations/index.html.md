# Sensor and CMMS gateway operations (for industrial plants)

> How to operate the edge gateway that bridges OT sensors (OPC-UA, MQTT) and your existing CMMS (SAP, Maximo) to WorkHive. Covers daily health checks, sensor inventory, cybersecurity boundaries, and the OT/IT operating model.

Source: https://workhiveph.com/learn/sensor-cmms-gateway-operations/

Plant Connections · OT/IT bridge

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 11 Nov 2026
·
8 min read

**Short answer:** The Plant Connections gateway links two networks. One is your plant's OT network: PLCs, SCADA, and IoT sensors over OPC-UA or MQTT. The other is your IT network: WorkHive, SAP and Maximo. Daily operations need three things. The first is a 5-minute health check on the edge gateway. The second is a current sensor list with each one's health. The third is a written OT/IT security boundary. The IT and reliability teams must both sign it off. Plants that run the gateway well get reliable Stage 3 PdM. Plants that install it and forget it get silent data gaps. Those show up as missing alerts. The daily five-minute health check is the whole discipline. Skip it, and gateway problems show up 6 to 18 hours late, as missing alerts.

Who this is for

- OT and automation engineers
- IT cybersecurity teams
- Plant managers overseeing PdM
- Reliability engineers consuming sensor data
- Integration consultants and SIs
- Sensor vendors and edge platform providers
- New OT/IT graduates joining plants

Operate the Plant Connections gateway daily, not install-and-forget. Three things keep it reliable. Run a 5-minute edge-gateway health check every day. Keep a current sensor list with each one's health. And set an OT/IT security boundary. Build it on ISA/IEC 62443, and have IT and reliability both sign it off. Skip the check and gateway problems surface 6 to 18 hours late, as missing alerts.

## What the Plant Connections gateway does

The edge gateway is a small server, physical or virtual, on the plant network. It:

- Reads sensor data from your OT systems via OPC-UA (for PLCs and SCADA) or MQTT (for IoT sensors)
- Pulls work orders from your CMMS (computerized maintenance management system). That covers SAP PM, IBM Maximo and other REST APIs
- Sends condition summaries and running data to the WorkHive cloud. It uses secure HTTPS
- Sends WorkHive completion data back to the CMMS. That keeps finance and the asset register in step

The gateway runs on site. Sensitive plant data never leaves your network unencrypted. It sends only the condition-data summaries WorkHive needs. This matters for Philippine plants with strict security rules. Some limit direct cloud access from the OT network.

## Daily 5-minute gateway health check

At the start of shift, the OT engineer opens the Plant Connections console. They check five things:

1. **Gateway uptime.** Has the edge process been running continuously since last reboot? The log records each restart.
2. **OPC-UA connection.** Are all subscribed nodes responding within their expected sample period?
3. **MQTT broker.** Are all subscribed topics receiving messages at the expected cadence?
4. **CMMS API connection.** Last successful sync timestamp; any failed sync attempts in the last 24 hours?
5. **WorkHive cloud push.** Last successful push timestamp; any backlogged messages waiting?

5 minutes per shift, end of story. Plants that skip this check learn of gateway problems when alerts stop. That is usually 6 to 18 hours late.

## Sensor inventory and health rotation

Every sensor in the plant goes in the Plant Connections sensor list, with:

- Tag (OPC-UA node ID or MQTT topic)
- Asset link (which Asset Hub asset this sensor belongs to)
- Measurement type (vibration, temperature, pressure, etc.)
- Expected sample period and value range
- Last reading received timestamp
- Calibration due date
- Battery status (for wireless sensors)

The dashboard shows three kinds of sensor. Some have not reported in the expected time; they likely failed, or their batteries are dying. Some report outside the expected range. They are likely off calibration, or the setting changed. And some are due for calibration in the next 30 days. The OT engineer rotates through the action list weekly.

## OT/IT cybersecurity boundary

The gateway sits on the OT/IT boundary. Three rules that work in Philippine plants:

- **OT-initiated outbound only.** The gateway pushes to WorkHive cloud; WorkHive cloud does not push to the gateway. No inbound connection from the internet to the OT network.
- **TLS everywhere.** OPC-UA security mode SignAndEncrypt, MQTT over TLS, HTTPS to WorkHive. No plaintext on any leg.
- **Air-gap optionality.** Plants with strict policies can run the gateway offline. It batches data and uploads it from a DMZ host at set times. Latency goes up; security goes up.

Both teams sign off the boundary design during commissioning. That means the IT security team and the reliability team. Annual review keeps it current as threats and standards evolve.

## OT/IT operating model that works

In Philippine plants, the most common failure is that no one clearly owns the gateway. The reliability engineer thinks IT owns it, because it talks to the cloud. IT thinks the OT team owns it, because it sits on the OT network. After 3 months, nobody runs the daily health check. Then the gateway fails without a sound.

The model that works:

- **OT team owns operational health** of the gateway. That is the daily check, restarts, and sensor list updates
- **IT cybersecurity team owns the boundary**. That covers firewall rules, TLS certificates and audit log review
- **Reliability engineer owns the data quality**. Are sensors calibrated? Are thresholds tuned? Does someone act on the alerts?
- **Plant manager owns the cross-team coordination**. They hold a 30-minute review each month with all three

The tool this guide is about

### WorkHive Plant Connections is the OT/IT operations console

The console carries a sensor topic map. It lists the MQTT topics and OPC-UA tags your gateway publishes. Each one points to a parameter. The console also shows a gateway audit for the last 7 days. It shows external sync activity for the last 30. You get the CMMS integration list too. You can set a data-retention policy. And there is an SSO status card. Note who can see it before you plan around it. The page is supervisor-only. There are no separate OT and IT logins with different views. Whoever holds the supervisor account sees the gateway. Free at the worker tier. There is no view across several sites' gateways. A group with several plants runs a gateway and a hive per plant. It watches them one at a time.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Frequently asked questions

### What is the Plant Connections gateway?

A small server (physical or virtual) running on the plant network that bridges OT (PLCs, SCADA via OPC-UA; IoT sensors via MQTT) and IT (CMMS via API; WorkHive cloud via HTTPS). It runs on-premise so sensitive plant data never leaves the plant unencrypted; only condition summaries get pushed to WorkHive cloud. This matters for plants with cybersecurity policies that restrict direct OT-to-cloud access.

### How often should I check gateway health?

Daily, 5 minutes, at start of shift. Verify gateway uptime, OPC-UA connection, MQTT broker, CMMS API sync, and WorkHive cloud push. Plants that skip this check find out about problems when alerts stop firing, typically 6 to 18 hours late. Daily check catches the same problems within 8 hours.

### Who owns the gateway in the plant organisation?

Split ownership that works: OT team owns operational health (daily check, restarts, sensor inventory), IT cybersecurity owns the boundary (firewall, TLS, audit log), reliability engineer owns data quality (calibration, threshold tuning, alert acting), plant manager owns cross-team coordination via monthly 30-min review. Single-owner models (all to OT or all to IT) tend to fail because the skills do not overlap.

### What are the cybersecurity rules for the gateway?

Three rules: (1) OT-initiated outbound only (no inbound from internet to OT network); (2) TLS everywhere (OPC-UA SignAndEncrypt, MQTT over TLS, HTTPS to WorkHive); (3) air-gap optionality for strict-policy plants (batched upload from DMZ host during scheduled windows). IT cybersecurity and reliability teams both sign off during commissioning and review annually.

### Which sensors and protocols does it support?

OPC-UA for traditional industrial automation (Siemens, Rockwell, Schneider PLCs and SCADA). MQTT for newer IoT sensors (wireless vibration, temperature, ultrasonic, energy meters). Edge gateway runtime options include AVEVA Edge, Ignition Edge, and Node-RED depending on stack preference. For the CMMS side there are exactly three configured paths: SAP OData, Maximo OSLC, and a generic REST connector for anything else. A CMMS not on that list is reached through the generic connector rather than a purpose-built one, so budget integration time accordingly.

### What happens when the gateway loses internet?

The gateway continues reading sensor and CMMS data locally and buffers it. Buffer size depends on disk space (typically 7 to 30 days). When internet is restored, the gateway pushes the backlog to WorkHive cloud in time order; the cloud accepts the late timestamps. This matters for plants with intermittent Globe/Smart/PLDT connectivity at remote sites.

## Sources

- OPC Foundation, **OPC Unified Architecture Specification**, Parts 1 through 14.
- OASIS, **MQTT Version 5.0** specification.
- ISA / IEC 62443, **Industrial Automation and Control Systems Security**. Reference for OT cybersecurity architecture.
- WorkHive platform positioning, "Four Gaps One Hive" with Plant Connections as the Stage 3 OT/IT bridge. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [CMMS Integration](https://workhiveph.com/learn/connecting-workhive-to-sap-maximo-cmms/) · [Predictive on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 8b5ae47d0faf1f48 -->
