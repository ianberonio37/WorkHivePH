---
name: change_external-ux-core-web-vitals-thresholds-learn_2026-10-31
type: source-change
chunk: external-ux-core-web-vitals-thresholds-learn
topic: ux core web vitals thresholds learn
source: https://web.dev/articles/vitals
detected: 2026-10-31
age_days: 108
ttl_days: 30
---

# external-ux-core-web-vitals-thresholds-learn changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-ux-core-web-vitals-thresholds-learn (before)
+++ external-ux-core-web-vitals-thresholds-learn (after)
@@ -1,19 +1,21 @@
-## reference · Core Web Vitals Thresholds
+## reference · ux core web vitals thresholds learn
+- **Core Web Vitals metrics and good‑experience thresholds**  
+  - Largest Contentful Paint (LCP): ≤ 2.5 seconds.  
+  - Interaction to Next Paint (INP): ≤ 200 ms.  
+  - Cumulative Layout Shift (CLS): ≤ 0.1.  
+- **Target percentile for compliance** – measure the **75th percentile** of page loads (separate for mobile and desktop). A page passes if all three metrics meet their thresholds at this percentile.  
+- **Metric lifecycle stages**  
+  - *Experimental*: metric is newly introduced, may change; community feedback is critical.  
+  - *Pending*: metric has passed experimental feedback, will be stable after ≥ 6 months.  
+  - *Stable*: metric is officially part of Core Web Vitals; definitions change ≤ once per year and are announced publicly.  
+- **Current lifecycle status (as of 2024)**  
+  - LCP – Stable.  
+  - INP – Stable (promoted from experimental/pending in 2024).  
+  - CLS – Stable.  
+- **Tooling guidance**  
+  - Use the **web‑vitals** JavaScript library (`onCLS`, `onINP`, `onLCP`) to collect field data that matches Google‑tool reporting.  
+  - Send metrics via `navigator.sendBeacon()` or `fetch()` to your analytics endpoint.  
+  - Complement field data with lab tools (Lighthouse, Chrome DevTools) for regression testing; note that INP cannot be measured in pure lab runs—use Total Blocking Time (TBT) as a proxy.  
+- **Reporting requirement** – for a site to be considered compliant, **all three Core Web Vitals must meet their thresholds at the 75th percentile** on both mobile and desktop.  
 
-* Core Web Vitals metrics:
-  * Largest Contentful Paint (LCP)
-  * Cumulative Layout Shift (CLS)
-  * Interaction to Next Paint (INP)
-* Thresholds for Core Web Vitals metrics:
-  * LCP: 2.5 seconds or less
-  * CLS: 0.1 or less
-  * INP: 200 milliseconds or less
-* Measuring Core Web Vitals:
-  * Use lab and field data to measure Core Web Vitals
-  * Google tools can help with Core Web Vitals workflows
-* Best practices:
-  * Optimize images to improve LCP
-  * Minimize layout shifts to improve CLS
-  * Optimize server response times to improve INP
-
-Sources: https://web.dev/explore/learn-core-web-vitals
+Sources: https://web.dev/articles/vitals
```

## Decision (2026-10-31)

No lever moves; thresholds re-confirmed (LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1 at the 75th percentile). The stored URL was web.dev's course index (/explore/learn-core-web-vitals), which has nothing to distill; the chunk now reads the thresholds article itself, https://web.dev/articles/vitals.
