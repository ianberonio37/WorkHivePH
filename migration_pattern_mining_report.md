# SQL Migration Pattern Mining Report

- Files scanned: **593**
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
| `filename_dated` | 100% | 593 / 593 |
| `has_header_comment` | 99% | 592 / 593 |
| `targets_public_schema` | 86% | 511 / 593 |
| `uses_create_or_replace` | 54% | 321 / 593 |
| `creates_function` | 46% | 275 / 593 |
| `uses_security_definer` | 42% | 249 / 593 |
| `sets_search_path` | 41% | 243 / 593 |
| `drops_before_create` | 37% | 221 / 593 |
| `uses_created_at_col` | 30% | 180 / 593 |
| `wraps_in_transaction` | 23% | 140 / 593 |
| `uses_create_if_not_exists` | 22% | 132 / 593 |
| `creates_index` | 22% | 132 / 593 |
| `creates_policy` | 20% | 122 / 593 |
| `uses_updated_at_col` | 18% | 111 / 593 |
| `creates_trigger` | 18% | 108 / 593 |
| `declares_foreign_key` | 14% | 87 / 593 |
| `enables_rls` | 14% | 85 / 593 |
| `has_banner_header` | 13% | 82 / 593 |
| `has_on_delete_clause` | 13% | 82 / 593 |
| `uses_uuid_pk` | 11% | 67 / 593 |
| `has_comment_on_table` | 7% | 42 / 593 |
| `has_comment_on_column` | 7% | 42 / 593 |