# HTML Page Pattern Mining Report

- Pages scanned: **42** (backups + test pages excluded)
- Features extracted: **40**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **2**

## Promotion candidates (sweet spot)

Emergent conventions ready to graduate. For each: decide if the
outliers are real gaps or legitimate exceptions for that page type.

| Feature | Conformance | Outliers |
|---|---:|---|
| `loads_utils_js` | 90% | architecture.html, promo-poster.html, symbol-gallery.html, validator-catalog.html |
| `has_main_landmark` | 90% | design-system.html, platform-actions.html, promo-poster.html, status.html |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_doctype_html` | 100% | 42 / 42 |
| `has_lang_attr` | 100% | 42 / 42 |
| `has_meta_charset` | 100% | 42 / 42 |
| `has_meta_viewport` | 100% | 42 / 42 |
| `has_title_tag` | 100% | 42 / 42 |
| `has_h1` | 100% | 42 / 42 |
| `loads_utils_js` | 90% | 38 / 42 |
| `has_main_landmark` | 90% | 38 / 42 |
| `has_meta_description` | 83% | 35 / 42 |
| `has_manifest_link` | 83% | 35 / 42 |
| `loads_offline_banner_js` | 83% | 35 / 42 |
| `loads_supabase_cdn` | 83% | 35 / 42 |
| `calls_eschtml` | 76% | 32 / 42 |
| `loads_nav_hub_js` | 73% | 31 / 42 |
| `has_og_title` | 71% | 30 / 42 |
| `has_og_image` | 71% | 30 / 42 |
| `has_canonical_link` | 66% | 28 / 42 |
| `has_details_toggle` | 64% | 27 / 42 |
| `has_meta_robots` | 57% | 24 / 42 |
| `has_empty_state_anchor` | 57% | 24 / 42 |
| `has_verdict_card` | 45% | 19 / 42 |
| `uses_eschtml_binding` | 33% | 14 / 42 |
| `loads_wh_capture_validate` | 14% | 6 / 42 |
| `validates_hive_membership` | 14% | 6 / 42 |
| `has_source_chip` | 9% | 4 / 42 |
| `has_og_description` | 7% | 3 / 42 |
| `has_twitter_card` | 7% | 3 / 42 |
| `has_jsonld_schema` | 7% | 3 / 42 |
| `loads_maturity_gate_js` | 7% | 3 / 42 |
| `loads_wh_persona_js` | 4% | 2 / 42 |
| `has_theme_color` | 2% | 1 / 42 |
| `loads_wh_ga4_js` | 2% | 1 / 42 |
| `loads_wh_help_js` | 2% | 1 / 42 |
| `loads_wh_tts_js` | 2% | 1 / 42 |
| `registers_service_worker` | 2% | 1 / 42 |
| `loads_floating_ai_js` | 0% | 0 / 42 |
| `loads_search_overlay_js` | 0% | 0 / 42 |
| `uses_createclient` | 0% | 0 / 42 |
| `handles_signin_redirect` | 0% | 0 / 42 |
| `uses_tailwind_cdn` | 0% | 0 / 42 |

## How to act on this report

1. Open a promotion candidate.
2. Look at the outlier pages -- are they legit exceptions for their page type
   (e.g., marketplace checkout doesn't need a verdict card)?
3a. **Real rule, real gaps** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Page-type-specific rule** -> write the validator with the outlier pages allowlisted.
3c. **Accidental pattern** -> drop it; not a real rule.
