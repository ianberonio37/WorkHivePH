# Validator Pattern Mining Report (Meta)

- Files scanned: **411** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 411 / 411 |
| `has_main_guard` | 99% | 407 / 411 |
| `defines_main` | 94% | 388 / 411 |
| `has_module_docstring` | 85% | 351 / 411 |
| `writes_report_json` | 74% | 305 / 411 |
| `has_check_names_const` | 69% | 284 / 411 |
| `uses_future_annotations` | 67% | 277 / 411 |
| `main_exits_with_code` | 58% | 239 / 411 |
| `returns_1_on_fail` | 53% | 218 / 411 |
| `imports_validator_utils` | 45% | 186 / 411 |
| `imports_format_result` | 45% | 185 / 411 |
| `calls_format_result` | 45% | 185 / 411 |
| `mentions_layer_structure` | 44% | 181 / 411 |
| `has_check_labels_const` | 42% | 175 / 411 |
| `returns_0_on_success` | 42% | 173 / 411 |
| `imports_read_file` | 41% | 169 / 411 |
| `prints_header_banner` | 37% | 154 / 411 |
| `mentions_skills_consulted` | 19% | 78 / 411 |
| `imports_wh_pages` | 1% | 7 / 411 |
| `has_allowlist_constant` | 1% | 4 / 411 |