# Validator Pattern Mining Report (Meta)

- Files scanned: **334** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 334 / 334 |
| `has_main_guard` | 98% | 330 / 334 |
| `defines_main` | 93% | 312 / 334 |
| `has_module_docstring` | 92% | 309 / 334 |
| `has_check_names_const` | 77% | 259 / 334 |
| `writes_report_json` | 77% | 259 / 334 |
| `uses_future_annotations` | 68% | 227 / 334 |
| `imports_validator_utils` | 53% | 180 / 334 |
| `imports_format_result` | 53% | 179 / 334 |
| `calls_format_result` | 53% | 179 / 334 |
| `main_exits_with_code` | 50% | 170 / 334 |
| `has_check_labels_const` | 50% | 169 / 334 |
| `imports_read_file` | 50% | 168 / 334 |
| `mentions_layer_structure` | 50% | 167 / 334 |
| `returns_1_on_fail` | 46% | 156 / 334 |
| `prints_header_banner` | 43% | 146 / 334 |
| `returns_0_on_success` | 32% | 110 / 334 |
| `mentions_skills_consulted` | 22% | 76 / 334 |
| `imports_wh_pages` | 2% | 7 / 334 |
| `has_allowlist_constant` | 1% | 4 / 334 |