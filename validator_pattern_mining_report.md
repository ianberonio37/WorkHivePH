# Validator Pattern Mining Report (Meta)

- Files scanned: **414** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 414 / 414 |
| `has_main_guard` | 99% | 410 / 414 |
| `defines_main` | 94% | 391 / 414 |
| `has_module_docstring` | 85% | 352 / 414 |
| `writes_report_json` | 73% | 306 / 414 |
| `has_check_names_const` | 68% | 284 / 414 |
| `uses_future_annotations` | 67% | 279 / 414 |
| `main_exits_with_code` | 58% | 244 / 414 |
| `returns_1_on_fail` | 53% | 221 / 414 |
| `imports_validator_utils` | 44% | 186 / 414 |
| `imports_format_result` | 44% | 185 / 414 |
| `calls_format_result` | 44% | 185 / 414 |
| `mentions_layer_structure` | 43% | 181 / 414 |
| `returns_0_on_success` | 43% | 179 / 414 |
| `has_check_labels_const` | 42% | 175 / 414 |
| `imports_read_file` | 40% | 169 / 414 |
| `prints_header_banner` | 37% | 154 / 414 |
| `mentions_skills_consulted` | 18% | 78 / 414 |
| `imports_wh_pages` | 1% | 7 / 414 |
| `has_allowlist_constant` | 1% | 4 / 414 |