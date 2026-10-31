---
name: change_external-ux-core-web-vitals-lcp-inp-cls_2026-10-31
type: source-change
chunk: external-ux-core-web-vitals-lcp-inp-cls
topic: ux core web vitals lcp inp cls
source: https://web.dev/articles/vitals
detected: 2026-10-31
age_days: 108
ttl_days: 30
---

# external-ux-core-web-vitals-lcp-inp-cls changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-ux-core-web-vitals-lcp-inp-cls (before)
+++ external-ux-core-web-vitals-lcp-inp-cls (after)
@@ -1,11 +1,12 @@
-## reference · Core Web Vitals (LCP, INP, CLS)
-* **Largest Contentful Paint (LCP)**: measures loading performance, target **2.5 seconds** or less.
-* **Interaction to Next Paint (INP)**: measures interactivity, target **200 milliseconds** or less.
-* **Cumulative Layout Shift (CLS)**: measures visual stability, target **0.1** or less.
-* To ensure good user experience, aim for 75th percentile of page loads to meet targets on both mobile and desktop devices.
-* Tools assessing Core Web Vitals compliance should consider a page passing if it meets recommended targets at 75th percentile for all three metrics.
-* Core Web Vitals metrics lifecycle stages: 
-  * **Experimental**: prospective metrics undergoing testing and feedback.
-  * **Pending**: future metrics with well-defined timeline to becoming stable.
-  * **Stable**: current set of essential metrics for great user experiences.
+## reference · ux core web vitals lcp inp cls
+- **Largest Contentful Paint (LCP)** – good experience when LCP ≤ 2.5 seconds from start of page load.  
+- **Interaction to Next Paint (INP)** – good experience when INP ≤ 200 ms.  
+- **Cumulative Layout Shift (CLS)** – good experience when CLS ≤ 0.1.  
+- **Target percentile** – evaluate the **75th percentile** of page loads (mobile + desktop) to determine compliance.  
+- **Pass criteria** – a page passes Core Web Vitals if all three metrics meet their recommended targets at the 75th percentile.  
+- **Lifecycle status (as of 2024)**:  
+  - LCP – **Stable**  
+  - CLS – **Stable**  
+  - INP – **Stable** (promoted from experimental → pending → stable, replacing FID).  
+- **Metric stability** – stable Core Web Vitals change no more than once per year; any change is announced in official docs and changelogs.  
 
```

## Decision (2026-10-31)

No lever moves; thresholds re-confirmed (LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1 at the 75th percentile), the values cwv_gate holds.
