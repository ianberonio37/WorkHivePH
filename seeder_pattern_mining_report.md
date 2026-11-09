# Seeder Pattern Mining Report

- Files scanned: **48**
- Features extracted: **19**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outliers |
|---|---:|---|
| `accepts_client_param` | 91% | ai_reports.py, cmms.py, cmms_demo.py, cmms_webhook.py |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_module_docstring` | 100% | 48 / 48 |
| `accepts_client_param` | 91% | 44 / 48 |
| `calls_table_dot` | 72% | 35 / 48 |
| `has_module_constants` | 64% | 31 / 48 |
| `has_try_except` | 60% | 29 / 48 |
| `uses_datetime` | 58% | 28 / 48 |
| `uses_random_module` | 54% | 26 / 48 |
| `calls_insert` | 43% | 21 / 48 |
| `mentions_reseed` | 27% | 13 / 48 |
| `scopes_query_to_hive` | 27% | 13 / 48 |
| `calls_delete` | 12% | 6 / 48 |
| `calls_upsert` | 12% | 6 / 48 |
| `uses_on_conflict` | 12% | 6 / 48 |
| `accepts_hive_id_param` | 12% | 6 / 48 |
| `has_main_guard` | 2% | 1 / 48 |
| `has_print_progress` | 2% | 1 / 48 |
| `defines_seed_function` | 0% | 0 / 48 |
| `defines_main_function` | 0% | 0 / 48 |
| `has_cp1252_guard` | 0% | 0 / 48 |