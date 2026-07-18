# SQL Migration Pattern Mining Report

- Files scanned: **351**
- Features extracted: **22**
- Promotion threshold: >= 80% conformance, <= 8 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outlier count |
|---|---:|---:|
| `has_header_comment` | 99% | 2 |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `filename_dated` | 100% | 351 / 351 |
| `has_header_comment` | 99% | 349 / 351 |
| `targets_public_schema` | 78% | 275 / 351 |
| `uses_create_or_replace` | 46% | 164 / 351 |
| `drops_before_create` | 41% | 144 / 351 |
| `creates_function` | 38% | 136 / 351 |
| `uses_created_at_col` | 37% | 131 / 351 |
| `uses_create_if_not_exists` | 31% | 111 / 351 |
| `uses_security_definer` | 31% | 111 / 351 |
| `creates_index` | 31% | 110 / 351 |
| `wraps_in_transaction` | 31% | 109 / 351 |
| `sets_search_path` | 30% | 107 / 351 |
| `creates_policy` | 27% | 96 / 351 |
| `enables_rls` | 19% | 68 / 351 |
| `declares_foreign_key` | 19% | 67 / 351 |
| `has_on_delete_clause` | 18% | 65 / 351 |
| `uses_updated_at_col` | 18% | 65 / 351 |
| `uses_uuid_pk` | 16% | 56 / 351 |
| `creates_trigger` | 15% | 55 / 351 |
| `has_banner_header` | 12% | 45 / 351 |
| `has_comment_on_table` | 7% | 27 / 351 |
| `has_comment_on_column` | 5% | 20 / 351 |