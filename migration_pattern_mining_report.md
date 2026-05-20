# SQL Migration Pattern Mining Report

- Files scanned: **177**
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
| `filename_dated` | 100% | 177 / 177 |
| `has_header_comment` | 99% | 176 / 177 |
| `targets_public_schema` | 65% | 116 / 177 |
| `uses_create_if_not_exists` | 49% | 87 / 177 |
| `creates_index` | 48% | 86 / 177 |
| `uses_created_at_col` | 47% | 84 / 177 |
| `uses_create_or_replace` | 37% | 66 / 177 |
| `drops_before_create` | 36% | 64 / 177 |
| `wraps_in_transaction` | 35% | 63 / 177 |
| `declares_foreign_key` | 31% | 56 / 177 |
| `has_on_delete_clause` | 30% | 54 / 177 |
| `creates_policy` | 29% | 52 / 177 |
| `creates_function` | 26% | 47 / 177 |
| `enables_rls` | 26% | 46 / 177 |
| `uses_uuid_pk` | 24% | 44 / 177 |
| `uses_security_definer` | 21% | 38 / 177 |
| `uses_updated_at_col` | 19% | 34 / 177 |
| `sets_search_path` | 18% | 32 / 177 |
| `has_comment_on_table` | 13% | 24 / 177 |
| `creates_trigger` | 9% | 17 / 177 |
| `has_comment_on_column` | 7% | 13 / 177 |
| `has_banner_header` | 3% | 6 / 177 |