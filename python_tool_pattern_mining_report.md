# Python Tool Pattern Mining Report

- Files scanned: **623**
- Features extracted: **22**
- Promotion threshold: >= 80% conformance, <= 8 outliers
- Promotion candidates: **1**

## Promotion candidates

| Feature | Conformance | Outlier count |
|---|---:|---:|
| `has_print_calls` | 98% | 7 |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_print_calls` | 98% | 616 / 623 |
| `has_main_guard` | 95% | 595 / 623 |
| `defines_main` | 86% | 539 / 623 |
| `uses_pathlib` | 75% | 469 / 623 |
| `has_shebang` | 69% | 430 / 623 |
| `uses_future_annotations` | 66% | 415 / 623 |
| `uses_json_dump` | 55% | 345 / 623 |
| `has_cp1252_guard` | 55% | 344 / 623 |
| `uses_sys_argv` | 53% | 330 / 623 |
| `uses_subprocess` | 32% | 203 / 623 |
| `has_module_docstring` | 29% | 183 / 623 |
| `subprocess_has_timeout` | 26% | 167 / 623 |
| `uses_argparse` | 15% | 98 / 623 |
| `reads_env_directly` | 10% | 64 / 623 |
| `passes_request_timeout` | 9% | 57 / 623 |
| `uses_requests_lib` | 5% | 32 / 623 |
| `uses_dotenv` | 2% | 17 / 623 |
| `calls_ai_chain` | 1% | 10 / 623 |
| `bypasses_chain_with_anthropic` | 0% | 3 / 623 |
| `uses_httpx` | 0% | 2 / 623 |
| `bypasses_chain_with_openai` | 0% | 2 / 623 |
| `uses_logging_module` | 0% | 0 / 623 |