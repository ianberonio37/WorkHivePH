# Seeder Pattern Mining Report

- Files scanned: **40**
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
| `has_module_docstring` | 100% | 40 / 40 |
| `accepts_client_param` | 90% | 36 / 40 |
| `has_module_constants` | 65% | 26 / 40 |
| `calls_table_dot` | 57% | 23 / 40 |
| `uses_random_module` | 57% | 23 / 40 |
| `uses_datetime` | 52% | 21 / 40 |
| `has_try_except` | 40% | 16 / 40 |
| `calls_insert` | 37% | 15 / 40 |
| `scopes_query_to_hive` | 20% | 8 / 40 |
| `calls_delete` | 12% | 5 / 40 |
| `calls_upsert` | 10% | 4 / 40 |
| `mentions_reseed` | 10% | 4 / 40 |
| `uses_on_conflict` | 10% | 4 / 40 |
| `accepts_hive_id_param` | 10% | 4 / 40 |
| `has_main_guard` | 2% | 1 / 40 |
| `has_print_progress` | 2% | 1 / 40 |
| `defines_seed_function` | 0% | 0 / 40 |
| `defines_main_function` | 0% | 0 / 40 |
| `has_cp1252_guard` | 0% | 0 / 40 |