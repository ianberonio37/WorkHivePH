---
name: external-enterprise-data-table-usage-batch-actions-expand
type: reference
source: https://github.com/carbon-design-system/carbon-website/blob/main/src/pages/components/data-table/usage.mdx
source_sha: 64f4f1df0d0c6ce9
fetched_at: 2026-08-17T19:35:40Z
last_verified: 2026-08-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: enterprise data table usage batch actions expandable rows carbon
---

## reference · enterprise data table usage batch actions expandable rows carbon

- **Row sizes**: Data tables support five row heights – extra‑small, small, medium, large, extra‑large.  
- **Header‑row height match**: The `<thead>` row must use the same height as the table rows; never mix heights.  
- **Toolbar pairing**:  
  - Tall toolbar → only with **large** or **extra‑large** rows.  
  - Small toolbar → only with **small** or **extra‑small** rows.  
- **Batch expansion**: The “expand‑all” chevron is **not shown by default** in the expandable variant; enable it only when a true “batch expansion” use case exists.  
- **Performance tip**: Expanding all rows at once defeats the lazy‑load benefit of expandable tables; use batch expansion sparingly.  
- **Selection controls**:  
  - Row checkboxes: two states (checked / unchecked).  
  - Header “select‑all” checkbox: three states (checked, unchecked, indeterminate).  
  - Radio selection limits the user to **one** row; radio button appears in the first column.  
- **Batch actions**: Appear in the table toolbar or in a dedicated batch‑action mode after one or more rows are selected.  
- **Toolbar action limit**: Show **up to five** primary/ghost/icon‑only actions directly; expose additional actions via an overflow menu or combo button.  
- **Hover state**: Row hover must always be enabled to aid visual scanning, even for non‑interactive rows.  
- **Pagination**: Always placed at the **bottom** of the table.  
  - Simple pagination → only previous/next controls and current page indicator.  
  - Advanced pagination → includes items‑per‑page selector and direct page‑number input.  
- **Column titles**: Use 1‑2 words, sentence‑case; if longer, wrap to two lines and truncate with a tooltip on hover.  
- **Expandable rows**: Use for large data sets where secondary information can be hidden until needed; if expanded content feels cramped, move it to a dedicated page, side panel, or separate table.  
- **Batch actions + expansion**: When both are present, the expand icon appears **left** of the selection icon.  
- **Placement**: Position tables in the main content area with ample width; avoid nesting tables or placing them in cramped containers.  
- **Gutter modes**:  
  - **Wide** (default) → maximum breathing room.  
  - **Narrow** → aligns table title with surrounding type.  
  - **Condensed** → permissible but requires contrasting background or hybrid grid to prevent visual blending.  

Sources: https://github.com/carbon-design-system/carbon-website/blob/main/src/pages/components/data-table/usage.mdx
