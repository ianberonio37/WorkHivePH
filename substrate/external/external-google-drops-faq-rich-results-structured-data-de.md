---
name: external-google-drops-faq-rich-results-structured-data-de
type: reference
source: https://www.searchenginejournal.com/google-drops-faq-rich-results-from-search/574429/
source_sha: fccc1f9ee45200d4
fetched_at: 2026-10-25T21:56:29Z
last_verified: 2026-10-26
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Google drops FAQ rich results structured data deprecation
---

## reference · Google FAQ Rich Results Deprecation

- **Status**: Google has fully deprecated FAQ rich results; they no longer appear in Google Search.
- **Key Dates**:
  - **May 7, 2026**: FAQ rich results stopped appearing in search results.
  - **June 2026**: Removal of the FAQ search appearance filter, rich result report, and support in the Rich Results Test tool.
  - **August 2026**: Removal of FAQ rich result support from the Search Console API.
- **Action Items**:
  - **Do not rush to remove markup**: Existing `FAQPage` structured data can remain on pages without causing errors or penalties.
  - **Update API calls**: Teams using the Search Console API must adjust or remove FAQ-related calls before August 2026.
  - **Ignore visibility expectations**: FAQ schema no longer generates visible rich results for any site, including government and health websites (which were the last eligible category).
- **Context**:
  - This completes a three-year phase-out that began in April 2023 with reduced visibility and continued in August 2023 when eligibility was restricted to authoritative government and health sites.
  - `FAQPage` remains a valid Schema.org type, but its utility for Google Search rich results is zero.
  - Google has not explicitly linked this deprecation to AI search trends, though practitioners have noted FAQ schema's potential role in AI content parsing.
