---
name: change_external-common-crawl-ccbot-official-faq-robots-txt-corpu_2026-10-31
type: source-change
chunk: external-common-crawl-ccbot-official-faq-robots-txt-corpu
topic: Common Crawl CCBot official FAQ robots.txt corpus AI training
source: https://commoncrawl.org/faq
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-common-crawl-ccbot-official-faq-robots-txt-corpu changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-common-crawl-ccbot-official-faq-robots-txt-corpu (before)
+++ external-common-crawl-ccbot-official-faq-robots-txt-corpu (after)
@@ -1,22 +1,30 @@
-## reference · Common Crawl CCBot official FAQ robots.txt corpus AI training
+## reference · Common Crawl CCBot crawler behavior and robots.txt
 
-* Common Crawl is a 501(c)(3) non-profit organization.
-* Common Crawl's goal is to democratize the data so that everyone, not just big companies, can do high-quality research and analysis.
-* The crawl data is stored on Amazon’s S3 service.
-* The crawl data can be bulk downloaded as well as directly accessed for Map-Reduce processing in EC2.
-* The terms of use for Common Crawl data are described on the [Terms of Use](https://commoncrawl.org/terms-of-use/) page.
-* The Common Crawl CCBot crawler is a Nutch-based web crawler that makes use of the Apache Hadoop project.
-* The CCBot identifies itself via its UserAgent string as: `CCBot/2.0 (https://commoncrawl.org/faq/)`
-* The CCBot supports both HTTP/1.1 and HTTP/2, the latter only over TLS (https://).
-* The CCBot follows up to four consecutive HTTP redirects, or up to five when fetching robots.txt in line with [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html#name-redirects).
-* The CCBot uses an adaptive back-off algorithm that slows down requests to your website if your web server is responding with a HTTP 429 or 5xx status.
-* To slow down the CCBot, add the following to your robots.txt file: `User-agent: CCBot Crawl-delay: <number>`
-* To block the CCBot, add the following to your robots.txt file: `User-agent: CCBot Disallow: /`
-* The CCBot supports the Sitemap Protocol and utilizes any Sitemap announced in the robots.txt file.
-* The CCBot supports conditional GET requests and currently supports the gzip, Brotli, and ZStandard encoding formats.
-* The CCBot IP address ranges are as follows:
-  * IPv6: `2600:1f28:365:80b0::/60`
-  * IPv4: `18.97.9.168/29`, `18.97.14.80/29`, `18.97.14.88/30`, `98.85.178.216/32`, `3.41.188.32/29`
-* The CCBot is now run on dedicated IP address ranges with reverse DNS.
-* The CCBot currently honors the nofollow attribute as it applies to links embedded on your site.
+*   **Identity**: CCBot identifies via User-Agent `CCBot/2.0 (https://commoncrawl.org/faq/)`. Legacy string was `CCBot/1.0 (+https://commoncrawl.org/bot.html)`.
+*   **Blocking**: To block crawling, add `User-agent: CCBot` and `Disallow: /` to `robots.txt`. CCBot periodically re-checks `robots.txt` for updates.
+*   **Rate Limiting**: CCBot honors the `Crawl-delay` parameter in `robots.txt`. Example: `Crawl-delay: 2` limits requests to one every 2 seconds.
+*   **Protocol Support**:
+    *   Supports HTTP/1.1 and HTTP/2 (HTTP/2 only over TLS/HTTPS).
+    *   Supports IPv4 and IPv6.
+    *   Supports conditional GET requests.
+    *   Supports gzip, Brotli, and ZStandard compression encodings.
+    *   Does **not** execute JavaScript or use Cookies.
+*   **Redirects**: Follows up to 4 consecutive HTTP redirects for page fetches. Follows up to 5 redirects when fetching `robots.txt` (per RFC 9309).
+*   **Load Management**: Uses an adaptive back-off algorithm. If the target server returns HTTP 429 or 5xx status codes, CCBot slows down request rates. Default wait time between requests to the same site is a few seconds.
+*   **Sitemaps**: CCBot supports the Sitemap Protocol and utilizes any sitemap announced in `robots.txt`.
+*   **Nofollow**: Honors `nofollow` attributes for link discovery. If ignored in the future, it would only be for discovery, never for associating source PageRank with targets.
+*   **IP Ranges (as of 2026-08-11)**:
+    *   IPv6: `2600:1f28:365:8000::/56` (no reverse DNS).
+    *   IPv4: `3.41.188.32/29`, `18.97.9.168/29`, `18.97.14.80/29`, `18.97.14.88/30`.
+    *   Verify authenticity via reverse DNS (e.g., `18-97-14-84.crawl.commoncrawl.org`).
+    *   Current IP ranges are available as JSON at `https://index.commoncrawl.org/ccbot.json`.
+*   **Index API Usage**:
+    *   Always use **HTTPS** (`https://index.commoncrawl.org`); HTTP is unsupported and may fail.
+    *   HTTP 503 responses indicate rate limiting; slow down request rate.
+    *   If IP is temporarily blocked, wait **24 hours** before retrying.
+    *   Avoid multiple threads from the same IP, proxy networks, or missing User-Agent strings (must comply with RFC 9110).
+    *   For large-scale filtering, use the URL Index via Amazon Athena or Apache Spark instead of the CDX API.
+    *   Use official tools like `cc-downloader` or `cdx-toolkit` for polite access.
+*   **Data Access**: Data is stored on Amazon S3, supporting bulk downloads and Map-Reduce processing on EC2.
+*   **Opt-Out**: Webmasters can request removal via the Common Crawl Foundation Opt-Out Registry.
 
```

## Decision (2026-10-31)

No lever moves. robots.txt addresses CCBot by name (read 2026-10-31); the facts re-fetched (CCBot/2.0 identity, honours Crawl-delay, no JavaScript) change nothing the site relies on.
