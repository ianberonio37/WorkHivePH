# JS Shared Module Pattern Mining Report

- Files scanned: **25** (1 excluded: ['sw.js'])
- Features extracted: **16**
- Promotion threshold (small cluster): >= 85% conformance, <= 3 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outliers |
|---|---:|---|
| `wraps_in_iife` | 88% | drawing-symbols.js, skill-content.js, utils.js |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `wraps_in_iife` | 88% | 22 / 25 |
| `exports_via_window` | 80% | 20 / 25 |
| `has_try_catch` | 76% | 19 / 25 |
| `uses_wh_namespace` | 64% | 16 / 25 |
| `uses_strict_mode` | 52% | 13 / 25 |
| `has_idempotent_guard` | 52% | 13 / 25 |
| `uses_localstorage` | 48% | 12 / 25 |
| `listens_dom_ready` | 36% | 9 / 25 |
| `has_jsdoc_header` | 32% | 8 / 25 |
| `has_capability_tag` | 32% | 8 / 25 |
| `has_any_console_log` | 32% | 8 / 25 |
| `logs_with_module_prefix` | 16% | 4 / 25 |
| `uses_eschtml` | 12% | 3 / 25 |
| `calls_create_client` | 12% | 3 / 25 |
| `injects_script_tag` | 8% | 2 / 25 |
| `uses_get_db` | 4% | 1 / 25 |
