# Validator Pattern Mining Report (Meta)

- Files scanned: **402** validate_*.py
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
| `has_cp1252_stdout_guard` | 100% | 402 / 402 |
| `has_main_guard` | 99% | 398 / 402 |
| `defines_main` | 94% | 379 / 402 |
| `has_module_docstring` | 87% | 350 / 402 |
| `writes_report_json` | 75% | 305 / 402 |
| `has_check_names_const` | 70% | 284 / 402 |
| `uses_future_annotations` | 67% | 271 / 402 |
| `main_exits_with_code` | 57% | 230 / 402 |
| `returns_1_on_fail` | 52% | 209 / 402 |
| `imports_validator_utils` | 46% | 186 / 402 |
| `imports_format_result` | 46% | 185 / 402 |
| `calls_format_result` | 46% | 185 / 402 |
| `mentions_layer_structure` | 45% | 181 / 402 |
| `has_check_labels_const` | 43% | 175 / 402 |
| `returns_0_on_success` | 42% | 170 / 402 |
| `imports_read_file` | 42% | 169 / 402 |
| `prints_header_banner` | 38% | 154 / 402 |
| `mentions_skills_consulted` | 19% | 78 / 402 |
| `imports_wh_pages` | 1% | 7 / 402 |
| `has_allowlist_constant` | 1% | 4 / 402 |