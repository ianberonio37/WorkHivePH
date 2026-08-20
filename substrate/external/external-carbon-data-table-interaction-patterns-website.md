---
name: external-carbon-data-table-interaction-patterns-website
type: reference
source: https://carbondesignsystem.com/components/data-table/usage/
source_sha: d6430482f6fe928c
fetched_at: 2026-08-17T19:37:11Z
last_verified: 2026-08-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: carbon data table interaction patterns website
---

## reference · carbon data table interaction patterns website
*   Data tables organize and display data efficiently.
*   Data table with AI label is stable and introduces an AI explainability feature when AI is present.
*   **Use data tables when:**
    *   Organizing and displaying data.
    *   Users need to navigate to specific data for a task.
    *   Displaying all of a user’s resources.
*   **Do NOT use data tables when:**
    *   More complex data display or interactions are required.
    *   As a replacement for a spreadsheet application.
*   Carbon Design System components are tested for accessibility requirements, including default states, advanced states, screen reader compatibility (manually tested), and keyboard navigation.
*   **Data table variants:**
    *   **Default:** Basic table with header and rows, available in five row sizes.
    *   **With selection:** Allows single-select (radio button) or multi-select (checkbox) of rows for single or batch actions.
    *   **With expansion:** Presents large data in a small space; users expand/collapse rows for additional information.
*   **Data table anatomy includes:**
    1.  Title and description
    2.  Toolbar (global controls like search, filtering, settings)
    3.  Column header (with optional sorting)
    4.  Table row (configurable, selectable, expandable, zebra stripe option)
    5.  Pagination table bar (optional, for navigating large datasets)
*   **Sizing:**
    *   Available in five row sizes: extra large, large, medium, small, extra small.
    *   The column header row (`.cds--data-table thead`) must match the table row size.
    *   Extra large row heights are recommended only if data is expected to have 2 lines of content per row.
    *   Do not mix row heights for the table and header rows.
    *   **Toolbar sizing:**
        *   Tall toolbar: Pair with large and extra large row heights.
        *   Small toolbar: Pair with small and extra small row heights.
*   **Placement:**
    *   Place in a page’s main content area with ample space to avoid truncation.
    *   Avoid placing data tables inside other data tables or smaller containers.
    *   Can follow 2x grid gutter modes: wide (default), narrow, condensed.
    *   Wide
