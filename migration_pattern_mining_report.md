# SQL Migration Pattern Mining Report

- Files scanned: **549**
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
| `filename_dated` | 100% | 549 / 549 |
| `has_header_comment` | 99% | 548 / 549 |
| `targets_public_schema` | 85% | 470 / 549 |
| `uses_create_or_replace` | 52% | 290 / 549 |
| `creates_function` | 46% | 253 / 549 |
| `uses_security_definer` | 41% | 229 / 549 |
| `sets_search_path` | 40% | 223 / 549 |
| `drops_before_create` | 38% | 210 / 549 |
| `uses_created_at_col` | 30% | 169 / 549 |
| `wraps_in_transaction` | 25% | 137 / 549 |
| `uses_create_if_not_exists` | 24% | 132 / 549 |
| `creates_index` | 23% | 131 / 549 |
| `creates_policy` | 21% | 119 / 549 |
| `uses_updated_at_col` | 18% | 102 / 549 |
| `creates_trigger` | 18% | 101 / 549 |
| `declares_foreign_key` | 15% | 86 / 549 |
| `enables_rls` | 15% | 85 / 549 |
| `has_banner_header` | 14% | 82 / 549 |
| `has_on_delete_clause` | 14% | 81 / 549 |
| `uses_uuid_pk` | 12% | 67 / 549 |
| `has_comment_on_table` | 7% | 42 / 549 |
| `has_comment_on_column` | 7% | 41 / 549 |