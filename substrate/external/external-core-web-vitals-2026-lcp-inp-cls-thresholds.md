---
name: external-core-web-vitals-2026-lcp-inp-cls-thresholds
type: reference
source: https://www.digivate.com/blog/seo/core-web-vitals-in-2026/
source_sha: 696487bedaac5de6
fetched_at: 2026-07-18T22:42:29Z
last_verified: 2026-07-19
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Core Web Vitals 2026 LCP INP CLS thresholds
---

## reference · Core Web Vitals 2026 LCP INP CLS thresholds
* Core Web Vitals (CWV) include three metrics: LCP (loading performance), INP (responsiveness), and CLS (visual stability).
* CWV metrics are measured on a sliding scale at the 75th percentile of real user data.
* LCP measures loading performance, with a good score being under 2.5 seconds.
* INP measures responsiveness, with a good score being under 200 ms.
* CLS measures visual stability, with a good score being under 0.1.
* Sites fail INP because it measures every click, tap, and keypress during the entire session, not just the initial load.
* Lighthouse can't replicate INP reliably, so use Chrome User Experience (CrUX) data as the primary source of truth for INP.
* LCP is not just a large image problem, but a sequence of dependencies, including server response time, asset download time, and browser rendering time.
* Common culprits for LCP issues include unoptimized database queries, absent edge caching, and synchronous JavaScript or non-critical CSS loaded on the initial view.
* To diagnose LCP issues, use the Network Tab in Chrome DevTools and check the Timing sub-tab for server response time.
* To fix LCP issues, add fetchpriority="high" to the LCP image tag, and use a stale-while-revalidate caching strategy or improved CDN compute at the edge.
* INP issues are often caused by long-running JavaScript tasks that block the browser from responding.
* To diagnose INP issues, use the Rendering tab in Chrome DevTools to visualize shifting elements, and look for red-flagged Long Tasks in the main thread track.
* CLS issues are often caused by late-loading dynamic elements, such as cookie consent banners, unreserved ad slots, and web fonts that cause significant text reflow.
* To diagnose CLS issues, use the Layout Shift Regions flag in Chrome DevTools to visually highlight elements that move during the load cycle.
* Google reads CrUX data at the 75th percentile, so a site's score is not its average, but its slowest quarter.
* The Lab vs. Field Gap: Lighthouse is a controlled experiment, while CrUX data reflects real-world conditions.
* When deploying technical fixes, expect incremental movement in Search Console within the first week, but it takes the full 28 days for the old, failing data points to drop out of the sample entirely.
Sources: https://www.digivate.com/blog/seo/core-web-vitals-in-2026/
