---
name: external-circuit-breaker-resilience-failing-dependency
type: reference
source: https://microservices.io/patterns/reliability/circuit-breaker.html
source_sha: a5846e2d8fb47a20
fetched_at: 2026-07-29T06:22:06Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: circuit breaker resilience failing dependency
---

## reference · circuit breaker resilience failing dependency
* A service client should invoke a remote service via a proxy that functions like an electrical circuit breaker.
* When the number of consecutive failures crosses a threshold, the circuit breaker trips and all attempts to invoke the remote service will fail immediately for a timeout period.
* After the timeout expires, the circuit breaker allows a limited number of test requests to pass through.
* If those requests succeed, the circuit breaker resumes normal operation; otherwise, the timeout period begins again.
* The circuit breaker functionality can be enabled using annotations such as `@HystrixCommand` and `@EnableCircuitBreaker`.
* Choosing timeout values without creating false positives or introducing excessive latency can be challenging.
* The circuit breaker pattern has benefits, including handling the failure of services that are invoked, but also has issues such as introducing complexity.
* Related patterns include the Microservice Chassis, API Gateway, and Server-side discovery.
* Libraries such as Netflix Hystrix implement the circuit breaker pattern.
Sources: https://microservices.io/patterns/reliability/circuit-breaker.html
