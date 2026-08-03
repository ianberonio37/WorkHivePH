# SQL Migration Pattern Mining Report

- Files scanned: **518**
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
| `filename_dated` | 100% | 518 / 518 |
| `has_header_comment` | 99% | 517 / 518 |
| `targets_public_schema` | 84% | 439 / 518 |
| `uses_create_or_replace` | 52% | 271 / 518 |
| `creates_function` | 45% | 236 / 518 |
| `uses_security_definer` | 40% | 210 / 518 |
| `sets_search_path` | 39% | 206 / 518 |
| `drops_before_create` | 38% | 201 / 518 |
| `uses_created_at_col` | 32% | 166 / 518 |
| `wraps_in_transaction` | 25% | 131 / 518 |
| `uses_create_if_not_exists` | 24% | 129 / 518 |
| `creates_index` | 24% | 129 / 518 |
| `creates_policy` | 22% | 116 / 518 |
| `uses_updated_at_col` | 19% | 99 / 518 |
| `creates_trigger` | 18% | 96 / 518 |
| `declares_foreign_key` | 16% | 83 / 518 |
| `enables_rls` | 15% | 81 / 518 |
| `has_banner_header` | 15% | 80 / 518 |
| `has_on_delete_clause` | 15% | 78 / 518 |
| `uses_uuid_pk` | 12% | 65 / 518 |
| `has_comment_on_table` | 7% | 39 / 518 |
| `has_comment_on_column` | 7% | 39 / 518 |