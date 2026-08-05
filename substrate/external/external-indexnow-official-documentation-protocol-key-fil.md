---
name: external-indexnow-official-documentation-protocol-key-fil
type: reference
source: https://www.indexnow.org/documentation
source_sha: ccde97f92a3bfa02
fetched_at: 2026-08-05T03:54:26Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: IndexNow official documentation protocol key file submission limits
---

## reference · IndexNow protocol key file submission limits
* The key must have a minimum of 8 and a maximum of 128 hexadecimal characters.
* The key can contain only lowercase characters (a-z), uppercase characters (A-Z), numbers (0-9), and dashes (-).
* URL must be URL-escaped and encoded, following the RFC-3986 standard for URIs.
* You can submit up to 10,000 URLs per post.
* The key file must be a UTF-8 encoded text file.
* The key file can be hosted at the root directory of the host or in other locations within the same host.
* If hosting in a location other than the root directory, the key file location must be specified using the keyLocation variable.
* A key file located in a subdirectory can only include URLs starting with that subdirectory.
* HTTP response codes:
  + 200: OK, URL submitted successfully
  + 202: Accepted, URL received, IndexNow key validation pending
  + 400: Bad request, invalid format
  + 403: Forbidden, key not valid
  + 422: Unprocessable Entity, URLs don't belong to the host or key doesn't match the schema
  + 429: Too Many Requests, potential spam
* Search engines must have a noticeable presence in at least one market to participate in the IndexNow protocol.
Sources: https://www.indexnow.org/documentation
