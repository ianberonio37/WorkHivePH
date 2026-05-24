# SQL Migration Pattern Mining Report

- Files scanned: **187**
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
| `filename_dated` | 100% | 187 / 187 |
| `has_header_comment` | 99% | 186 / 187 |
| `targets_public_schema` | 67% | 126 / 187 |
| `uses_create_if_not_exists` | 49% | 92 / 187 |
| `creates_index` | 48% | 91 / 187 |
| `uses_created_at_col` | 46% | 87 / 187 |
| `drops_before_create` | 37% | 70 / 187 |
| `uses_create_or_replace` | 35% | 66 / 187 |
| `wraps_in_transaction` | 35% | 66 / 187 |
| `declares_foreign_key` | 33% | 62 / 187 |
| `has_on_delete_clause` | 32% | 60 / 187 |
| `creates_policy` | 30% | 57 / 187 |
| `enables_rls` | 27% | 51 / 187 |
| `uses_uuid_pk` | 26% | 49 / 187 |
| `creates_function` | 25% | 47 / 187 |
| `uses_security_definer` | 20% | 38 / 187 |
| `uses_updated_at_col` | 18% | 35 / 187 |
| `sets_search_path` | 17% | 33 / 187 |
| `has_comment_on_table` | 12% | 24 / 187 |
| `creates_trigger` | 9% | 17 / 187 |
| `has_comment_on_column` | 7% | 13 / 187 |
| `has_banner_header` | 3% | 6 / 187 |