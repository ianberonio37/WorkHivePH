# SQL Migration Pattern Mining Report

- Files scanned: **366**
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
| `filename_dated` | 100% | 366 / 366 |
| `has_header_comment` | 99% | 365 / 366 |
| `targets_public_schema` | 79% | 290 / 366 |
| `uses_create_or_replace` | 46% | 169 / 366 |
| `drops_before_create` | 39% | 146 / 366 |
| `creates_function` | 38% | 140 / 366 |
| `uses_created_at_col` | 36% | 133 / 366 |
| `uses_create_if_not_exists` | 31% | 116 / 366 |
| `uses_security_definer` | 31% | 115 / 366 |
| `creates_index` | 31% | 114 / 366 |
| `sets_search_path` | 30% | 111 / 366 |
| `wraps_in_transaction` | 29% | 109 / 366 |
| `creates_policy` | 26% | 97 / 366 |
| `enables_rls` | 19% | 70 / 366 |
| `declares_foreign_key` | 18% | 69 / 366 |
| `has_on_delete_clause` | 18% | 67 / 366 |
| `uses_updated_at_col` | 18% | 66 / 366 |
| `uses_uuid_pk` | 15% | 57 / 366 |
| `creates_trigger` | 15% | 56 / 366 |
| `has_banner_header` | 12% | 45 / 366 |
| `has_comment_on_table` | 7% | 28 / 366 |
| `has_comment_on_column` | 6% | 23 / 366 |