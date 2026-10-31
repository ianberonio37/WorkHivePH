---
name: change_external-google-structured-data-general-guidelines-polici_2026-10-31
type: source-change
chunk: external-google-structured-data-general-guidelines-polici
topic: Google structured data general guidelines policies spam quality requirements
source: https://developers.google.com/search/docs/appearance/structured-data/sd-policies
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-google-structured-data-general-guidelines-polici changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-google-structured-data-general-guidelines-polici (before)
+++ external-google-structured-data-general-guidelines-polici (after)
@@ -1,21 +1,14 @@
 ## reference · Google structured data general guidelines policies spam quality requirements
-* Use structured data to describe content, not to manipulate search rankings
-* Ensure structured data is accurate, up-to-date, and visible on the page
-* Use schema.org vocabulary for structured data
-* Test and validate structured data using Google's tools
-* Avoid spamming or manipulating search results with structured data
-* Do not use structured data to misrepresent content or deceive users
-* Use rel attributes to qualify outbound links
-* Specify a canonical URL with rel="canonical" and other methods
-* Fix canonicalization issues to avoid duplicate content
-* Use meta tags and HTML attributes that Google supports
-* Use the robots meta tag, data-nosnippet, and X-Robots-Tag to control crawling and indexing
-* Remove or redact sensitive information from pages and images
-* Use redirects and Google Search to handle site moves and changes
-* Optimize for page experience, including Core Web Vitals and interstitials
-* Follow Google's guidelines for AI features, featured snippets, and flexible sampling
-* Ensure site names, sitelinks, and snippets are accurate and descriptive
-* Use structured data to generate enriched search results
-* Generate structured data with JavaScript, if necessary
-* Follow feature guides for specific structured data types, such as Article, Book, and Breadcrumb
+*   Structured data must follow Google Search Essentials, including Spam Policies.
+*   Structured data must be a true representation of the page content.
+*   Structured data should not be used to deceive users.
+*   Structured data must not describe content that is hidden from users.
+*   Structured data must be up-to-date.
+*   Structured data should use specific Google-supported types and properties.
+*   Structured data should not be used for irrelevant content.
+*   Structured data should not be used for reviews or ratings that are manipulated or not credible.
+*   Structured data should not be used for content that violates Google's content policies (e.g., illegal, hateful, sexually explicit).
+*   Google may take manual action against sites that violate these guidelines.
+*   Violations can result in structured data not being shown in search results.
+
 Sources: https://developers.google.com/search/docs/appearance/structured-data/sd-policies
```

## Decision (2026-10-31)

No lever moves. Google's structured-data rules (true to the visible page, current, no manipulated ratings) are unchanged in substance and are what the site's schema already keeps - the FAQPage answers are the visible FAQ text, prices carry an 'as of' date.
