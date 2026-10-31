---
name: external-service-hailing-postgis-geo-queries
type: reference
source: https://supabase.com/docs/guides/database/extensions/postgis
source_sha: 200f01d8ab17b3f3
fetched_at: 2026-10-30T17:04:33Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: service-hailing-postgis-geo-queries
---

## reference · service-hailing-postgis-geo-queries
- PostGIS is a PostgreSQL extension that adds native geometric data types and functions for scalable geo queries.  
- Core geometry types include **Point**, **Polygon**, **LineString**, plus many others for representing spatial features.  
- Use the **Point** type to store a single latitude/longitude pair (e.g., `POINT(lon lat)`).  
- Geometry columns can be indexed with **GiST** or **SP‑GiST** indexes, enabling fast spatial searches (e.g., nearest‑neighbor, within‑radius).  
- Typical spatial queries:  
  - `ST_Distance(geom1, geom2)` – compute distance between two geometries.  
  - `ST_Within(geom, polygon)` – test if a point lies inside a polygon.  
  - `ST_Contains(polygon, geom)` – inverse of `ST_Within`.  
  - `ST_Intersects(geom1, geom2)` – check any overlap.  
- For large datasets, always create a GiST index on the geometry column:  
  ```sql
  CREATE INDEX idx_table_geom ON table USING GIST (geom);
  ```  
- When inserting points, use the `ST_SetSRID` function to define the spatial reference (commonly SRID 4326 for WGS 84 lat/long):  
  ```sql
  INSERT INTO rides (location) VALUES (ST_SetSRID(ST_MakePoint(lon, lat), 4326));
  ```  
- To find records within a radius (e.g., 5 km) of a location:  
  ```sql
  SELECT *
  FROM rides
  WHERE ST_DWithin(
        location,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
        5000);  -- distance in meters
  ```  
- For ordering results by proximity:  
  ```sql
  SELECT *, ST_Distance(location, ref_geom) AS dist
  FROM rides
  ORDER BY dist ASC
  LIMIT 10;
  ```  

Sources: https://supabase.com/docs/guides/database/extensions/postgis
