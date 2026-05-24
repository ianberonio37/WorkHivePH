# HTML Page Pattern Mining Report

- Pages scanned: **37** (backups + test pages excluded)
- Features extracted: **40**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **11**

## Promotion candidates (sweet spot)

Emergent conventions ready to graduate. For each: decide if the
outliers are real gaps or legitimate exceptions for that page type.

| Feature | Conformance | Outliers |
|---|---:|---|
| `has_main_landmark` | 97% | agentic-rag-observability.html |
| `has_meta_description` | 91% | architecture.html, marketplace-admin.html, symbol-gallery.html |
| `has_manifest_link` | 91% | architecture.html, parts-tracker.html, symbol-gallery.html |
| `loads_utils_js` | 91% | architecture.html, parts-tracker.html, symbol-gallery.html |
| `loads_supabase_cdn` | 91% | architecture.html, parts-tracker.html, symbol-gallery.html |
| `uses_createclient` | 89% | architecture.html, index.html, parts-tracker.html, symbol-gallery.html |
| `has_canonical_link` | 83% | architecture.html, founder-console.html, marketplace-admin.html, marketplace-seller-profile.html, parts-tracker.html, symbol-gallery.html |
| `has_og_title` | 83% | agentic-rag-observability.html, architecture.html, founder-console.html, marketplace-admin.html, parts-tracker.html, symbol-gallery.html |
| `has_og_image` | 83% | agentic-rag-observability.html, architecture.html, founder-console.html, marketplace-admin.html, parts-tracker.html, symbol-gallery.html |
| `loads_nav_hub_js` | 83% | agentic-rag-observability.html, architecture.html, founder-console.html, parts-tracker.html, platform-health.html, symbol-gallery.html |
| `calls_eschtml` | 83% | alert-hub.html, architecture.html, parts-tracker.html, project-report.html, shift-brain.html, symbol-gallery.html |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_doctype_html` | 100% | 37 / 37 |
| `has_lang_attr` | 100% | 37 / 37 |
| `has_meta_charset` | 100% | 37 / 37 |
| `has_meta_viewport` | 100% | 37 / 37 |
| `has_title_tag` | 100% | 37 / 37 |
| `has_main_landmark` | 97% | 36 / 37 |
| `has_meta_description` | 91% | 34 / 37 |
| `has_manifest_link` | 91% | 34 / 37 |
| `loads_utils_js` | 91% | 34 / 37 |
| `loads_supabase_cdn` | 91% | 34 / 37 |
| `uses_createclient` | 89% | 33 / 37 |
| `has_canonical_link` | 83% | 31 / 37 |
| `has_og_title` | 83% | 31 / 37 |
| `has_og_image` | 83% | 31 / 37 |
| `loads_nav_hub_js` | 83% | 31 / 37 |
| `calls_eschtml` | 83% | 31 / 37 |
| `has_h1` | 75% | 28 / 37 |
| `has_empty_state_anchor` | 67% | 25 / 37 |
| `has_theme_color` | 54% | 20 / 37 |
| `has_verdict_card` | 54% | 20 / 37 |
| `has_meta_robots` | 48% | 18 / 37 |
| `has_details_toggle` | 43% | 16 / 37 |
| `uses_eschtml_binding` | 29% | 11 / 37 |
| `loads_offline_banner_js` | 27% | 10 / 37 |
| `uses_tailwind_cdn` | 24% | 9 / 37 |
| `validates_hive_membership` | 16% | 6 / 37 |
| `loads_wh_capture_validate` | 13% | 5 / 37 |
| `loads_maturity_gate_js` | 10% | 4 / 37 |
| `has_og_description` | 8% | 3 / 37 |
| `has_twitter_card` | 8% | 3 / 37 |
| `has_jsonld_schema` | 8% | 3 / 37 |
| `has_source_chip` | 8% | 3 / 37 |
| `loads_wh_persona_js` | 5% | 2 / 37 |
| `loads_wh_ga4_js` | 2% | 1 / 37 |
| `loads_wh_help_js` | 2% | 1 / 37 |
| `loads_wh_tts_js` | 2% | 1 / 37 |
| `registers_service_worker` | 2% | 1 / 37 |
| `loads_floating_ai_js` | 0% | 0 / 37 |
| `loads_search_overlay_js` | 0% | 0 / 37 |
| `handles_signin_redirect` | 0% | 0 / 37 |

## How to act on this report

1. Open a promotion candidate.
2. Look at the outlier pages -- are they legit exceptions for their page type
   (e.g., marketplace checkout doesn't need a verdict card)?
3a. **Real rule, real gaps** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Page-type-specific rule** -> write the validator with the outlier pages allowlisted.
3c. **Accidental pattern** -> drop it; not a real rule.
