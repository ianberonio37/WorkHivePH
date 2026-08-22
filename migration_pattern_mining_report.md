# SQL Migration Pattern Mining Report

- Files scanned: **550**
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
| `filename_dated` | 100% | 550 / 550 |
| `has_header_comment` | 99% | 549 / 550 |
| `targets_public_schema` | 85% | 471 / 550 |
| `uses_create_or_replace` | 52% | 291 / 550 |
| `creates_function` | 46% | 253 / 550 |
| `uses_security_definer` | 41% | 229 / 550 |
| `sets_search_path` | 40% | 223 / 550 |
| `drops_before_create` | 38% | 210 / 550 |
| `uses_created_at_col` | 30% | 170 / 550 |
| `wraps_in_transaction` | 24% | 137 / 550 |
| `uses_create_if_not_exists` | 24% | 132 / 550 |
| `creates_index` | 23% | 131 / 550 |
| `creates_policy` | 21% | 119 / 550 |
| `uses_updated_at_col` | 18% | 103 / 550 |
| `creates_trigger` | 18% | 101 / 550 |
| `declares_foreign_key` | 15% | 86 / 550 |
| `enables_rls` | 15% | 85 / 550 |
| `has_banner_header` | 14% | 82 / 550 |
| `has_on_delete_clause` | 14% | 81 / 550 |
| `uses_uuid_pk` | 12% | 67 / 550 |
| `has_comment_on_table` | 7% | 42 / 550 |
| `has_comment_on_column` | 7% | 41 / 550 |