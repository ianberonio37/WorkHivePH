# SQL Migration Pattern Mining Report

- Files scanned: **614**
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
| `filename_dated` | 100% | 614 / 614 |
| `has_header_comment` | 99% | 613 / 614 |
| `targets_public_schema` | 86% | 531 / 614 |
| `uses_create_or_replace` | 53% | 329 / 614 |
| `creates_function` | 45% | 280 / 614 |
| `uses_security_definer` | 41% | 253 / 614 |
| `sets_search_path` | 40% | 248 / 614 |
| `drops_before_create` | 36% | 224 / 614 |
| `uses_created_at_col` | 30% | 187 / 614 |
| `wraps_in_transaction` | 23% | 143 / 614 |
| `uses_create_if_not_exists` | 21% | 133 / 614 |
| `creates_index` | 21% | 133 / 614 |
| `creates_policy` | 20% | 123 / 614 |
| `uses_updated_at_col` | 18% | 116 / 614 |
| `creates_trigger` | 17% | 110 / 614 |
| `declares_foreign_key` | 14% | 89 / 614 |
| `enables_rls` | 13% | 85 / 614 |
| `has_on_delete_clause` | 13% | 84 / 614 |
| `has_banner_header` | 13% | 82 / 614 |
| `uses_uuid_pk` | 10% | 67 / 614 |
| `has_comment_on_column` | 7% | 45 / 614 |
| `has_comment_on_table` | 6% | 42 / 614 |