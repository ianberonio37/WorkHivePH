---
name: external-ux-core-web-vitals-thresholds-learn
type: reference
source: https://web.dev/articles/vitals
source_sha: 0cc0f90da16993a1
fetched_at: 2026-10-30T17:27:08Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: ux core web vitals thresholds learn
---

## reference · ux core web vitals thresholds learn
- **Core Web Vitals metrics and good‑experience thresholds**  
  - Largest Contentful Paint (LCP): ≤ 2.5 seconds.  
  - Interaction to Next Paint (INP): ≤ 200 ms.  
  - Cumulative Layout Shift (CLS): ≤ 0.1.  
- **Target percentile for compliance** – measure the **75th percentile** of page loads (separate for mobile and desktop). A page passes if all three metrics meet their thresholds at this percentile.  
- **Metric lifecycle stages**  
  - *Experimental*: metric is newly introduced, may change; community feedback is critical.  
  - *Pending*: metric has passed experimental feedback, will be stable after ≥ 6 months.  
  - *Stable*: metric is officially part of Core Web Vitals; definitions change ≤ once per year and are announced publicly.  
- **Current lifecycle status (as of 2024)**  
  - LCP – Stable.  
  - INP – Stable (promoted from experimental/pending in 2024).  
  - CLS – Stable.  
- **Tooling guidance**  
  - Use the **web‑vitals** JavaScript library (`onCLS`, `onINP`, `onLCP`) to collect field data that matches Google‑tool reporting.  
  - Send metrics via `navigator.sendBeacon()` or `fetch()` to your analytics endpoint.  
  - Complement field data with lab tools (Lighthouse, Chrome DevTools) for regression testing; note that INP cannot be measured in pure lab runs—use Total Blocking Time (TBT) as a proxy.  
- **Reporting requirement** – for a site to be considered compliant, **all three Core Web Vitals must meet their thresholds at the 75th percentile** on both mobile and desktop.  

Sources: https://web.dev/articles/vitals
