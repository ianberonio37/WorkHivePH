# SQL Migration Pattern Mining Report

- Files scanned: **477**
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
| `filename_dated` | 100% | 477 / 477 |
| `has_header_comment` | 99% | 476 / 477 |
| `targets_public_schema` | 83% | 399 / 477 |
| `uses_create_or_replace` | 50% | 242 / 477 |
| `creates_function` | 43% | 208 / 477 |
| `drops_before_create` | 39% | 188 / 477 |
| `uses_security_definer` | 38% | 182 / 477 |
| `sets_search_path` | 37% | 178 / 477 |
| `uses_created_at_col` | 32% | 156 / 477 |
| `wraps_in_transaction` | 27% | 131 / 477 |
| `creates_index` | 26% | 126 / 477 |
| `uses_create_if_not_exists` | 26% | 125 / 477 |
| `creates_policy` | 23% | 110 / 477 |
| `uses_updated_at_col` | 19% | 94 / 477 |
| `creates_trigger` | 18% | 87 / 477 |
| `declares_foreign_key` | 16% | 80 / 477 |
| `enables_rls` | 16% | 77 / 477 |
| `has_on_delete_clause` | 15% | 75 / 477 |
| `has_banner_header` | 15% | 72 / 477 |
| `uses_uuid_pk` | 13% | 62 / 477 |
| `has_comment_on_column` | 7% | 36 / 477 |
| `has_comment_on_table` | 7% | 35 / 477 |