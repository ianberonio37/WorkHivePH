# Validator Pattern Mining Report (Meta)

- Files scanned: **204** validate_*.py
- Features extracted: **20**
- Promotion threshold (homogeneous cluster): >= 90% conformance, <= 12 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outlier count |
|---|---:|---:|
| `has_main_guard` | 98% | 4 |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_cp1252_stdout_guard` | 100% | 204 / 204 |
| `has_main_guard` | 98% | 200 / 204 |
| `defines_main` | 89% | 182 / 204 |
| `has_module_docstring` | 88% | 181 / 204 |
| `writes_report_json` | 88% | 180 / 204 |
| `mentions_layer_structure` | 77% | 159 / 204 |
| `has_check_names_const` | 72% | 148 / 204 |
| `has_check_labels_const` | 72% | 147 / 204 |
| `prints_header_banner` | 70% | 144 / 204 |
| `imports_validator_utils` | 68% | 139 / 204 |
| `imports_format_result` | 67% | 138 / 204 |
| `calls_format_result` | 67% | 138 / 204 |
| `imports_read_file` | 62% | 127 / 204 |
| `uses_future_annotations` | 49% | 100 / 204 |
| `mentions_skills_consulted` | 37% | 76 / 204 |
| `main_exits_with_code` | 20% | 41 / 204 |
| `returns_1_on_fail` | 15% | 31 / 204 |
| `returns_0_on_success` | 11% | 23 / 204 |
| `imports_wh_pages` | 3% | 7 / 204 |
| `has_allowlist_constant` | 1% | 2 / 204 |