---
name: change_external-google-javascript-seo-basics-rendering-crawl-bud_2026-10-31
type: source-change
chunk: external-google-javascript-seo-basics-rendering-crawl-bud
topic: Google JavaScript SEO basics rendering crawl budget dynamic content
source: https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-google-javascript-seo-basics-rendering-crawl-bud changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-google-javascript-seo-basics-rendering-crawl-bud (before)
+++ external-google-javascript-seo-basics-rendering-crawl-bud (after)
@@ -1,33 +1,26 @@
-## reference · Google JavaScript SEO basics rendering crawl budget dynamic content
-* Google can index the following file types: HTML, CSS, JavaScript, JSON, PDF, and more
-* Use descriptive and concise URLs with a maximum length of 2048 characters
-* Use the `rel` attribute to qualify outbound links
-* Use the `robots.txt` file to control crawling and indexing of pages
-* Use the `meta` tags to provide page metadata, such as title, description, and keywords
-* Use the `canonical` tag to specify the preferred version of a page
-* Use the `noindex` tag to prevent indexing of a page
-* Use dynamic rendering as a workaround for JavaScript rendering issues
-* Use lazy loading to improve page load times and reduce crawl budget
-* Ensure that all content is accessible and crawlable by Googlebot
-* Use the Search Console to monitor and troubleshoot crawl errors and issues
-* Use structured data to provide additional context and information about pages
-* Ensure that all pages have a unique and descriptive title tag
-* Ensure that all pages have a meta description tag
-* Use header tags (H1-H6) to structure and organize content
-* Use alt text for all images
-* Use descriptive and concise anchor text for links
-* Avoid using too many links on a page
-* Avoid using duplicate content on multiple pages
-* Use 301 redirects to permanently redirect users and search engines to a new page
-* Use the `hreflang` tag to specify the language and region of a page
-* Ensure that all pages are mobile-friendly and responsive
-* Ensure that all pages have a fast page load time (less than 3 seconds)
-* Use Core Web Vitals to measure and improve page experience
-* Avoid using intrusive interstitials and dialogs
-* Ensure that all pages have a clear and consistent structure and organization
-* Use the `site name` and `sitelinks` features to improve search appearance
-* Use the `snippet` feature to provide a summary of a page's content
-* Use the `preferred sources` feature to specify preferred sources for a page
-* Use the `ranking systems` feature to understand how Google ranks pages
-* Ensure that all pages comply with Google's spam policies and guidelines
+## reference · Google JavaScript SEO rendering crawl budget dynamic content
+
+*   **Processing Pipeline**: Google processes JavaScript in three phases: Crawling (HTTP fetch), Rendering (headless Chromium execution), and Indexing.
+*   **Rendering Queue**: All pages with a `200` HTTP status code are queued for rendering, regardless of JavaScript presence. Non-`200` statuses (e.g., `404`) may skip rendering.
+*   **Crawl Budget & Latency**: Rendering is resource-intensive; pages may wait in the render queue for seconds to minutes. Server-side rendering (SSR) or pre-rendering is recommended to reduce latency and ensure content is visible to non-JS bots.
+*   **Link Discovery**:
+    *   Googlebot parses `href` attributes in raw HTML for initial link discovery.
+    *   Links injected via JavaScript are discovered only after rendering.
+    *   Use `rel="nofollow"` to prevent link discovery.
+    *   **Do not** use URL fragments (`#/path`) for routing; Googlebot cannot reliably resolve these. Use the **History API** (`pushState`) for client-side routing to ensure URLs are crawlable.
+*   **Soft 404s in SPAs**: Client-side routing often prevents meaningful HTTP status codes. To avoid soft 404 errors:
+    *   Redirect to a server-side `404` URL (e.g., `/not-found`) via JavaScript if content is missing.
+    *   Inject `<meta name="robots" content="noindex">` via JavaScript for error states.
+*   **Canonical URLs**:
+    *   Prefer setting `rel="canonical"` in original HTML.
+    *   If using JavaScript, ensure it sets the **same** URL as the original HTML or is the **only** canonical tag on the page. Multiple or conflicting canonical tags cause unexpected indexing results.
+*   **Robots Meta Tags**:
+    *   If a `noindex` tag is present in the initial HTML, Google may skip rendering/JS execution entirely.
+    *   **Do not** rely on JavaScript to remove a `noindex` tag from the initial HTML; it may not execute. If indexing is required, omit `noindex` from the initial HTML.
+*   **Caching & Resource Fingerprinting**:
+    *   Googlebot caches aggressively and may ignore standard cache headers.
+    *   Use **content fingerprinting** (e.g., `main.2bb85551.js`) in filenames to ensure Googlebot fetches updated JS/CSS resources.
+*   **Web Components**: Google flattens Shadow DOM and Light DOM during rendering. Only content visible in the rendered HTML is indexed. Verify visibility using the URL Inspection Tool or Rich Results Test.
+*   **Compatibility**: Use an evergreen Chromium version for testing. Use polyfills for missing browser APIs, but note that some features cannot be polyfilled.
+
 Sources: https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
```

## Decision (2026-10-31)

No lever moves. Google's pipeline (crawl, render queue, index), links found in raw HTML first, History API over URL fragments, real status codes over soft 404s - the public /learn and /tools pages are static HTML with plain anchor links, so none of the SPA cautions applies to them.
