# SQL Migration Pattern Mining Report

- Files scanned: **209**
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
| `filename_dated` | 100% | 209 / 209 |
| `has_header_comment` | 99% | 207 / 209 |
| `targets_public_schema` | 70% | 148 / 209 |
| `uses_created_at_col` | 47% | 99 / 209 |
| `uses_create_if_not_exists` | 46% | 98 / 209 |
| `creates_index` | 46% | 98 / 209 |
| `uses_create_or_replace` | 39% | 82 / 209 |
| `wraps_in_transaction` | 38% | 81 / 209 |
| `drops_before_create` | 35% | 74 / 209 |
| `declares_foreign_key` | 31% | 65 / 209 |
| `has_on_delete_clause` | 30% | 63 / 209 |
| `creates_function` | 29% | 62 / 209 |
| `creates_policy` | 29% | 61 / 209 |
| `enables_rls` | 26% | 55 / 209 |
| `uses_uuid_pk` | 24% | 52 / 209 |
| `uses_security_definer` | 24% | 51 / 209 |
| `sets_search_path` | 22% | 47 / 209 |
| `uses_updated_at_col` | 18% | 39 / 209 |
| `has_comment_on_table` | 12% | 26 / 209 |
| `creates_trigger` | 9% | 19 / 209 |
| `has_comment_on_column` | 6% | 13 / 209 |
| `has_banner_header` | 4% | 10 / 209 |