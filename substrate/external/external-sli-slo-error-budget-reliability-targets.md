---
name: external-sli-slo-error-budget-reliability-targets
type: reference
source: https://cloud.google.com/blog/products/devops-sre/sre-fundamentals-slis-slas-and-slos
source_sha: 1de453704c32b61e
fetched_at: 2026-07-29T06:19:30Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: SLI SLO error budget reliability targets
---

## reference · SLI SLO error budget reliability targets
* Define a precise numerical target for system availability, known as the Service-Level Objective (SLO).
* The SLO should be the lowest level of reliability that can be tolerated for each service.
* Every service should have an availability SLO to make principled judgments about reliability.
* Excessive availability can become a problem, so avoid making a system overly reliable if it's not intended to be.
* Implement periodic downtime in some services to prevent over-availability.
* Distinguish between SLO and Service-Level Agreement (SLA), where SLA involves a promise to meet a certain availability level and may include penalties for non-compliance.
* The availability SLO in an SLA is normally looser than the internal availability SLO.
* Use Service-Level Indicators (SLIs) as direct measurements of a service's behavior, such as successful probe frequencies.
* SLIs are used to evaluate if a system is running within SLO and to identify potential problems.
* Measure SLI compliance explicitly and prioritize traffic based on SLA obligations.
* Be careful when defining SLA availability SLO to ensure only legitimate queries are counted.
* Use tools like Stackdriver to incorporate SLIs into workflows and monitor service availability.
Sources: https://cloud.google.com/blog/products/devops-sre/sre-fundamentals-slis-slas-and-slos
