# SQL Migration Pattern Mining Report

- Files scanned: **506**
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
| `filename_dated` | 100% | 506 / 506 |
| `has_header_comment` | 99% | 505 / 506 |
| `targets_public_schema` | 84% | 428 / 506 |
| `uses_create_or_replace` | 51% | 262 / 506 |
| `creates_function` | 44% | 227 / 506 |
| `uses_security_definer` | 39% | 201 / 506 |
| `sets_search_path` | 38% | 197 / 506 |
| `drops_before_create` | 38% | 196 / 506 |
| `uses_created_at_col` | 32% | 164 / 506 |
| `wraps_in_transaction` | 25% | 131 / 506 |
| `uses_create_if_not_exists` | 25% | 128 / 506 |
| `creates_index` | 25% | 127 / 506 |
| `creates_policy` | 22% | 114 / 506 |
| `uses_updated_at_col` | 19% | 97 / 506 |
| `creates_trigger` | 18% | 92 / 506 |
| `declares_foreign_key` | 16% | 81 / 506 |
| `enables_rls` | 15% | 80 / 506 |
| `has_on_delete_clause` | 15% | 76 / 506 |
| `has_banner_header` | 14% | 72 / 506 |
| `uses_uuid_pk` | 12% | 64 / 506 |
| `has_comment_on_table` | 7% | 39 / 506 |
| `has_comment_on_column` | 7% | 37 / 506 |