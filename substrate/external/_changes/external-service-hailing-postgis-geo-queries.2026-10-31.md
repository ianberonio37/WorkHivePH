---
name: change_external-service-hailing-postgis-geo-queries_2026-10-31
type: source-change
chunk: external-service-hailing-postgis-geo-queries
topic: service-hailing-postgis-geo-queries
source: https://supabase.com/docs/guides/database/extensions/postgis
detected: 2026-10-31
age_days: 94
ttl_days: 30
---

# external-service-hailing-postgis-geo-queries changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-service-hailing-postgis-geo-queries (before)
+++ external-service-hailing-postgis-geo-queries (after)
@@ -1,14 +1,36 @@
 ## reference · service-hailing-postgis-geo-queries
-* PostGIS is a Postgres extension for interacting with Geo data, allowing sorting by geographic location and querying within boundaries.
-* PostGIS provides data types like Point, Polygon, and LineString for efficient and indexable geo data.
-* To enable PostGIS, go to the Database page in the Supabase dashboard, click on Extensions, search for `postgis`, and enable the extension.
-* Create a spatial index on a column using `create index <index_name> on <table_name> using GIST (<column_name>)`.
-* Insert geographical data using SQL or the API, with longitude first, followed by latitude.
-* Use the `st_y()` and `st_x()` functions to convert geo data to lat and long floating values.
-* Sort datasets by distance using the `<->` operator, which returns the two-dimensional distance between two geometries.
-* Use the `&&` operator to find data points within a bounding box, which returns a boolean of whether the bounding box of two geometries intersect.
-* Create database functions to encapsulate complex geo queries, such as sorting by distance or finding data within a bounding box.
-* Use the `ST_SetSRID` function to set the spatial reference system identifier (SRID) of a geometry.
-* Use the `ST_MakeBox2D` function to create a 2-dimensional box from two points.
-* PostGIS functions like `st_distance` and `st_point` can be used to calculate distances and create points.
+- PostGIS is a PostgreSQL extension that adds native geometric data types and functions for scalable geo queries.  
+- Core geometry types include **Point**, **Polygon**, **LineString**, plus many others for representing spatial features.  
+- Use the **Point** type to store a single latitude/longitude pair (e.g., `POINT(lon lat)`).  
+- Geometry columns can be indexed with **GiST** or **SP‑GiST** indexes, enabling fast spatial searches (e.g., nearest‑neighbor, within‑radius).  
+- Typical spatial queries:  
+  - `ST_Distance(geom1, geom2)` – compute distance between two geometries.  
+  - `ST_Within(geom, polygon)` – test if a point lies inside a polygon.  
+  - `ST_Contains(polygon, geom)` – inverse of `ST_Within`.  
+  - `ST_Intersects(geom1, geom2)` – check any overlap.  
+- For large datasets, always create a GiST index on the geometry column:  
+  ```sql
+  CREATE INDEX idx_table_geom ON table USING GIST (geom);
+  ```  
+- When inserting points, use the `ST_SetSRID` function to define the spatial reference (commonly SRID 4326 for WGS 84 lat/long):  
+  ```sql
+  INSERT INTO rides (location) VALUES (ST_SetSRID(ST_MakePoint(lon, lat), 4326));
+  ```  
+- To find records within a radius (e.g., 5 km) of a location:  
+  ```sql
+  SELECT *
+  FROM rides
+  WHERE ST_DWithin(
+        location,
+        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
+        5000);  -- distance in meters
+  ```  
+- For ordering results by proximity:  
+  ```sql
+  SELECT *, ST_Distance(location, ref_geom) AS dist
+  FROM rides
+  ORDER BY dist ASC
+  LIMIT 10;
+  ```  
+
 Sources: https://supabase.com/docs/guides/database/extensions/postgis
```

## Decision (2026-10-31)

No lever moves. PostGIS basics (Point, GiST index, ST_Distance / ST_DWithin) are what the service-hailing broadcast radius already uses (service_requests.location, broadcast_radius_m); nothing in the re-fetch changes a query or index.
