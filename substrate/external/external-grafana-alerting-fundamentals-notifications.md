---
name: external-grafana-alerting-fundamentals-notifications
type: reference
source: https://grafana.com/docs/grafana/latest/alerting/fundamentals/
source_sha: d8e214fe1aae1c41
fetched_at: 2026-07-18T05:37:45Z
last_verified: 2026-07-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: grafana alerting fundamentals notifications
---

## reference · grafana alerting fundamentals notifications
* Grafana Alerting lets you define alert rules across multiple data sources and manage notifications with flexible routing.
* Alert rules consist of one or more queries and expressions that select the data you want to measure, and a condition that must be met or exceeded to fire an alert.
* Each alert rule can produce multiple alert instances, one per time series or dimension.
* Alert instances are sent for notifications when they fire or are resolved.
* Contact points determine the notification message and where notifications are sent, such as email, Slack, or incident management systems.
* Notification policies are an advanced option for handling alert notifications by distinct scopes, such as by team or service.
* Notification policies route alerts to contact points via label matching.
* Grafana Alerting groups related firing alerts into a single notification by default, but this behavior can be customized.
* Silences and mute timings allow you to pause notifications without interrupting alert rule evaluation.
* Use a silence to pause notifications on a one-time basis, such as during a maintenance window.
* Use mute timings to pause notifications at regular intervals, such as evenings and weekends.
Sources: https://grafana.com/docs/grafana/latest/alerting/fundamentals/
