---
name: external-supabase-realtime-architecture-channels-scaling
type: reference
source: https://supabase.com/docs/guides/realtime/architecture
source_sha: 630bc23b5dd5b3a4
fetched_at: 2026-07-29T06:21:18Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: supabase realtime architecture channels scaling
---

## reference · supabase realtime architecture channels scaling
* Supabase Realtime is a globally distributed Elixir cluster.
* Clients can connect to any node in the cluster via WebSockets.
* Realtime is written in Elixir, which compiles to Erlang, and uses the Phoenix Framework.
* Phoenix can handle millions of concurrent connections.
* Channels are implemented using Phoenix Channels with the Phoenix.PubSub.PG2 adapter.
* The PG2 adapter uses Erlang process groups to implement the PubSub model.
* Presence is an in-memory key-value store backed by a CRDT.
* Broadcast lets you send a message from any connected client to a Channel.
* Realtime connects to your Postgres database and starts streaming changes from a replication slot.
* Every Realtime region has at least two nodes for redundancy.
* Realtime retains partitions of the `realtime.messages` table for 3 days before deleting them.
* Broadcast uses Realtime Authorization by default to protect your data.
* A Postgres logical replication slot is acquired when connecting to your database.
* Subscription IDs are globally unique and messages to processes are routed automatically by the Erlang virtual machine.
Sources: https://supabase.com/docs/guides/realtime/architecture
