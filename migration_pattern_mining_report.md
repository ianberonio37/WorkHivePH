# SQL Migration Pattern Mining Report

- Files scanned: **176**
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
| `filename_dated` | 100% | 176 / 176 |
| `has_header_comment` | 99% | 175 / 176 |
| `targets_public_schema` | 65% | 115 / 176 |
| `uses_create_if_not_exists` | 49% | 87 / 176 |
| `creates_index` | 48% | 86 / 176 |
| `uses_created_at_col` | 47% | 84 / 176 |
| `uses_create_or_replace` | 37% | 66 / 176 |
| `drops_before_create` | 36% | 64 / 176 |
| `wraps_in_transaction` | 35% | 62 / 176 |
| `declares_foreign_key` | 31% | 56 / 176 |
| `has_on_delete_clause` | 30% | 54 / 176 |
| `creates_policy` | 29% | 52 / 176 |
| `creates_function` | 26% | 47 / 176 |
| `enables_rls` | 26% | 46 / 176 |
| `uses_uuid_pk` | 25% | 44 / 176 |
| `uses_security_definer` | 21% | 38 / 176 |
| `uses_updated_at_col` | 19% | 34 / 176 |
| `sets_search_path` | 18% | 32 / 176 |
| `has_comment_on_table` | 13% | 24 / 176 |
| `creates_trigger` | 9% | 17 / 176 |
| `has_comment_on_column` | 6% | 12 / 176 |
| `has_banner_header` | 3% | 6 / 176 |