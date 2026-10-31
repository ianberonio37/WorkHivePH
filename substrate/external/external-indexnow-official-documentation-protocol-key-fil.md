---
name: external-indexnow-official-documentation-protocol-key-fil
type: reference
source: https://www.indexnow.org/documentation
source_sha: 364e06959e96a9e0
fetched_at: 2026-10-30T16:54:12Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: IndexNow official documentation protocol key file submission limits
---

## reference · IndexNow protocol key file submission limits

- **Key format**: 8–128 hexadecimal characters (a–f, A–F, 0–9) plus optional dashes (`-`).  
- **Key file location** (Option 1): place a UTF‑8 text file named `{key}.txt` in the web root; file content must be the key itself.  
- **Key file location** (Option 2): any path on the host; must be specified via `keyLocation` in the request.  The key file’s path limits the URL prefix that can be submitted (e.g., a key at `/catalog/` can only submit URLs starting with `/catalog/`).  
- **Single‑URL submission**: `GET https://<searchengine>/indexnow?url=<URL‑escaped>&key=<key>`; URL must be RFC‑3986 compliant.  
- **Batch submission**: `POST https://<searchengine>/indexnow` with JSON body  
  ```json
  {
    "host":"www.example.com",
    "key":"<key>",
    "urlList":[ "https://www.example.com/url1", ... ]
  }
  ```  
  - Up to **10 000 URLs per POST**.  
  - `Content-Type: application/json; charset=utf-8`.  
- **Response codes**  
  - `200 OK`: URL(s) received.  
  - `202 Accepted`: URL received; key validation pending.  
  - `400 Bad Request`: malformed request.  
  - `403 Forbidden`: key not found or invalid.  
  - `422 Unprocessable Entity`: URLs not belonging to host or key mismatch.  
  - `429 Too Many Requests`: request rate exceeded (spam protection).  
- **Rate limiting**: Exceeding the allowed frequency triggers `429`; avoid submitting too often.  
- **Ownership verification**: Search engines crawl the key file after submission; only the key owner and search engines should know the key.  
- **Best practice**: Use Option 1 (root key file) for simplicity and broader URL coverage.  

Sources: https://www.indexnow.org/documentation
