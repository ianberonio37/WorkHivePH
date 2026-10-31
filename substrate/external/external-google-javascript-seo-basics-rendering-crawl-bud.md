---
name: external-google-javascript-seo-basics-rendering-crawl-bud
type: reference
source: https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
source_sha: 62075892c7b1f310
fetched_at: 2026-10-30T17:15:53Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Google JavaScript SEO basics rendering crawl budget dynamic content
---

## reference · Google JavaScript SEO rendering crawl budget dynamic content

*   **Processing Pipeline**: Google processes JavaScript in three phases: Crawling (HTTP fetch), Rendering (headless Chromium execution), and Indexing.
*   **Rendering Queue**: All pages with a `200` HTTP status code are queued for rendering, regardless of JavaScript presence. Non-`200` statuses (e.g., `404`) may skip rendering.
*   **Crawl Budget & Latency**: Rendering is resource-intensive; pages may wait in the render queue for seconds to minutes. Server-side rendering (SSR) or pre-rendering is recommended to reduce latency and ensure content is visible to non-JS bots.
*   **Link Discovery**:
    *   Googlebot parses `href` attributes in raw HTML for initial link discovery.
    *   Links injected via JavaScript are discovered only after rendering.
    *   Use `rel="nofollow"` to prevent link discovery.
    *   **Do not** use URL fragments (`#/path`) for routing; Googlebot cannot reliably resolve these. Use the **History API** (`pushState`) for client-side routing to ensure URLs are crawlable.
*   **Soft 404s in SPAs**: Client-side routing often prevents meaningful HTTP status codes. To avoid soft 404 errors:
    *   Redirect to a server-side `404` URL (e.g., `/not-found`) via JavaScript if content is missing.
    *   Inject `<meta name="robots" content="noindex">` via JavaScript for error states.
*   **Canonical URLs**:
    *   Prefer setting `rel="canonical"` in original HTML.
    *   If using JavaScript, ensure it sets the **same** URL as the original HTML or is the **only** canonical tag on the page. Multiple or conflicting canonical tags cause unexpected indexing results.
*   **Robots Meta Tags**:
    *   If a `noindex` tag is present in the initial HTML, Google may skip rendering/JS execution entirely.
    *   **Do not** rely on JavaScript to remove a `noindex` tag from the initial HTML; it may not execute. If indexing is required, omit `noindex` from the initial HTML.
*   **Caching & Resource Fingerprinting**:
    *   Googlebot caches aggressively and may ignore standard cache headers.
    *   Use **content fingerprinting** (e.g., `main.2bb85551.js`) in filenames to ensure Googlebot fetches updated JS/CSS resources.
*   **Web Components**: Google flattens Shadow DOM and Light DOM during rendering. Only content visible in the rendered HTML is indexed. Verify visibility using the URL Inspection Tool or Rich Results Test.
*   **Compatibility**: Use an evergreen Chromium version for testing. Use polyfills for missing browser APIs, but note that some features cannot be polyfilled.

Sources: https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
