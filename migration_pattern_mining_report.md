# SQL Migration Pattern Mining Report

- Files scanned: **516**
- Features extracted: **22**
- Promotion threshold: >= 80% conformance, <= 8 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outlier count |
|---|---:|---:|
| `has_header_comment` | 99% | 1 |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `filename_dated` | 100% | 516 / 516 |
| `has_header_comment` | 99% | 515 / 516 |
| `targets_public_schema` | 84% | 437 / 516 |
| `uses_create_or_replace` | 52% | 269 / 516 |
| `creates_function` | 45% | 234 / 516 |
| `uses_security_definer` | 40% | 208 / 516 |
| `sets_search_path` | 39% | 204 / 516 |
| `drops_before_create` | 38% | 199 / 516 |
| `uses_created_at_col` | 32% | 165 / 516 |
| `wraps_in_transaction` | 25% | 131 / 516 |
| `uses_create_if_not_exists` | 24% | 128 / 516 |
| `creates_index` | 24% | 127 / 516 |
| `creates_policy` | 22% | 115 / 516 |
| `uses_updated_at_col` | 19% | 99 / 516 |
| `creates_trigger` | 18% | 94 / 516 |
| `declares_foreign_key` | 15% | 81 / 516 |
| `enables_rls` | 15% | 80 / 516 |
| `has_banner_header` | 15% | 78 / 516 |
| `has_on_delete_clause` | 14% | 76 / 516 |
| `uses_uuid_pk` | 12% | 64 / 516 |
| `has_comment_on_table` | 7% | 39 / 516 |
| `has_comment_on_column` | 7% | 39 / 516 |