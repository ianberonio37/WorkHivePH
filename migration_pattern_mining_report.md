# SQL Migration Pattern Mining Report

- Files scanned: **526**
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
| `filename_dated` | 100% | 526 / 526 |
| `has_header_comment` | 99% | 525 / 526 |
| `targets_public_schema` | 85% | 447 / 526 |
| `uses_create_or_replace` | 52% | 277 / 526 |
| `creates_function` | 45% | 241 / 526 |
| `uses_security_definer` | 40% | 215 / 526 |
| `sets_search_path` | 40% | 211 / 526 |
| `drops_before_create` | 38% | 202 / 526 |
| `uses_created_at_col` | 31% | 166 / 526 |
| `wraps_in_transaction` | 24% | 131 / 526 |
| `uses_create_if_not_exists` | 24% | 129 / 526 |
| `creates_index` | 24% | 129 / 526 |
| `creates_policy` | 22% | 116 / 526 |
| `uses_updated_at_col` | 19% | 100 / 526 |
| `creates_trigger` | 18% | 96 / 526 |
| `declares_foreign_key` | 15% | 83 / 526 |
| `has_banner_header` | 15% | 81 / 526 |
| `enables_rls` | 15% | 81 / 526 |
| `has_on_delete_clause` | 14% | 78 / 526 |
| `uses_uuid_pk` | 12% | 65 / 526 |
| `has_comment_on_table` | 7% | 39 / 526 |
| `has_comment_on_column` | 7% | 39 / 526 |