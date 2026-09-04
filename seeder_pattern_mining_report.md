# Seeder Pattern Mining Report

- Files scanned: **43**
- Features extracted: **19**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outliers |
|---|---:|---|
| `accepts_client_param` | 90% | ai_reports.py, cmms.py, cmms_demo.py, cmms_webhook.py |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_module_docstring` | 100% | 43 / 43 |
| `accepts_client_param` | 90% | 39 / 43 |
| `calls_table_dot` | 62% | 27 / 43 |
| `has_module_constants` | 62% | 27 / 43 |
| `uses_datetime` | 58% | 25 / 43 |
| `uses_random_module` | 55% | 24 / 43 |
| `has_try_except` | 55% | 24 / 43 |
| `calls_insert` | 41% | 18 / 43 |
| `mentions_reseed` | 20% | 9 / 43 |
| `scopes_query_to_hive` | 20% | 9 / 43 |
| `calls_delete` | 14% | 6 / 43 |
| `calls_upsert` | 11% | 5 / 43 |
| `uses_on_conflict` | 11% | 5 / 43 |
| `accepts_hive_id_param` | 11% | 5 / 43 |
| `has_main_guard` | 2% | 1 / 43 |
| `has_print_progress` | 2% | 1 / 43 |
| `defines_seed_function` | 0% | 0 / 43 |
| `defines_main_function` | 0% | 0 / 43 |
| `has_cp1252_guard` | 0% | 0 / 43 |