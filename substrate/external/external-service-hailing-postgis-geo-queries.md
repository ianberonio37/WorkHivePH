---
name: external-service-hailing-postgis-geo-queries
type: reference
source: https://supabase.com/docs/guides/database/extensions/postgis
source_sha: 0f1a2e64b4d131bd
fetched_at: 2026-07-28T10:49:25Z
last_verified: 2026-07-28
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: service-hailing-postgis-geo-queries
---

## reference · service-hailing-postgis-geo-queries
* PostGIS is a Postgres extension for interacting with Geo data, allowing sorting by geographic location and querying within boundaries.
* PostGIS provides data types like Point, Polygon, and LineString for efficient and indexable geo data.
* To enable PostGIS, go to the Database page in the Supabase dashboard, click on Extensions, search for `postgis`, and enable the extension.
* Create a spatial index on a column using `create index <index_name> on <table_name> using GIST (<column_name>)`.
* Insert geographical data using SQL or the API, with longitude first, followed by latitude.
* Use the `st_y()` and `st_x()` functions to convert geo data to lat and long floating values.
* Sort datasets by distance using the `<->` operator, which returns the two-dimensional distance between two geometries.
* Use the `&&` operator to find data points within a bounding box, which returns a boolean of whether the bounding box of two geometries intersect.
* Create database functions to encapsulate complex geo queries, such as sorting by distance or finding data within a bounding box.
* Use the `ST_SetSRID` function to set the spatial reference system identifier (SRID) of a geometry.
* Use the `ST_MakeBox2D` function to create a 2-dimensional box from two points.
* PostGIS functions like `st_distance` and `st_point` can be used to calculate distances and create points.
Sources: https://supabase.com/docs/guides/database/extensions/postgis
