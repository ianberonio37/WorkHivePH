---
name: external-transactional-outbox-reliable-event-publishing
type: reference
source: https://microservices.io/patterns/data/transactional-outbox.html
source_sha: 6af1db49eac5a138
fetched_at: 2026-07-29T06:15:51Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: transactional outbox reliable event publishing
---

## reference · transactional outbox reliable event publishing
* To atomically update a database and send messages to a message broker, store the message in the database as part of the transaction that updates the business entities.
* A separate process (Message relay) sends the messages to the message broker.
* The Message relay might publish a message more than once, so message consumers must be idempotent.
* Messages must be sent to the message broker in the order they were sent by the service.
* The Transactional outbox pattern has benefits: no 2PC is used, messages are guaranteed to be sent if and only if the database transaction commits, and messages are sent to the message broker in the order they were sent by the application.
* The pattern has drawbacks: it's potentially error-prone, and the Message relay might publish a message more than once.
* Related patterns include Saga, Domain event, Event sourcing, Transaction log tailing, and Polling publisher.
* To implement the Message relay, use either the Transaction log tailing or Polling publisher pattern.
Sources: https://microservices.io/patterns/data/transactional-outbox.html
