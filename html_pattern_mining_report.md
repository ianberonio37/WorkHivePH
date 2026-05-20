# HTML Page Pattern Mining Report

- Pages scanned: **36** (backups + test pages excluded)
- Features extracted: **40**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **5**

## Promotion candidates (sweet spot)

Emergent conventions ready to graduate. For each: decide if the
outliers are real gaps or legitimate exceptions for that page type.

| Feature | Conformance | Outliers |
|---|---:|---|
| `has_manifest_link` | 91% | architecture.html, parts-tracker.html, symbol-gallery.html |
| `loads_utils_js` | 91% | architecture.html, parts-tracker.html, symbol-gallery.html |
| `loads_supabase_cdn` | 91% | architecture.html, parts-tracker.html, symbol-gallery.html |
| `uses_createclient` | 88% | architecture.html, index.html, parts-tracker.html, symbol-gallery.html |
| `loads_nav_hub_js` | 86% | architecture.html, founder-console.html, parts-tracker.html, platform-health.html, symbol-gallery.html |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_doctype_html` | 100% | 36 / 36 |
| `has_lang_attr` | 100% | 36 / 36 |
| `has_meta_charset` | 100% | 36 / 36 |
| `has_meta_viewport` | 100% | 36 / 36 |
| `has_title_tag` | 100% | 36 / 36 |
| `has_main_landmark` | 100% | 36 / 36 |
| `has_manifest_link` | 91% | 33 / 36 |
| `loads_utils_js` | 91% | 33 / 36 |
| `loads_supabase_cdn` | 91% | 33 / 36 |
| `uses_createclient` | 88% | 32 / 36 |
| `loads_nav_hub_js` | 86% | 31 / 36 |
| `calls_eschtml` | 80% | 29 / 36 |
| `has_h1` | 77% | 28 / 36 |
| `has_empty_state_anchor` | 66% | 24 / 36 |
| `has_meta_description` | 61% | 22 / 36 |
| `has_verdict_card` | 55% | 20 / 36 |
| `has_theme_color` | 52% | 19 / 36 |
| `has_meta_robots` | 50% | 18 / 36 |
| `has_details_toggle` | 44% | 16 / 36 |
| `has_canonical_link` | 38% | 14 / 36 |
| `uses_eschtml_binding` | 30% | 11 / 36 |
| `loads_offline_banner_js` | 27% | 10 / 36 |
| `uses_tailwind_cdn` | 25% | 9 / 36 |
| `validates_hive_membership` | 16% | 6 / 36 |
| `loads_wh_capture_validate` | 13% | 5 / 36 |
| `loads_maturity_gate_js` | 11% | 4 / 36 |
| `has_og_title` | 8% | 3 / 36 |
| `has_og_description` | 8% | 3 / 36 |
| `has_og_image` | 8% | 3 / 36 |
| `has_twitter_card` | 8% | 3 / 36 |
| `has_jsonld_schema` | 8% | 3 / 36 |
| `has_source_chip` | 8% | 3 / 36 |
| `loads_wh_persona_js` | 5% | 2 / 36 |
| `loads_wh_ga4_js` | 2% | 1 / 36 |
| `loads_wh_help_js` | 2% | 1 / 36 |
| `loads_wh_tts_js` | 2% | 1 / 36 |
| `registers_service_worker` | 2% | 1 / 36 |
| `loads_floating_ai_js` | 0% | 0 / 36 |
| `loads_search_overlay_js` | 0% | 0 / 36 |
| `handles_signin_redirect` | 0% | 0 / 36 |

## How to act on this report

1. Open a promotion candidate.
2. Look at the outlier pages -- are they legit exceptions for their page type
   (e.g., marketplace checkout doesn't need a verdict card)?
3a. **Real rule, real gaps** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Page-type-specific rule** -> write the validator with the outlier pages allowlisted.
3c. **Accidental pattern** -> drop it; not a real rule.
