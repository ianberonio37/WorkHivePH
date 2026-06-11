# SQL Migration Pattern Mining Report

- Files scanned: **212**
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
| `filename_dated` | 100% | 212 / 212 |
| `has_header_comment` | 99% | 210 / 212 |
| `targets_public_schema` | 71% | 151 / 212 |
| `uses_created_at_col` | 47% | 101 / 212 |
| `uses_create_if_not_exists` | 46% | 98 / 212 |
| `creates_index` | 46% | 98 / 212 |
| `uses_create_or_replace` | 39% | 84 / 212 |
| `wraps_in_transaction` | 38% | 82 / 212 |
| `drops_before_create` | 34% | 74 / 212 |
| `declares_foreign_key` | 30% | 65 / 212 |
| `has_on_delete_clause` | 29% | 63 / 212 |
| `creates_function` | 29% | 63 / 212 |
| `creates_policy` | 28% | 61 / 212 |
| `enables_rls` | 25% | 55 / 212 |
| `uses_security_definer` | 24% | 52 / 212 |
| `uses_uuid_pk` | 24% | 52 / 212 |
| `sets_search_path` | 22% | 48 / 212 |
| `uses_updated_at_col` | 18% | 40 / 212 |
| `has_comment_on_table` | 12% | 26 / 212 |
| `creates_trigger` | 9% | 19 / 212 |
| `has_comment_on_column` | 6% | 13 / 212 |
| `has_banner_header` | 4% | 10 / 212 |