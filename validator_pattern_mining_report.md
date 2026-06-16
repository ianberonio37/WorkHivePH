# Validator Pattern Mining Report (Meta)

- Files scanned: **339** validate_*.py
- Features extracted: **20**
- Promotion threshold (homogeneous cluster): >= 90% conformance, <= 12 outliers
- Promotion candidates: **2**

## Promotion candidates

| Feature | Conformance | Outlier count |
|---|---:|---:|
| `has_cp1252_stdout_guard` | 99% | 3 |
| `has_main_guard` | 98% | 4 |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_cp1252_stdout_guard` | 99% | 336 / 339 |
| `has_main_guard` | 98% | 335 / 339 |
| `defines_main` | 93% | 316 / 339 |
| `has_module_docstring` | 92% | 314 / 339 |
| `has_check_names_const` | 77% | 264 / 339 |
| `writes_report_json` | 77% | 264 / 339 |
| `uses_future_annotations` | 67% | 227 / 339 |
| `imports_validator_utils` | 54% | 185 / 339 |
| `imports_format_result` | 54% | 184 / 339 |
| `calls_format_result` | 54% | 184 / 339 |
| `has_check_labels_const` | 51% | 174 / 339 |
| `main_exits_with_code` | 50% | 171 / 339 |
| `mentions_layer_structure` | 49% | 169 / 339 |
| `imports_read_file` | 49% | 168 / 339 |
| `returns_1_on_fail` | 46% | 157 / 339 |
| `prints_header_banner` | 44% | 150 / 339 |
| `returns_0_on_success` | 32% | 111 / 339 |
| `mentions_skills_consulted` | 22% | 76 / 339 |
| `imports_wh_pages` | 2% | 7 / 339 |
| `has_allowlist_constant` | 1% | 4 / 339 |