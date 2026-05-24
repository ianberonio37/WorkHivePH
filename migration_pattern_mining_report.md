# SQL Migration Pattern Mining Report

- Files scanned: **179**
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
| `filename_dated` | 100% | 179 / 179 |
| `has_header_comment` | 99% | 178 / 179 |
| `targets_public_schema` | 65% | 118 / 179 |
| `uses_create_if_not_exists` | 48% | 87 / 179 |
| `creates_index` | 48% | 86 / 179 |
| `uses_created_at_col` | 46% | 84 / 179 |
| `uses_create_or_replace` | 36% | 66 / 179 |
| `drops_before_create` | 35% | 64 / 179 |
| `wraps_in_transaction` | 35% | 64 / 179 |
| `declares_foreign_key` | 31% | 57 / 179 |
| `has_on_delete_clause` | 30% | 55 / 179 |
| `creates_policy` | 29% | 52 / 179 |
| `creates_function` | 26% | 47 / 179 |
| `enables_rls` | 25% | 46 / 179 |
| `uses_uuid_pk` | 24% | 44 / 179 |
| `uses_security_definer` | 21% | 38 / 179 |
| `uses_updated_at_col` | 19% | 34 / 179 |
| `sets_search_path` | 18% | 33 / 179 |
| `has_comment_on_table` | 13% | 24 / 179 |
| `creates_trigger` | 9% | 17 / 179 |
| `has_comment_on_column` | 7% | 13 / 179 |
| `has_banner_header` | 3% | 6 / 179 |