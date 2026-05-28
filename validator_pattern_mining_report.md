# Validator Pattern Mining Report (Meta)

- Files scanned: **311** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 311 / 311 |
| `has_main_guard` | 98% | 307 / 311 |
| `defines_main` | 92% | 289 / 311 |
| `has_module_docstring` | 92% | 287 / 311 |
| `writes_report_json` | 80% | 251 / 311 |
| `has_check_names_const` | 79% | 248 / 311 |
| `uses_future_annotations` | 66% | 206 / 311 |
| `imports_validator_utils` | 55% | 174 / 311 |
| `imports_format_result` | 55% | 173 / 311 |
| `calls_format_result` | 55% | 173 / 311 |
| `has_check_labels_const` | 53% | 167 / 311 |
| `mentions_layer_structure` | 53% | 165 / 311 |
| `imports_read_file` | 52% | 162 / 311 |
| `main_exits_with_code` | 47% | 148 / 311 |
| `prints_header_banner` | 46% | 144 / 311 |
| `returns_1_on_fail` | 44% | 138 / 311 |
| `returns_0_on_success` | 30% | 95 / 311 |
| `mentions_skills_consulted` | 24% | 76 / 311 |
| `imports_wh_pages` | 2% | 7 / 311 |
| `has_allowlist_constant` | 1% | 3 / 311 |