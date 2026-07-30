---
name: external-service-hailing-realtime-location-map
type: reference
source: https://supabase.com/blog/postgres-realtime-location-sharing-with-maplibre
source_sha: c90c144815178071
fetched_at: 2026-07-28T10:48:52Z
last_verified: 2026-07-28
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: service-hailing-realtime-location-map
---

## reference · service-hailing-realtime-location-map
* Use Supabase Edge Functions to capture live location data from a Telegram Bot and insert it into Postgres.
* Use an RPC (remote procedure call) to insert location data into Postgres, validating user sessions and inserting data into the `locations` table.
* Use Supabase Realtime to listen to changes in the database, broadcasting updates to multiple clients.
* Use MapLibre GL JS in React to draw live location data onto a map, updating the map with new location data in real-time.
* Set up a Realtime subscription in the `useEffect` hook to listen to `INSERT` events on the `locations` table.
* Use `react-map-gl` to draw location markers onto the map, updating the map with new location data.
* Use Protomaps hosted on Supabase Storage for the base map.
* Create a function `location_insert` to insert location data into the `locations` table, validating user sessions and inserting data.
* Use the `supabase` client to create a Realtime subscription, listening to `postgres_changes` events on the `locations` table.
* Use the `maplibregl` library to render the map, adding markers for each location.
* Set the initial view state of the map with `longitude`, `latitude`, and `zoom` properties.
* Use the `st_point` function to create a point from the location's longitude and latitude.
* Validate user sessions before inserting location data into the `locations` table.
* Handle errors when inserting location data, logging error messages.
* Sources: https://supabase.com/blog/postgres-realtime-location-sharing-with-maplibre
