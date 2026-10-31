---
name: external-structured-data-product-offer-policy
type: reference
source: https://developers.google.com/search/docs/appearance/structured-data/product
source_sha: 75b2ea8d6226aa58
fetched_at: 2026-10-30T17:19:55Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: structured-data-product-offer-policy
---

## reference · structured-data-product-offer-policy

*   **Markup Selection**: Use **Product snippets** for pages where direct purchase is not possible (e.g., editorial reviews); this markup supports detailed review info like pros/cons. Use **Merchant listings** for pages where users can directly purchase; this highlights product details, sizing, and shipping.
*   **Overlap & Eligibility**: Adding required product information properties for merchant listings generally makes pages eligible for product snippets. Provide as many properties as possible to maximize eligibility for various search enhancements.
*   **Product Variants**: Implement product variant structured data to help Google identify variations of the same parent product. Both product snippets and merchant listings support this.
*   **Business Policies**: Add structured data defining ecommerce business policies (e.g., returns, shipping) nested under `Organization` markup.
*   **Data Sources**: Provide product data via on-page structured data, Google Merchant Center (GMC) feeds, or both.
    *   **Recommendation**: Use both on-page structured data and GMC feeds to maximize eligibility and allow Google to verify data.
    *   **Data Merging**: Some experiences combine data from both sources (e.g., product snippets may use pricing from the GMC feed if missing from on-page structured data).
*   **Result Enhancements**: Specific data points trigger potential search result enhancements:
    *   **Pros and Cons**: Identify in review descriptions for highlighting.
    *   **Shipping**: Share costs (especially free shipping) to clarify total cost.
    *   **Availability**: Provide stock status data.
    *   **Returns**: Share return policy, fees, and return window (days).
    *   **Price Drops**: Computed by Google observing price changes over time; display is not guaranteed.
*   **Visibility Scope**: Product structured data affects appearance in Google Search, Google Images, and Google Lens.
*   **Flexibility**: Search result enhancements are shown at Google's discretion and may change; focus on providing comprehensive rich product information rather than targeting specific UI elements.

Sources: https://developers.google.com/search/docs/appearance/structured-data/product
