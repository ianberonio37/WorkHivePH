# SQL Migration Pattern Mining Report

- Files scanned: **527**
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
| `filename_dated` | 100% | 527 / 527 |
| `has_header_comment` | 99% | 526 / 527 |
| `targets_public_schema` | 85% | 448 / 527 |
| `uses_create_or_replace` | 52% | 277 / 527 |
| `creates_function` | 45% | 241 / 527 |
| `uses_security_definer` | 40% | 215 / 527 |
| `sets_search_path` | 40% | 211 / 527 |
| `drops_before_create` | 38% | 203 / 527 |
| `uses_created_at_col` | 31% | 166 / 527 |
| `wraps_in_transaction` | 24% | 131 / 527 |
| `uses_create_if_not_exists` | 24% | 129 / 527 |
| `creates_index` | 24% | 129 / 527 |
| `creates_policy` | 22% | 117 / 527 |
| `uses_updated_at_col` | 19% | 100 / 527 |
| `creates_trigger` | 18% | 96 / 527 |
| `declares_foreign_key` | 15% | 83 / 527 |
| `has_banner_header` | 15% | 82 / 527 |
| `enables_rls` | 15% | 81 / 527 |
| `has_on_delete_clause` | 14% | 78 / 527 |
| `uses_uuid_pk` | 12% | 65 / 527 |
| `has_comment_on_table` | 7% | 39 / 527 |
| `has_comment_on_column` | 7% | 39 / 527 |