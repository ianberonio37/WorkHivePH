# SQL Migration Pattern Mining Report

- Files scanned: **454**
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
| `filename_dated` | 100% | 454 / 454 |
| `has_header_comment` | 99% | 453 / 454 |
| `targets_public_schema` | 82% | 376 / 454 |
| `uses_create_or_replace` | 50% | 227 / 454 |
| `creates_function` | 42% | 193 / 454 |
| `drops_before_create` | 39% | 181 / 454 |
| `uses_security_definer` | 36% | 167 / 454 |
| `sets_search_path` | 35% | 163 / 454 |
| `uses_created_at_col` | 33% | 153 / 454 |
| `wraps_in_transaction` | 27% | 126 / 454 |
| `uses_create_if_not_exists` | 26% | 122 / 454 |
| `creates_index` | 26% | 122 / 454 |
| `creates_policy` | 23% | 108 / 454 |
| `uses_updated_at_col` | 18% | 86 / 454 |
| `creates_trigger` | 17% | 81 / 454 |
| `declares_foreign_key` | 17% | 77 / 454 |
| `enables_rls` | 16% | 74 / 454 |
| `has_banner_header` | 15% | 72 / 454 |
| `has_on_delete_clause` | 15% | 72 / 454 |
| `uses_uuid_pk` | 13% | 60 / 454 |
| `has_comment_on_table` | 7% | 33 / 454 |
| `has_comment_on_column` | 7% | 33 / 454 |