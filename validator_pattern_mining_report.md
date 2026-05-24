# Validator Pattern Mining Report (Meta)

- Files scanned: **298** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 298 / 298 |
| `has_main_guard` | 98% | 294 / 298 |
| `defines_main` | 92% | 276 / 298 |
| `has_module_docstring` | 92% | 275 / 298 |
| `writes_report_json` | 80% | 239 / 298 |
| `has_check_names_const` | 79% | 236 / 298 |
| `uses_future_annotations` | 65% | 194 / 298 |
| `imports_validator_utils` | 58% | 174 / 298 |
| `imports_format_result` | 58% | 173 / 298 |
| `calls_format_result` | 58% | 173 / 298 |
| `has_check_labels_const` | 56% | 167 / 298 |
| `mentions_layer_structure` | 55% | 164 / 298 |
| `imports_read_file` | 54% | 162 / 298 |
| `prints_header_banner` | 48% | 144 / 298 |
| `main_exits_with_code` | 45% | 135 / 298 |
| `returns_1_on_fail` | 41% | 125 / 298 |
| `returns_0_on_success` | 27% | 82 / 298 |
| `mentions_skills_consulted` | 25% | 76 / 298 |
| `imports_wh_pages` | 2% | 7 / 298 |
| `has_allowlist_constant` | 0% | 2 / 298 |