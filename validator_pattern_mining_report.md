# Validator Pattern Mining Report (Meta)

- Files scanned: **288** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 288 / 288 |
| `has_main_guard` | 98% | 284 / 288 |
| `defines_main` | 92% | 266 / 288 |
| `has_module_docstring` | 92% | 265 / 288 |
| `writes_report_json` | 83% | 239 / 288 |
| `has_check_names_const` | 81% | 236 / 288 |
| `uses_future_annotations` | 63% | 184 / 288 |
| `has_check_labels_const` | 57% | 167 / 288 |
| `mentions_layer_structure` | 56% | 164 / 288 |
| `imports_validator_utils` | 56% | 164 / 288 |
| `imports_format_result` | 56% | 163 / 288 |
| `calls_format_result` | 56% | 163 / 288 |
| `imports_read_file` | 52% | 152 / 288 |
| `prints_header_banner` | 50% | 144 / 288 |
| `main_exits_with_code` | 43% | 125 / 288 |
| `returns_1_on_fail` | 39% | 115 / 288 |
| `returns_0_on_success` | 28% | 82 / 288 |
| `mentions_skills_consulted` | 26% | 76 / 288 |
| `imports_wh_pages` | 2% | 7 / 288 |
| `has_allowlist_constant` | 0% | 2 / 288 |