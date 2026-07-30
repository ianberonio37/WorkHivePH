# SQL Migration Pattern Mining Report

- Files scanned: **449**
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
| `filename_dated` | 100% | 449 / 449 |
| `has_header_comment` | 99% | 448 / 449 |
| `targets_public_schema` | 82% | 371 / 449 |
| `uses_create_or_replace` | 49% | 222 / 449 |
| `creates_function` | 42% | 189 / 449 |
| `drops_before_create` | 40% | 181 / 449 |
| `uses_security_definer` | 36% | 163 / 449 |
| `sets_search_path` | 35% | 159 / 449 |
| `uses_created_at_col` | 33% | 151 / 449 |
| `wraps_in_transaction` | 27% | 125 / 449 |
| `uses_create_if_not_exists` | 27% | 122 / 449 |
| `creates_index` | 27% | 122 / 449 |
| `creates_policy` | 24% | 109 / 449 |
| `uses_updated_at_col` | 19% | 86 / 449 |
| `creates_trigger` | 18% | 81 / 449 |
| `declares_foreign_key` | 17% | 77 / 449 |
| `enables_rls` | 16% | 74 / 449 |
| `has_banner_header` | 16% | 72 / 449 |
| `has_on_delete_clause` | 16% | 72 / 449 |
| `uses_uuid_pk` | 13% | 60 / 449 |
| `has_comment_on_table` | 7% | 33 / 449 |
| `has_comment_on_column` | 7% | 33 / 449 |