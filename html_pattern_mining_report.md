# HTML Page Pattern Mining Report

- Pages scanned: **38** (backups + test pages excluded)
- Features extracted: **40**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **7**

## Promotion candidates (sweet spot)

Emergent conventions ready to graduate. For each: decide if the
outliers are real gaps or legitimate exceptions for that page type.

| Feature | Conformance | Outliers |
|---|---:|---|
| `has_details_toggle` | 97% | promo-poster.html |
| `has_main_landmark` | 97% | promo-poster.html |
| `loads_utils_js` | 94% | offline-fallback.html, promo-poster.html |
| `loads_offline_banner_js` | 94% | offline-fallback.html, promo-poster.html |
| `has_meta_description` | 89% | marketplace-admin.html, offline-fallback.html, platform-actions.html, promo-poster.html |
| `has_manifest_link` | 89% | offline-fallback.html, platform-actions.html, promo-poster.html, status.html |
| `calls_eschtml` | 84% | alert-hub.html, engineering-design.html, offline-fallback.html, project-report.html, promo-poster.html, status.html |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_doctype_html` | 100% | 38 / 38 |
| `has_lang_attr` | 100% | 38 / 38 |
| `has_meta_charset` | 100% | 38 / 38 |
| `has_meta_viewport` | 100% | 38 / 38 |
| `has_title_tag` | 100% | 38 / 38 |
| `has_h1` | 100% | 38 / 38 |
| `has_details_toggle` | 97% | 37 / 38 |
| `has_main_landmark` | 97% | 37 / 38 |
| `loads_utils_js` | 94% | 36 / 38 |
| `loads_offline_banner_js` | 94% | 36 / 38 |
| `has_meta_description` | 89% | 34 / 38 |
| `has_manifest_link` | 89% | 34 / 38 |
| `calls_eschtml` | 84% | 32 / 38 |
| `has_og_title` | 81% | 31 / 38 |
| `loads_nav_hub_js` | 81% | 31 / 38 |
| `has_og_image` | 78% | 30 / 38 |
| `has_canonical_link` | 73% | 28 / 38 |
| `has_empty_state_anchor` | 63% | 24 / 38 |
| `has_meta_robots` | 55% | 21 / 38 |
| `has_verdict_card` | 50% | 19 / 38 |
| `uses_eschtml_binding` | 39% | 15 / 38 |
| `has_source_chip` | 36% | 14 / 38 |
| `has_og_description` | 15% | 6 / 38 |
| `loads_wh_capture_validate` | 15% | 6 / 38 |
| `validates_hive_membership` | 15% | 6 / 38 |
| `has_twitter_card` | 10% | 4 / 38 |
| `has_jsonld_schema` | 7% | 3 / 38 |
| `loads_maturity_gate_js` | 7% | 3 / 38 |
| `loads_wh_persona_js` | 5% | 2 / 38 |
| `has_theme_color` | 2% | 1 / 38 |
| `loads_wh_ga4_js` | 2% | 1 / 38 |
| `loads_wh_help_js` | 2% | 1 / 38 |
| `loads_wh_tts_js` | 2% | 1 / 38 |
| `registers_service_worker` | 2% | 1 / 38 |
| `loads_floating_ai_js` | 0% | 0 / 38 |
| `loads_search_overlay_js` | 0% | 0 / 38 |
| `loads_supabase_cdn` | 0% | 0 / 38 |
| `uses_createclient` | 0% | 0 / 38 |
| `handles_signin_redirect` | 0% | 0 / 38 |
| `uses_tailwind_cdn` | 0% | 0 / 38 |

## How to act on this report

1. Open a promotion candidate.
2. Look at the outlier pages -- are they legit exceptions for their page type
   (e.g., marketplace checkout doesn't need a verdict card)?
3a. **Real rule, real gaps** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Page-type-specific rule** -> write the validator with the outlier pages allowlisted.
3c. **Accidental pattern** -> drop it; not a real rule.
