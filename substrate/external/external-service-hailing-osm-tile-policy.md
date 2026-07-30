---
name: external-service-hailing-osm-tile-policy
type: reference
source: https://operations.osmfoundation.org/policies/tiles/
source_sha: 93573379bc6c4cf6
fetched_at: 2026-07-28T10:49:01Z
last_verified: 2026-07-28
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: service-hailing-osm-tile-policy
---

## reference · service-hailing-osm-tile-policy

* **Tile usage is free for everyone, but tile servers are not**: funded by donations and sponsorship, with limited capacity.
* **Must follow this policy**: to protect the service for mappers and the wider community.
* **Availability is best-effort**: no SLA or guarantee.
* **Use the correct URL**: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
* **Provide visible licence attribution**: following the [Attribution Guidelines](https://wiki.osmfoundation.org/wiki/Licence/Attribution_Guidelines).
* **Send a valid HTTP User-Agent**: clearly identifying your application.
* **Send a valid HTTP Referer (web only)**: a header is sent by browsers.
* **Cache tiles locally**: according to HTTP caching headers (or at least 7 days if your cache cannot read them).
* **Do not bulk download (“scrape”) tiles**: or offer prefetch features.
* **Do not send no-cache headers**: by default.
* **Do not set a restrictive Referrer-Policy**: that prevents the HTTP Referer header being sent.
* **Use HTTPS URL**: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
* **Do not masquerade as another app’s User-Agent**: or rely on a library’s default User-Agent.
* **Avoid hard-coding the tile URL**: allow switching without needing a software update.
* **Add a “Report a map issue” link**: to <https://www.openstreetmap.org/fixthemap>.
* **Publish a contact email**: on your website or app store listing.
* **Support HTTP/2 or HTTP/3**: for efficient multiplexed downloads.

**You must not:**

* **Use generic User-Agent headers**: from libraries or SDKs.
* **Strip Referer on web traffic**: or tunnel all clients behind a single, anonymous identity.
* **Preload entire towns/regions**: or multiple zoom stacks “just in case”.

**Enforcement:**

* **Traffic using generic defaults**: may be blocked without notice.
* **Prefetch/offline patterns**: place disproportionate load on community-funded servers and will be blocked without notice.

Sources: https://operations.osmfoundation.org/policies/tiles/
