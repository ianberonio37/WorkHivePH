# Seeder Pattern Mining Report

- Files scanned: **42**
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
| `has_module_docstring` | 100% | 42 / 42 |
| `accepts_client_param` | 90% | 38 / 42 |
| `calls_table_dot` | 61% | 26 / 42 |
| `has_module_constants` | 61% | 26 / 42 |
| `uses_random_module` | 54% | 23 / 42 |
| `uses_datetime` | 54% | 23 / 42 |
| `has_try_except` | 50% | 21 / 42 |
| `calls_insert` | 38% | 16 / 42 |
| `mentions_reseed` | 21% | 9 / 42 |
| `scopes_query_to_hive` | 21% | 9 / 42 |
| `calls_delete` | 11% | 5 / 42 |
| `calls_upsert` | 11% | 5 / 42 |
| `uses_on_conflict` | 11% | 5 / 42 |
| `accepts_hive_id_param` | 11% | 5 / 42 |
| `has_main_guard` | 2% | 1 / 42 |
| `has_print_progress` | 2% | 1 / 42 |
| `defines_seed_function` | 0% | 0 / 42 |
| `defines_main_function` | 0% | 0 / 42 |
| `has_cp1252_guard` | 0% | 0 / 42 |