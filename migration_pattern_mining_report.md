# SQL Migration Pattern Mining Report

- Files scanned: **483**
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
| `filename_dated` | 100% | 483 / 483 |
| `has_header_comment` | 99% | 482 / 483 |
| `targets_public_schema` | 83% | 405 / 483 |
| `uses_create_or_replace` | 50% | 244 / 483 |
| `creates_function` | 43% | 209 / 483 |
| `drops_before_create` | 39% | 190 / 483 |
| `uses_security_definer` | 37% | 183 / 483 |
| `sets_search_path` | 37% | 179 / 483 |
| `uses_created_at_col` | 32% | 158 / 483 |
| `wraps_in_transaction` | 27% | 131 / 483 |
| `creates_index` | 26% | 126 / 483 |
| `uses_create_if_not_exists` | 25% | 125 / 483 |
| `creates_policy` | 23% | 111 / 483 |
| `uses_updated_at_col` | 19% | 96 / 483 |
| `creates_trigger` | 18% | 88 / 483 |
| `declares_foreign_key` | 16% | 80 / 483 |
| `enables_rls` | 15% | 77 / 483 |
| `has_on_delete_clause` | 15% | 75 / 483 |
| `has_banner_header` | 14% | 72 / 483 |
| `uses_uuid_pk` | 12% | 62 / 483 |
| `has_comment_on_table` | 7% | 36 / 483 |
| `has_comment_on_column` | 7% | 36 / 483 |