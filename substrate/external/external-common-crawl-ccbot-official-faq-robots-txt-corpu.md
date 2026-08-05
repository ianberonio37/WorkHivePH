---
name: external-common-crawl-ccbot-official-faq-robots-txt-corpu
type: reference
source: https://commoncrawl.org/faq
source_sha: 6b6b0794e14ee58f
fetched_at: 2026-08-05T04:05:53Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Common Crawl CCBot official FAQ robots.txt corpus AI training
---

## reference · Common Crawl CCBot official FAQ robots.txt corpus AI training

* Common Crawl is a 501(c)(3) non-profit organization.
* Common Crawl's goal is to democratize the data so that everyone, not just big companies, can do high-quality research and analysis.
* The crawl data is stored on Amazon’s S3 service.
* The crawl data can be bulk downloaded as well as directly accessed for Map-Reduce processing in EC2.
* The terms of use for Common Crawl data are described on the [Terms of Use](https://commoncrawl.org/terms-of-use/) page.
* The Common Crawl CCBot crawler is a Nutch-based web crawler that makes use of the Apache Hadoop project.
* The CCBot identifies itself via its UserAgent string as: `CCBot/2.0 (https://commoncrawl.org/faq/)`
* The CCBot supports both HTTP/1.1 and HTTP/2, the latter only over TLS (https://).
* The CCBot follows up to four consecutive HTTP redirects, or up to five when fetching robots.txt in line with [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html#name-redirects).
* The CCBot uses an adaptive back-off algorithm that slows down requests to your website if your web server is responding with a HTTP 429 or 5xx status.
* To slow down the CCBot, add the following to your robots.txt file: `User-agent: CCBot Crawl-delay: <number>`
* To block the CCBot, add the following to your robots.txt file: `User-agent: CCBot Disallow: /`
* The CCBot supports the Sitemap Protocol and utilizes any Sitemap announced in the robots.txt file.
* The CCBot supports conditional GET requests and currently supports the gzip, Brotli, and ZStandard encoding formats.
* The CCBot IP address ranges are as follows:
  * IPv6: `2600:1f28:365:80b0::/60`
  * IPv4: `18.97.9.168/29`, `18.97.14.80/29`, `18.97.14.88/30`, `98.85.178.216/32`, `3.41.188.32/29`
* The CCBot is now run on dedicated IP address ranges with reverse DNS.
* The CCBot currently honors the nofollow attribute as it applies to links embedded on your site.

Sources: https://commoncrawl.org/faq
