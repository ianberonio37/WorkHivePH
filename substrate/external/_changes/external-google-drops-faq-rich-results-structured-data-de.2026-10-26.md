---
name: change_external-google-drops-faq-rich-results-structured-data-de_2026-10-26
type: source-change
chunk: external-google-drops-faq-rich-results-structured-data-de
topic: Google drops FAQ rich results structured data deprecation
source: https://www.searchenginejournal.com/google-drops-faq-rich-results-from-search/574429/
detected: 2026-10-26
age_days: 98
ttl_days: 30
---

# external-google-drops-faq-rich-results-structured-data-de changed on re-fetch (2026-10-26)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-google-drops-faq-rich-results-structured-data-de (before)
+++ external-google-drops-faq-rich-results-structured-data-de (after)
@@ -1,9 +1,15 @@
-## reference · Google drops FAQ rich results structured data deprecation
+## reference · Google FAQ Rich Results Deprecation
 
-* Google is dropping support for FAQ rich results structured data.
-* No specific date or timeline for the deprecation was mentioned.
-* FAQ rich results are a type of search engine result that displays frequently asked questions and answers about a webpage.
-* Webmasters should review their structured data and update it to ensure it is accurate and up-to-date.
-* Google recommends using other types of structured data, such as schema.org, to enhance search engine results.
-
-Sources: https://www.searchenginejournal.com/google-drops-faq-rich-results-from-search/574429/
+- **Status**: Google has fully deprecated FAQ rich results; they no longer appear in Google Search.
+- **Key Dates**:
+  - **May 7, 2026**: FAQ rich results stopped appearing in search results.
+  - **June 2026**: Removal of the FAQ search appearance filter, rich result report, and support in the Rich Results Test tool.
+  - **August 2026**: Removal of FAQ rich result support from the Search Console API.
+- **Action Items**:
+  - **Do not rush to remove markup**: Existing `FAQPage` structured data can remain on pages without causing errors or penalties.
+  - **Update API calls**: Teams using the Search Console API must adjust or remove FAQ-related calls before August 2026.
+  - **Ignore visibility expectations**: FAQ schema no longer generates visible rich results for any site, including government and health websites (which were the last eligible category).
+- **Context**:
+  - This completes a three-year phase-out that began in April 2023 with reduced visibility and continued in August 2023 when eligibility was restricted to authoritative government and health sites.
+  - `FAQPage` remains a valid Schema.org type, but its utility for Google Search rich results is zero.
+  - Google has not explicitly linked this deprecation to AI search trends, though practitioners have noted FAQ schema's potential role in AI content parsing.
```
