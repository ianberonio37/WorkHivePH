# Validator Pattern Mining Report (Meta)

- Files scanned: **399** validate_*.py
- Features extracted: **20**
- Promotion threshold (homogeneous cluster): >= 90% conformance, <= 12 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outlier count |
|---|---:|---:|
| `has_main_guard` | 99% | 4 |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_cp1252_stdout_guard` | 100% | 399 / 399 |
| `has_main_guard` | 99% | 395 / 399 |
| `defines_main` | 94% | 376 / 399 |
| `has_module_docstring` | 87% | 349 / 399 |
| `writes_report_json` | 76% | 304 / 399 |
| `has_check_names_const` | 70% | 283 / 399 |
| `uses_future_annotations` | 67% | 270 / 399 |
| `main_exits_with_code` | 56% | 227 / 399 |
| `returns_1_on_fail` | 51% | 206 / 399 |
| `imports_validator_utils` | 46% | 186 / 399 |
| `imports_format_result` | 46% | 185 / 399 |
| `calls_format_result` | 46% | 185 / 399 |
| `mentions_layer_structure` | 45% | 181 / 399 |
| `has_check_labels_const` | 43% | 175 / 399 |
| `imports_read_file` | 42% | 169 / 399 |
| `returns_0_on_success` | 41% | 167 / 399 |
| `prints_header_banner` | 38% | 154 / 399 |
| `mentions_skills_consulted` | 19% | 78 / 399 |
| `imports_wh_pages` | 1% | 7 / 399 |
| `has_allowlist_constant` | 1% | 4 / 399 |