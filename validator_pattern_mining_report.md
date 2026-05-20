# Validator Pattern Mining Report (Meta)

- Files scanned: **229** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 229 / 229 |
| `has_main_guard` | 98% | 225 / 229 |
| `defines_main` | 90% | 207 / 229 |
| `has_module_docstring` | 90% | 206 / 229 |
| `writes_report_json` | 89% | 204 / 229 |
| `mentions_layer_structure` | 69% | 160 / 229 |
| `has_check_names_const` | 65% | 149 / 229 |
| `has_check_labels_const` | 64% | 148 / 229 |
| `prints_header_banner` | 62% | 144 / 229 |
| `imports_validator_utils` | 61% | 140 / 229 |
| `imports_format_result` | 60% | 139 / 229 |
| `calls_format_result` | 60% | 139 / 229 |
| `imports_read_file` | 55% | 128 / 229 |
| `uses_future_annotations` | 54% | 125 / 229 |
| `mentions_skills_consulted` | 33% | 76 / 229 |
| `main_exits_with_code` | 28% | 66 / 229 |
| `returns_1_on_fail` | 24% | 56 / 229 |
| `returns_0_on_success` | 20% | 47 / 229 |
| `imports_wh_pages` | 3% | 7 / 229 |
| `has_allowlist_constant` | 0% | 2 / 229 |