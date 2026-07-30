---
name: external-h3-hexagonal-spatial-index-geospatial-partitioni
type: reference
source: https://h3geo.org/docs/highlights/indexing/
source_sha: 02a1ec63a03de052
fetched_at: 2026-07-29T06:17:47Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: H3 hexagonal spatial index geospatial partitioning
---

## reference · H3 hexagonal spatial index geospatial partitioning
* H3 is a hierarchical geospatial index with a spatial hierarchy of hexagonal cells.
* Every hexagonal cell has seven child cells below it in the hierarchy, referred to as _aperture 7_.
* Hexagons do not cleanly subdivide into seven finer hexagons, but this can be approximated by alternating the orientation of grids.
* The borders of hexagons indexed at a specific resolution are not approximate and are not affected by these considerations.
* Logical containment in the index is exact, while geographic containment is approximate.
* The H3 index allows for efficiently relating datasets indexed at different resolutions of the H3 grid.
* Functions for changing precision (`h3ToParent`, `h3ToChildren`) are implemented with only a few bitwise operations, making them very fast.
* Geographically close locations will tend to have numerically close indexes.
* The hierarchical structure can be used in analysis to encode precision or uncertainty for a location in the spatial index.
* Hierarchical containment allows for use cases like making contiguous sets of cells "compact" with `compactCells`.
* In use cases where exact boundaries are needed, applications must take care to handle the hierarchical concerns.
* The grid system can be used as an optimization in addition to a more precise point-in-polygon check.
Sources: https://h3geo.org/docs/highlights/indexing/
