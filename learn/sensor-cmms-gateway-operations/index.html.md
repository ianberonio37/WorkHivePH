# Sensor and CMMS gateway operations (for industrial plants)

> How to run the edge gateway that sends OT sensor readings (OPC-UA, MQTT) to WorkHive, beside its cloud link to your CMMS (SAP, Maximo). Covers daily health checks, sensor inventory, cybersecurity boundaries, and the OT/IT operating model.

Source: https://workhiveph.com/learn/sensor-cmms-gateway-operations/

Plant Connections · OT/IT bridge

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 13 Nov 2026
·
8 min read

**Short answer:** An edge gateway links your plant's OT network to WorkHive. It reads PLCs and sensors over OPC-UA or MQTT. It sends the readings over HTTPS. Check its health for 5 minutes each shift, and keep the sensor list current. Skip the check, and a dead gateway can go unseen for a whole 8-hour shift.

Who this is for

- OT and automation engineers
- IT cybersecurity teams
- Plant managers overseeing PdM
- Reliability engineers consuming sensor data
- Integration consultants and SIs
- Sensor vendors and edge platform providers
- New OT/IT graduates joining plants

Run the Plant Connections gateway every day; it is not install-and-forget. Three habits keep it healthy. Check it for 5 minutes each shift. Keep a current sensor list. And agree an OT/IT security boundary, built on ISA/IEC 62443. IT and reliability both sign it.

## What the Plant Connections gateway does

The gateway is your own small server, physical or virtual, on the plant network. WorkHive does not supply the box. You run an edge runtime on it, such as Ignition Edge, AVEVA Edge or Node-RED. For MQTT sensors, WorkHive also gives you a subscriber template to run there.

The gateway does two jobs:

- It reads your PLCs and SCADA over OPC-UA, or your IoT sensors over MQTT.
- It sends the readings to WorkHive over HTTPS. The connection always starts from the plant side.

WorkHive's topic map ties each topic to an asset and a parameter. It holds the unit and scale too. So each reading lands on the right machine.

The CMMS link is separate, and it runs in WorkHive's cloud, not on the gateway. Its connectors reach SAP PM over OData, and Maximo over OSLC. Any other CMMS can link through a REST API. They pull work orders in, and can push completions back. CMMS means computerized maintenance management system.

## Daily 5-minute gateway health check

At the start of each shift, the OT engineer checks two places. First, the gateway host itself:

- **Uptime.** Has the edge process run without a restart since the last check?
- **OPC-UA.** Are all subscribed tags answering on time?
- **MQTT.** Are all topics getting messages at the expected rate?
- **Backlog.** Is anything queued, waiting to send?

Then the Plant Connections page in WorkHive:

- **Gateway audit.** What reached WorkHive in the last 7 days.
- **External sync activity.** The CMMS syncs of the last 30 days, and any that failed.
- **Sensor topic map.** Check that every topic you expect is there and switched on.

Five minutes a shift is enough. Plants that skip it learn of a fault only when the alerts stop. That is often a shift or more later.

## Sensor inventory and health rotation

The topic map in WorkHive holds the basics for each sensor. That is its topic, its asset, the parameter, the unit and the scale. You can switch a mapping off without deleting it.

Keep the rest in your own sensor list:

- the expected sample period and value range
- the calibration due date
- the battery status, for wireless sensors

Put each calibration on the PM Scheduler as its own PM, so it comes due on a date. Then review the list weekly. Look for sensors that went quiet or read out of range. And check which calibrations fall due soon.

## OT/IT cybersecurity boundary

The gateway sits where the plant network meets the office network and the internet. Three rules keep that line safe:

- **Outbound only.** The gateway starts every connection to WorkHive. WorkHive never connects in to it. Nothing from the internet reaches the OT network.
- **Encrypt every leg.** Use OPC-UA's SignAndEncrypt mode, MQTT over TLS and HTTPS to WorkHive. Send nothing in plain text.
- **Batch it, if policy demands.** A strict plant can keep the gateway offline. A host in the DMZ, the buffer network between plant and office, then uploads the stored readings at set times. WorkHive takes up to 200 readings per request, up to 365 days old. You trade speed for safety.

Write the boundary down at commissioning. The IT security team and the reliability team both sign it. Review it once a year, as threats and standards change.

## OT/IT operating model that works

A common failure is that no one owns the gateway. The reliability engineer thinks IT owns it, because it talks to the cloud. IT thinks the OT team owns it, because it sits on the OT network. Within months, nobody runs the daily check. Then the gateway fails, and no one hears it.

Split the ownership four ways:

- **The OT team owns the gateway's health:** the daily check, restarts and sensor list updates.
- **IT security owns the boundary:** the firewall, TLS and audit logs.
- **The reliability engineer owns the data.** Are sensors calibrated and limits tuned? Does someone act on alerts?
- **The plant manager links the three:** a 30-minute review each month with all of them.

The tool this guide is about

### WorkHive Plant Connections is the OT/IT operations console

The console holds the sensor topic map. Each MQTT topic or OPC-UA tag maps to an asset and parameter. It shows the gateway audit for the last 7 days, and sync activity for the last 30.

It also lists your CMMS links and shows SSO status. And you set a data-retention policy there.

Know who can see it before you plan around it. The page is for supervisors only, with no separate OT and IT views. There is no view across several sites either. A group runs one gateway and one hive per plant, and checks each in turn.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Frequently asked questions

### What is the Plant Connections gateway?

Your own small server on the plant network, running an edge runtime such as Ignition Edge, AVEVA Edge or Node-RED. It reads PLCs and SCADA over OPC-UA, or sensors over MQTT, and sends readings to WorkHive over HTTPS. WorkHive's CMMS connectors run separately, in its cloud.

### How often should I check gateway health?

Daily, 5 minutes, at the start of shift. Check the gateway host for uptime, OPC-UA, MQTT and any backlog. Then check Plant Connections for the gateway audit and the sync activity. Plants that skip this find out when alerts stop, often a shift or more later.

### Who owns the gateway in the plant organisation?

Split it four ways. The OT team owns the gateway's health: the daily check, restarts and the sensor list. IT security owns the boundary: firewall, TLS and the audit log. The reliability engineer owns data quality: calibration, limits and acting on alerts. The plant manager runs a 30-minute review each month. One owner alone tends to fail, because the skills do not overlap.

### What are the cybersecurity rules for the gateway?

Three rules. The gateway connects out only, so nothing from the internet reaches the OT network. Every leg is encrypted: OPC-UA SignAndEncrypt, MQTT over TLS and HTTPS to WorkHive. A strict plant can stay offline and upload batches from a DMZ host at set times. IT security and reliability both sign the design, and review it each year.

### Which sensors and protocols does it support?

OPC-UA reads PLCs and SCADA from makers such as Siemens, Rockwell and Schneider. MQTT carries newer IoT sensors: wireless vibration, temperature, ultrasonic and energy meters. Your edge runtime might be AVEVA Edge, Ignition Edge or Node-RED. For the CMMS, WorkHive has three paths: SAP OData, Maximo OSLC and a generic REST connector. Any other CMMS goes through the generic one, so budget time for it.

### What happens when the gateway loses internet?

That depends on your edge runtime. Most can store and forward: they keep readings on disk and send the backlog when the link returns. WorkHive accepts late readings up to 365 days old, up to 200 per request, with their own timestamps. That matters at remote sites with patchy Globe, Smart or PLDT links. The CMMS sync never passes through the gateway; WorkHive's connectors run it.

## Sources

- OPC Foundation, **OPC Unified Architecture Specification**, Parts 1 through 14.
- OASIS, **MQTT Version 5.0** specification.
- ISA / IEC 62443, **Industrial Automation and Control Systems Security**. Reference for OT cybersecurity architecture.
- WorkHive platform positioning, "Four gaps. One hive." Plant Connections and the sensor ingest (HTTPS, up to 200 readings per request, up to 365 days old) as read from the product on 11 Nov 2026. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [CMMS Integration](https://workhiveph.com/learn/connecting-workhive-to-sap-maximo-cmms/) · [Predictive on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 6a64ff1f9f2a6093 -->
