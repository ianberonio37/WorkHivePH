---
name: change_external-indexnow-official-documentation-protocol-key-fil_2026-10-31
type: source-change
chunk: external-indexnow-official-documentation-protocol-key-fil
topic: IndexNow official documentation protocol key file submission limits
source: https://www.indexnow.org/documentation
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-indexnow-official-documentation-protocol-key-fil changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-indexnow-official-documentation-protocol-key-fil (before)
+++ external-indexnow-official-documentation-protocol-key-fil (after)
@@ -1,18 +1,28 @@
 ## reference · IndexNow protocol key file submission limits
-* The key must have a minimum of 8 and a maximum of 128 hexadecimal characters.
-* The key can contain only lowercase characters (a-z), uppercase characters (A-Z), numbers (0-9), and dashes (-).
-* URL must be URL-escaped and encoded, following the RFC-3986 standard for URIs.
-* You can submit up to 10,000 URLs per post.
-* The key file must be a UTF-8 encoded text file.
-* The key file can be hosted at the root directory of the host or in other locations within the same host.
-* If hosting in a location other than the root directory, the key file location must be specified using the keyLocation variable.
-* A key file located in a subdirectory can only include URLs starting with that subdirectory.
-* HTTP response codes:
-  + 200: OK, URL submitted successfully
-  + 202: Accepted, URL received, IndexNow key validation pending
-  + 400: Bad request, invalid format
-  + 403: Forbidden, key not valid
-  + 422: Unprocessable Entity, URLs don't belong to the host or key doesn't match the schema
-  + 429: Too Many Requests, potential spam
-* Search engines must have a noticeable presence in at least one market to participate in the IndexNow protocol.
+
+- **Key format**: 8–128 hexadecimal characters (a–f, A–F, 0–9) plus optional dashes (`-`).  
+- **Key file location** (Option 1): place a UTF‑8 text file named `{key}.txt` in the web root; file content must be the key itself.  
+- **Key file location** (Option 2): any path on the host; must be specified via `keyLocation` in the request.  The key file’s path limits the URL prefix that can be submitted (e.g., a key at `/catalog/` can only submit URLs starting with `/catalog/`).  
+- **Single‑URL submission**: `GET https://<searchengine>/indexnow?url=<URL‑escaped>&key=<key>`; URL must be RFC‑3986 compliant.  
+- **Batch submission**: `POST https://<searchengine>/indexnow` with JSON body  
+  ```json
+  {
+    "host":"www.example.com",
+    "key":"<key>",
+    "urlList":[ "https://www.example.com/url1", ... ]
+  }
+  ```  
+  - Up to **10 000 URLs per POST**.  
+  - `Content-Type: application/json; charset=utf-8`.  
+- **Response codes**  
+  - `200 OK`: URL(s) received.  
+  - `202 Accepted`: URL received; key validation pending.  
+  - `400 Bad Request`: malformed request.  
+  - `403 Forbidden`: key not found or invalid.  
+  - `422 Unprocessable Entity`: URLs not belonging to host or key mismatch.  
+  - `429 Too Many Requests`: request rate exceeded (spam protection).  
+- **Rate limiting**: Exceeding the allowed frequency triggers `429`; avoid submitting too often.  
+- **Ownership verification**: Search engines crawl the key file after submission; only the key owner and search engines should know the key.  
+- **Best practice**: Use Option 1 (root key file) for simplicity and broader URL coverage.  
+
 Sources: https://www.indexnow.org/documentation
```

## Decision (2026-10-31)

No lever moves. The protocol is unchanged (hex key 8-128 characters, {key}.txt at the web root, batch POST up to 10,000 URLs, 200/202 accepted) - what tools/indexnow_submit.py already does; the pushes themselves are the KA-S rows, which wait for the M4 frontend push.
