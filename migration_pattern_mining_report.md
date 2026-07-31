# SQL Migration Pattern Mining Report

- Files scanned: **474**
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
| `filename_dated` | 100% | 474 / 474 |
| `has_header_comment` | 99% | 473 / 474 |
| `targets_public_schema` | 83% | 396 / 474 |
| `uses_create_or_replace` | 50% | 240 / 474 |
| `creates_function` | 43% | 206 / 474 |
| `drops_before_create` | 39% | 187 / 474 |
| `uses_security_definer` | 38% | 180 / 474 |
| `sets_search_path` | 37% | 176 / 474 |
| `uses_created_at_col` | 32% | 156 / 474 |
| `wraps_in_transaction` | 27% | 131 / 474 |
| `creates_index` | 26% | 126 / 474 |
| `uses_create_if_not_exists` | 26% | 125 / 474 |
| `creates_policy` | 23% | 110 / 474 |
| `uses_updated_at_col` | 19% | 93 / 474 |
| `creates_trigger` | 18% | 86 / 474 |
| `declares_foreign_key` | 16% | 80 / 474 |
| `enables_rls` | 16% | 77 / 474 |
| `has_on_delete_clause` | 15% | 75 / 474 |
| `has_banner_header` | 15% | 72 / 474 |
| `uses_uuid_pk` | 13% | 62 / 474 |
| `has_comment_on_table` | 7% | 35 / 474 |
| `has_comment_on_column` | 7% | 35 / 474 |