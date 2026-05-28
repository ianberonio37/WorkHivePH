# SQL Migration Pattern Mining Report

- Files scanned: **188**
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
| `filename_dated` | 100% | 188 / 188 |
| `has_header_comment` | 99% | 187 / 188 |
| `targets_public_schema` | 67% | 127 / 188 |
| `uses_create_if_not_exists` | 49% | 93 / 188 |
| `creates_index` | 48% | 92 / 188 |
| `uses_created_at_col` | 46% | 88 / 188 |
| `drops_before_create` | 37% | 71 / 188 |
| `uses_create_or_replace` | 35% | 67 / 188 |
| `wraps_in_transaction` | 35% | 66 / 188 |
| `declares_foreign_key` | 33% | 62 / 188 |
| `has_on_delete_clause` | 31% | 60 / 188 |
| `creates_policy` | 30% | 58 / 188 |
| `enables_rls` | 27% | 52 / 188 |
| `uses_uuid_pk` | 26% | 49 / 188 |
| `creates_function` | 25% | 48 / 188 |
| `uses_security_definer` | 20% | 39 / 188 |
| `uses_updated_at_col` | 19% | 36 / 188 |
| `sets_search_path` | 18% | 34 / 188 |
| `has_comment_on_table` | 12% | 24 / 188 |
| `creates_trigger` | 9% | 17 / 188 |
| `has_comment_on_column` | 6% | 13 / 188 |
| `has_banner_header` | 3% | 6 / 188 |