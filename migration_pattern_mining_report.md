# SQL Migration Pattern Mining Report

- Files scanned: **522**
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
| `filename_dated` | 100% | 522 / 522 |
| `has_header_comment` | 99% | 521 / 522 |
| `targets_public_schema` | 84% | 443 / 522 |
| `uses_create_or_replace` | 52% | 275 / 522 |
| `creates_function` | 46% | 240 / 522 |
| `uses_security_definer` | 41% | 214 / 522 |
| `sets_search_path` | 40% | 210 / 522 |
| `drops_before_create` | 38% | 201 / 522 |
| `uses_created_at_col` | 31% | 166 / 522 |
| `wraps_in_transaction` | 25% | 131 / 522 |
| `uses_create_if_not_exists` | 24% | 129 / 522 |
| `creates_index` | 24% | 129 / 522 |
| `creates_policy` | 22% | 116 / 522 |
| `uses_updated_at_col` | 19% | 100 / 522 |
| `creates_trigger` | 18% | 96 / 522 |
| `declares_foreign_key` | 15% | 83 / 522 |
| `has_banner_header` | 15% | 81 / 522 |
| `enables_rls` | 15% | 81 / 522 |
| `has_on_delete_clause` | 14% | 78 / 522 |
| `uses_uuid_pk` | 12% | 65 / 522 |
| `has_comment_on_table` | 7% | 39 / 522 |
| `has_comment_on_column` | 7% | 39 / 522 |