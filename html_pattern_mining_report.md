# HTML Page Pattern Mining Report

- Pages scanned: **39** (backups + test pages excluded)
- Features extracted: **40**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **6**

## Promotion candidates (sweet spot)

Emergent conventions ready to graduate. For each: decide if the
outliers are real gaps or legitimate exceptions for that page type.

| Feature | Conformance | Outliers |
|---|---:|---|
| `has_h1` | 94% | marketplace-seller-profile.html, marketplace-seller.html |
| `has_meta_description` | 92% | architecture.html, marketplace-admin.html, symbol-gallery.html |
| `loads_utils_js` | 92% | architecture.html, symbol-gallery.html, validator-catalog.html |
| `loads_supabase_cdn` | 92% | architecture.html, symbol-gallery.html, validator-catalog.html |
| `has_manifest_link` | 89% | architecture.html, llm-observability.html, symbol-gallery.html, validator-catalog.html |
| `calls_eschtml` | 89% | alert-hub.html, architecture.html, project-report.html, symbol-gallery.html |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_doctype_html` | 100% | 39 / 39 |
| `has_lang_attr` | 100% | 39 / 39 |
| `has_meta_charset` | 100% | 39 / 39 |
| `has_meta_viewport` | 100% | 39 / 39 |
| `has_title_tag` | 100% | 39 / 39 |
| `has_main_landmark` | 100% | 39 / 39 |
| `has_h1` | 94% | 37 / 39 |
| `has_meta_description` | 92% | 36 / 39 |
| `loads_utils_js` | 92% | 36 / 39 |
| `loads_supabase_cdn` | 92% | 36 / 39 |
| `has_manifest_link` | 89% | 35 / 39 |
| `calls_eschtml` | 89% | 35 / 39 |
| `has_og_title` | 82% | 32 / 39 |
| `has_og_image` | 82% | 32 / 39 |
| `loads_nav_hub_js` | 82% | 32 / 39 |
| `has_canonical_link` | 76% | 30 / 39 |
| `has_empty_state_anchor` | 64% | 25 / 39 |
| `has_meta_robots` | 59% | 23 / 39 |
| `has_theme_color` | 53% | 21 / 39 |
| `has_verdict_card` | 53% | 21 / 39 |
| `has_details_toggle` | 43% | 17 / 39 |
| `uses_eschtml_binding` | 30% | 12 / 39 |
| `loads_offline_banner_js` | 25% | 10 / 39 |
| `uses_tailwind_cdn` | 23% | 9 / 39 |
| `loads_wh_capture_validate` | 15% | 6 / 39 |
| `validates_hive_membership` | 15% | 6 / 39 |
| `loads_maturity_gate_js` | 10% | 4 / 39 |
| `has_og_description` | 7% | 3 / 39 |
| `has_twitter_card` | 7% | 3 / 39 |
| `has_jsonld_schema` | 7% | 3 / 39 |
| `has_source_chip` | 7% | 3 / 39 |
| `loads_wh_persona_js` | 5% | 2 / 39 |
| `loads_wh_ga4_js` | 2% | 1 / 39 |
| `loads_wh_help_js` | 2% | 1 / 39 |
| `loads_wh_tts_js` | 2% | 1 / 39 |
| `registers_service_worker` | 2% | 1 / 39 |
| `loads_floating_ai_js` | 0% | 0 / 39 |
| `loads_search_overlay_js` | 0% | 0 / 39 |
| `uses_createclient` | 0% | 0 / 39 |
| `handles_signin_redirect` | 0% | 0 / 39 |

## How to act on this report

1. Open a promotion candidate.
2. Look at the outlier pages -- are they legit exceptions for their page type
   (e.g., marketplace checkout doesn't need a verdict card)?
3a. **Real rule, real gaps** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Page-type-specific rule** -> write the validator with the outlier pages allowlisted.
3c. **Accidental pattern** -> drop it; not a real rule.
