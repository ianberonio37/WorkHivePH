---
name: change_external-structured-data-product-offer-policy_2026-10-31
type: source-change
chunk: external-structured-data-product-offer-policy
topic: structured-data-product-offer-policy
source: https://developers.google.com/search/docs/appearance/structured-data/product
detected: 2026-10-31
age_days: 95
ttl_days: 30
---

# external-structured-data-product-offer-policy changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-structured-data-product-offer-policy (before)
+++ external-structured-data-product-offer-policy (after)
@@ -1,15 +1,19 @@
 ## reference · structured-data-product-offer-policy
-* Use schema.org vocabulary for structured data
-* Implement structured data for product offers, including price, availability, and reviews
-* Use the `@context` and `@type` attributes to define the context and type of structured data
-* Use the `priceSpecification` property to specify the price of a product
-* Use the `availability` property to specify the availability of a product
-* Use the `review` property to specify reviews of a product
-* Use the `aggregateRating` property to specify the average rating of a product
-* Test and validate structured data using Google's Structured Data Markup Helper and Rich Results Test tools
-* Follow Google's structured data guidelines and policies for implementation and maintenance
-* Keep structured data up-to-date and accurate to ensure proper display in search results
-* Use JSON-LD or Microdata formats for structured data implementation
-* Avoid using nested structured data or overly complex implementations
-* Use a consistent and standardized approach to implementing structured data across a website
+
+*   **Markup Selection**: Use **Product snippets** for pages where direct purchase is not possible (e.g., editorial reviews); this markup supports detailed review info like pros/cons. Use **Merchant listings** for pages where users can directly purchase; this highlights product details, sizing, and shipping.
+*   **Overlap & Eligibility**: Adding required product information properties for merchant listings generally makes pages eligible for product snippets. Provide as many properties as possible to maximize eligibility for various search enhancements.
+*   **Product Variants**: Implement product variant structured data to help Google identify variations of the same parent product. Both product snippets and merchant listings support this.
+*   **Business Policies**: Add structured data defining ecommerce business policies (e.g., returns, shipping) nested under `Organization` markup.
+*   **Data Sources**: Provide product data via on-page structured data, Google Merchant Center (GMC) feeds, or both.
+    *   **Recommendation**: Use both on-page structured data and GMC feeds to maximize eligibility and allow Google to verify data.
+    *   **Data Merging**: Some experiences combine data from both sources (e.g., product snippets may use pricing from the GMC feed if missing from on-page structured data).
+*   **Result Enhancements**: Specific data points trigger potential search result enhancements:
+    *   **Pros and Cons**: Identify in review descriptions for highlighting.
+    *   **Shipping**: Share costs (especially free shipping) to clarify total cost.
+    *   **Availability**: Provide stock status data.
+    *   **Returns**: Share return policy, fees, and return window (days).
+    *   **Price Drops**: Computed by Google observing price changes over time; display is not guaranteed.
+*   **Visibility Scope**: Product structured data affects appearance in Google Search, Google Images, and Google Lens.
+*   **Flexibility**: Search result enhancements are shown at Google's discretion and may change; focus on providing comprehensive rich product information rather than targeting specific UI elements.
+
 Sources: https://developers.google.com/search/docs/appearance/structured-data/product
```

## Decision (2026-10-31)

No lever moves. Product/merchant-listing markup and Merchant Center feeds apply to pages that sell; the site's public SEO pages sell nothing and the marketplace's listings are signed-in, not indexed. Nothing cites this source yet.
