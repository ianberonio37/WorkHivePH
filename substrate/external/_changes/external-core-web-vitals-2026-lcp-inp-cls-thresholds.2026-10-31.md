---
name: change_external-core-web-vitals-2026-lcp-inp-cls-thresholds_2026-10-31
type: source-change
chunk: external-core-web-vitals-2026-lcp-inp-cls-thresholds
topic: Core Web Vitals 2026 LCP INP CLS thresholds
source: https://www.digivate.com/blog/seo/core-web-vitals-in-2026/
detected: 2026-10-31
age_days: 103
ttl_days: 30
---

# external-core-web-vitals-2026-lcp-inp-cls-thresholds changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-core-web-vitals-2026-lcp-inp-cls-thresholds (before)
+++ external-core-web-vitals-2026-lcp-inp-cls-thresholds (after)
@@ -1,20 +1,46 @@
 ## reference · Core Web Vitals 2026 LCP INP CLS thresholds
-* Core Web Vitals (CWV) include three metrics: LCP (loading performance), INP (responsiveness), and CLS (visual stability).
-* CWV metrics are measured on a sliding scale at the 75th percentile of real user data.
-* LCP measures loading performance, with a good score being under 2.5 seconds.
-* INP measures responsiveness, with a good score being under 200 ms.
-* CLS measures visual stability, with a good score being under 0.1.
-* Sites fail INP because it measures every click, tap, and keypress during the entire session, not just the initial load.
-* Lighthouse can't replicate INP reliably, so use Chrome User Experience (CrUX) data as the primary source of truth for INP.
-* LCP is not just a large image problem, but a sequence of dependencies, including server response time, asset download time, and browser rendering time.
-* Common culprits for LCP issues include unoptimized database queries, absent edge caching, and synchronous JavaScript or non-critical CSS loaded on the initial view.
-* To diagnose LCP issues, use the Network Tab in Chrome DevTools and check the Timing sub-tab for server response time.
-* To fix LCP issues, add fetchpriority="high" to the LCP image tag, and use a stale-while-revalidate caching strategy or improved CDN compute at the edge.
-* INP issues are often caused by long-running JavaScript tasks that block the browser from responding.
-* To diagnose INP issues, use the Rendering tab in Chrome DevTools to visualize shifting elements, and look for red-flagged Long Tasks in the main thread track.
-* CLS issues are often caused by late-loading dynamic elements, such as cookie consent banners, unreserved ad slots, and web fonts that cause significant text reflow.
-* To diagnose CLS issues, use the Layout Shift Regions flag in Chrome DevTools to visually highlight elements that move during the load cycle.
-* Google reads CrUX data at the 75th percentile, so a site's score is not its average, but its slowest quarter.
-* The Lab vs. Field Gap: Lighthouse is a controlled experiment, while CrUX data reflects real-world conditions.
-* When deploying technical fixes, expect incremental movement in Search Console within the first week, but it takes the full 28 days for the old, failing data points to drop out of the sample entirely.
+
+- **CWV are still ranking factors** in 2026; they act as a “tie‑breaker” and prerequisite within Google’s Page Experience signal.  
+- **CWV thresholds (75th percentile of real‑user data):**  
+  - LCP ≤ 2.5 s (good)  
+  - INP ≤ 200 ms (good)  
+  - CLS ≤ 0.1 (good)  
+- **INP replaced FID in March 2024**; it measures *every* user interaction during a session, not just the first.  
+- **LCP failures are not only image problems**; common causes:  
+  1. **TTFB > 200 ms** – indicates server or CDN latency.  
+  2. **Resource load delay** – LCP element not discoverable early; fix with `fetchpriority="high"` and `<link rel="preload">`.  
+  3. **Render blocking** – synchronous JS or non‑critical CSS blocking paint; inline critical CSS and defer non‑essential JS.  
+  4. **Lazy‑loading hero image** – remove `loading="lazy"` from LCP candidate.  
+- **LCP optimization checklist:**  
+  - Preload LCP image with `<link rel="preload" as="image">`.  
+  - Add `fetchpriority="high"` to the image tag.  
+  - Serve modern formats (AVIF, WebP).  
+  - Ensure TTFB < 200 ms via edge caching or database query optimization.  
+  - Inline critical CSS; defer or async non‑critical JS.  
+- **INP optimization checklist:**  
+  - Use CrUX or Search Console field data as primary source; Lighthouse cannot fully replicate INP.  
+  - Identify long tasks in DevTools Performance panel; reduce main‑thread blocking.  
+  - Avoid heavy third‑party scripts; lazy‑load or defer them.  
+  - For CSR frameworks, compare FCP vs TTI; large gaps indicate hydration delays.  
+- **CLS optimization checklist:**  
+  - Reserve space for dynamic elements (ads, banners, images) with width/height or CSS aspect‑ratio.  
+  - Avoid late‑loading fonts that cause FOUT; use `font-display: swap`.  
+  - Prevent layout shifts from cookie banners or ad slots by injecting them above the fold with reserved space.  
+  - Enable “Layout Shift Regions” in DevTools to visualize shifting elements.  
+- **CMS‑heavy sites (WordPress with Elementor/Divi)**:  
+  - DOM size > 800 nodes triggers warning; > 1,400 nodes is error.  
+  - Excessive DOM depth increases main‑thread load and INP.  
+- **Ad‑heavy news sites**:  
+  - Third‑party ad scripts often block main thread for 200–500 ms.  
+  - Use Network tab to filter JS by “Total Time” and Performance panel to identify offenders.  
+- **CSR frameworks (React, Vue, Angular)**:  
+  - Large gap between FCP and TTI signals hydration delays affecting INP.  
+  - Measure with Performance panel; compare field CrUX INP for confirmation.  
+- **Conversion impact:**  
+  - 1 s mobile load delay can reduce conversions by up to 20 %.  
+  - Vodafone Italy: 8 % sales lift, 15 % lead‑to‑visit improvement, 11 % cart‑to‑visit lift after CWV improvements.  
+- **Measurement:**  
+  - Lighthouse shows potential performance; CrUX shows real‑user data.  
+  - Use CrUX data from Search Console or PageSpeed Insights field tab for accurate INP, LCP, CLS metrics.  
+
 Sources: https://www.digivate.com/blog/seo/core-web-vitals-in-2026/
```

## Decision (2026-10-31)

No lever moves. Thresholds re-confirmed - LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1 at the 75th percentile - exactly what MAXIMIZATION_ROADMAP line 111 and cwv_gate hold. Its LCP causes (render-blocking CSS, lazy-loaded hero) restate the open cold-LCP lever (Tailwind CDN, lines 36/62/159), which stays open.
