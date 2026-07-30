---
name: external-idempotency-keys-safe-api-retries
type: reference
source: https://docs.stripe.com/api/idempotent_requests
source_sha: de739803c8706e39
fetched_at: 2026-07-29T06:17:19Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: idempotency keys safe API retries
---

## reference · idempotency keys safe API retries
* The Stripe API uses REST and has predictable resource-oriented URLs.
* API requests must be made over HTTPS, and authentication is required.
* The Stripe API does not support bulk updates, and only one object can be worked on per request.
* API keys carry many privileges and should be kept safe by following best practices.
* Test mode secret keys start with `sk_test_` and have unrestricted access to their sandboxes.
* Live mode secret keys start with `sk_live_` and grant access to all Stripe API resources.
* Restricted API keys can be created with specific API permissions to limit damage in case of a security breach.
* API requests without authentication will fail.
* HTTP response codes indicate success or failure of an API request, with `2xx` indicating success, `4xx` indicating an error, and `5xx` indicating a server error.
* Error codes are provided for some errors, and can be used to handle errors programmatically.
* Idempotency errors occur when an `Idempotency-Key` is re-used on a request that does not match the first request's API endpoint and parameters.
* The `Idempotency-Key` header can be used to make safe retries of API requests.
* Client libraries raise exceptions for various reasons, and code should be written to handle these exceptions.
* Error types include `api_error`, `card_error`, `idempotency_error`, and `invalid_request_error`.
* The `expand` request parameter can be used to request additional information in API responses.
Sources: https://docs.stripe.com/api/idempotent_requests
