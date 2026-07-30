---
name: external-saga-pattern-long-running-distributed-transactio
type: reference
source: https://microservices.io/patterns/data/saga.html
source_sha: cd04883b9f8cea9a
fetched_at: 2026-07-29T06:16:44Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: saga pattern long running distributed transaction
---

## reference · saga pattern long running distributed transaction
* Implement each business transaction that spans multiple services as a saga, a sequence of local transactions.
* Each local transaction updates the database and publishes a message or event to trigger the next local transaction in the saga.
* If a local transaction fails, the saga executes a series of compensating transactions that undo the changes made by preceding local transactions.
* There are two ways to coordinate sagas: Choreography and Orchestration.
* Choreography: each local transaction publishes domain events that trigger local transactions in other services.
* Orchestration: an orchestrator tells the participants what local transactions to execute.
* A saga can be used to maintain data consistency across multiple services without using distributed transactions.
* Lack of automatic rollback: a developer must design compensating transactions to undo changes made earlier in a saga.
* Lack of isolation: the concurrent execution of multiple sagas and transactions can cause data anomalies.
* To address these issues, use patterns like Event Sourcing, Transactional Outbox, Aggregates, and Domain Events.
* A client that initiates a saga can determine its outcome through various options, such as waiting for the saga to complete or polling for the outcome.
* Related patterns include Database per Service, Event Sourcing, Transactional Outbox, and Command-side replica.
* When implementing sagas, consider using frameworks like Eventuate Tram Sagas or Eventuate Tram to simplify the process.
Sources: https://microservices.io/patterns/data/saga.html
