---
name: external-common-crawl-ccbot-official-faq-robots-txt-corpu
type: reference
source: https://commoncrawl.org/faq
source_sha: 76d1fbc92d212608
fetched_at: 2026-10-30T16:40:24Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Common Crawl CCBot official FAQ robots.txt corpus AI training
---

## reference · Common Crawl CCBot crawler behavior and robots.txt

*   **Identity**: CCBot identifies via User-Agent `CCBot/2.0 (https://commoncrawl.org/faq/)`. Legacy string was `CCBot/1.0 (+https://commoncrawl.org/bot.html)`.
*   **Blocking**: To block crawling, add `User-agent: CCBot` and `Disallow: /` to `robots.txt`. CCBot periodically re-checks `robots.txt` for updates.
*   **Rate Limiting**: CCBot honors the `Crawl-delay` parameter in `robots.txt`. Example: `Crawl-delay: 2` limits requests to one every 2 seconds.
*   **Protocol Support**:
    *   Supports HTTP/1.1 and HTTP/2 (HTTP/2 only over TLS/HTTPS).
    *   Supports IPv4 and IPv6.
    *   Supports conditional GET requests.
    *   Supports gzip, Brotli, and ZStandard compression encodings.
    *   Does **not** execute JavaScript or use Cookies.
*   **Redirects**: Follows up to 4 consecutive HTTP redirects for page fetches. Follows up to 5 redirects when fetching `robots.txt` (per RFC 9309).
*   **Load Management**: Uses an adaptive back-off algorithm. If the target server returns HTTP 429 or 5xx status codes, CCBot slows down request rates. Default wait time between requests to the same site is a few seconds.
*   **Sitemaps**: CCBot supports the Sitemap Protocol and utilizes any sitemap announced in `robots.txt`.
*   **Nofollow**: Honors `nofollow` attributes for link discovery. If ignored in the future, it would only be for discovery, never for associating source PageRank with targets.
*   **IP Ranges (as of 2026-08-11)**:
    *   IPv6: `2600:1f28:365:8000::/56` (no reverse DNS).
    *   IPv4: `3.41.188.32/29`, `18.97.9.168/29`, `18.97.14.80/29`, `18.97.14.88/30`.
    *   Verify authenticity via reverse DNS (e.g., `18-97-14-84.crawl.commoncrawl.org`).
    *   Current IP ranges are available as JSON at `https://index.commoncrawl.org/ccbot.json`.
*   **Index API Usage**:
    *   Always use **HTTPS** (`https://index.commoncrawl.org`); HTTP is unsupported and may fail.
    *   HTTP 503 responses indicate rate limiting; slow down request rate.
    *   If IP is temporarily blocked, wait **24 hours** before retrying.
    *   Avoid multiple threads from the same IP, proxy networks, or missing User-Agent strings (must comply with RFC 9110).
    *   For large-scale filtering, use the URL Index via Amazon Athena or Apache Spark instead of the CDX API.
    *   Use official tools like `cc-downloader` or `cdx-toolkit` for polite access.
*   **Data Access**: Data is stored on Amazon S3, supporting bulk downloads and Map-Reduce processing on EC2.
*   **Opt-Out**: Webmasters can request removal via the Common Crawl Foundation Opt-Out Registry.

Sources: https://commoncrawl.org/faq
