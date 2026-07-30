---
name: external-service-hailing-uber-dispatch-architecture
type: reference
source: https://highscalability.com/how-uber-scales-their-real-time-market-platform/
source_sha: 7df880b1677ce16f
fetched_at: 2026-07-28T10:49:54Z
last_verified: 2026-07-28
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: service-hailing-uber-dispatch-architecture
---

## reference · service-hailing-uber-dispatch-architecture

* **Goal**: Match dynamic demand with dynamic supply in real-time.
* **Supply and Demand Services**: Separate services for tracking supply and demand capabilities and requirements.
* **DISCO (Dispatch Optimization)**: Service for matching supply and demand using geospatial indexing and routing.
* **Geospatial Index**: Scalable index for handling 1 million writes per second and many more reads per second.
* **Cell-based Indexing**: Divide the earth into tiny cells using the Google S2 library for efficient summarization and approximation.
* **Sharding**: Use cell IDs as sharding keys for scalable data storage and retrieval.
* **Replication**: Use replicas for scaling read capacity and handling high traffic.
* **Routing**: Rank options based on reducing extra driving, waiting time, and lowest overall ETA.
* **Stateful Service**: Use a stateful service approach for scaling Node.js applications.
* **Ringpop**: Consistent hash ring with a gossip protocol for scalable, fault-tolerant application-layer sharding.
* **AP System**: Trade consistency for availability in CAP terminology.
* **Technology Stack**:
	+ Node.js
	+ Python
	+ Java
	+ Go
	+ Native applications on iOS and Android
	+ Microservices
	+ Redis
	+ Postgres
	+ MySQL
	+ Riak
	+ Twemproxy
	+ Google's S2 Geometry Library
	+ Ringpop
	+ TChannel
	+ Thrift
* **Databases**:
	+ Use a mix of relational and NoSQL databases for different use cases.
	+ Implement a custom distributed column store for handling large amounts of data.

Sources: https://highscalability.com/how-uber-scales-their-real-time-market-platform/
