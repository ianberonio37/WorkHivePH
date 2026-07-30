---
name: external-cqrs-read-model-separation-query-side
type: reference
source: https://microservices.io/patterns/data/cqrs.html
source_sha: 4247f2c37f85b8f6
fetched_at: 2026-07-29T06:22:37Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: CQRS read model separation query side
---

## reference · CQRS read model separation query side
* Define a view database, a read-only ‘replica’ designed to support a query or group of related queries.
* The application keeps the view database up to date by subscribing to Domain events published by the service that owns the data.
* The type of database and its schema are optimized for the query or queries, often a NoSQL database such as a document database or key-value store.
* CQRS supports multiple denormalized views that are scalable and performant.
* CQRS improves separation of concerns, resulting in simpler command and query models.
* CQRS is necessary in an event-sourced architecture.
* Drawbacks of CQRS include increased complexity, potential code duplication, and replication lag/eventually consistent views.
* Related patterns include Database per Service, API Composition, Domain Event, and Event Sourcing.
Sources: https://microservices.io/patterns/data/cqrs.html
