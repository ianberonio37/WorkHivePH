# HTML Page Pattern Mining Report

- Pages scanned: **40** (backups + test pages excluded)
- Features extracted: **40**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **6**

## Promotion candidates (sweet spot)

Emergent conventions ready to graduate. For each: decide if the
outliers are real gaps or legitimate exceptions for that page type.

| Feature | Conformance | Outliers |
|---|---:|---|
| `has_h1` | 95% | marketplace-seller-profile.html, marketplace-seller.html |
| `has_meta_description` | 92% | architecture.html, marketplace-admin.html, symbol-gallery.html |
| `loads_utils_js` | 90% | architecture.html, parts-tracker.html, symbol-gallery.html, validator-catalog.html |
| `loads_supabase_cdn` | 90% | architecture.html, parts-tracker.html, symbol-gallery.html, validator-catalog.html |
| `has_manifest_link` | 87% | architecture.html, llm-observability.html, parts-tracker.html, symbol-gallery.html, validator-catalog.html |
| `calls_eschtml` | 85% | alert-hub.html, architecture.html, parts-tracker.html, project-report.html, shift-brain.html, symbol-gallery.html |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_doctype_html` | 100% | 40 / 40 |
| `has_lang_attr` | 100% | 40 / 40 |
| `has_meta_charset` | 100% | 40 / 40 |
| `has_meta_viewport` | 100% | 40 / 40 |
| `has_title_tag` | 100% | 40 / 40 |
| `has_main_landmark` | 100% | 40 / 40 |
| `has_h1` | 95% | 38 / 40 |
| `has_meta_description` | 92% | 37 / 40 |
| `loads_utils_js` | 90% | 36 / 40 |
| `loads_supabase_cdn` | 90% | 36 / 40 |
| `has_manifest_link` | 87% | 35 / 40 |
| `calls_eschtml` | 85% | 34 / 40 |
| `uses_createclient` | 82% | 33 / 40 |
| `has_og_title` | 80% | 32 / 40 |
| `has_og_image` | 80% | 32 / 40 |
| `loads_nav_hub_js` | 80% | 32 / 40 |
| `has_canonical_link` | 77% | 31 / 40 |
| `has_empty_state_anchor` | 62% | 25 / 40 |
| `has_theme_color` | 52% | 21 / 40 |
| `has_verdict_card` | 52% | 21 / 40 |
| `has_meta_robots` | 47% | 19 / 40 |
| `has_details_toggle` | 42% | 17 / 40 |
| `uses_eschtml_binding` | 30% | 12 / 40 |
| `loads_offline_banner_js` | 25% | 10 / 40 |
| `uses_tailwind_cdn` | 22% | 9 / 40 |
| `loads_wh_capture_validate` | 15% | 6 / 40 |
| `validates_hive_membership` | 15% | 6 / 40 |
| `loads_maturity_gate_js` | 10% | 4 / 40 |
| `has_og_description` | 7% | 3 / 40 |
| `has_twitter_card` | 7% | 3 / 40 |
| `has_jsonld_schema` | 7% | 3 / 40 |
| `has_source_chip` | 7% | 3 / 40 |
| `loads_wh_persona_js` | 5% | 2 / 40 |
| `loads_wh_ga4_js` | 2% | 1 / 40 |
| `loads_wh_help_js` | 2% | 1 / 40 |
| `loads_wh_tts_js` | 2% | 1 / 40 |
| `registers_service_worker` | 2% | 1 / 40 |
| `loads_floating_ai_js` | 0% | 0 / 40 |
| `loads_search_overlay_js` | 0% | 0 / 40 |
| `handles_signin_redirect` | 0% | 0 / 40 |

## How to act on this report

1. Open a promotion candidate.
2. Look at the outlier pages -- are they legit exceptions for their page type
   (e.g., marketplace checkout doesn't need a verdict card)?
3a. **Real rule, real gaps** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Page-type-specific rule** -> write the validator with the outlier pages allowlisted.
3c. **Accidental pattern** -> drop it; not a real rule.
