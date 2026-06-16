# SQL Migration Pattern Mining Report

- Files scanned: **219**
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
| `filename_dated` | 100% | 219 / 219 |
| `has_header_comment` | 99% | 217 / 219 |
| `targets_public_schema` | 69% | 153 / 219 |
| `uses_created_at_col` | 47% | 103 / 219 |
| `uses_create_if_not_exists` | 46% | 101 / 219 |
| `creates_index` | 46% | 101 / 219 |
| `uses_create_or_replace` | 38% | 85 / 219 |
| `wraps_in_transaction` | 37% | 82 / 219 |
| `drops_before_create` | 33% | 74 / 219 |
| `declares_foreign_key` | 29% | 65 / 219 |
| `creates_function` | 29% | 64 / 219 |
| `has_on_delete_clause` | 28% | 63 / 219 |
| `creates_policy` | 28% | 62 / 219 |
| `enables_rls` | 25% | 56 / 219 |
| `uses_uuid_pk` | 24% | 54 / 219 |
| `uses_security_definer` | 23% | 52 / 219 |
| `sets_search_path` | 21% | 48 / 219 |
| `uses_updated_at_col` | 18% | 41 / 219 |
| `has_comment_on_table` | 11% | 26 / 219 |
| `creates_trigger` | 8% | 19 / 219 |
| `has_comment_on_column` | 5% | 13 / 219 |
| `has_banner_header` | 4% | 10 / 219 |