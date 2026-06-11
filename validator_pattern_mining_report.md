# Validator Pattern Mining Report (Meta)

- Files scanned: **337** validate_*.py
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
| `has_cp1252_stdout_guard` | 99% | 334 / 337 |
| `has_main_guard` | 98% | 333 / 337 |
| `defines_main` | 93% | 315 / 337 |
| `has_module_docstring` | 92% | 312 / 337 |
| `has_check_names_const` | 77% | 262 / 337 |
| `writes_report_json` | 77% | 262 / 337 |
| `uses_future_annotations` | 67% | 227 / 337 |
| `imports_validator_utils` | 54% | 183 / 337 |
| `imports_format_result` | 54% | 182 / 337 |
| `calls_format_result` | 54% | 182 / 337 |
| `has_check_labels_const` | 51% | 172 / 337 |
| `main_exits_with_code` | 50% | 170 / 337 |
| `mentions_layer_structure` | 50% | 169 / 337 |
| `imports_read_file` | 49% | 168 / 337 |
| `returns_1_on_fail` | 46% | 156 / 337 |
| `prints_header_banner` | 44% | 149 / 337 |
| `returns_0_on_success` | 32% | 110 / 337 |
| `mentions_skills_consulted` | 22% | 76 / 337 |
| `imports_wh_pages` | 2% | 7 / 337 |
| `has_allowlist_constant` | 1% | 4 / 337 |