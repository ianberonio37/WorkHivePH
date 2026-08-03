# Python Tool Pattern Mining Report

- Files scanned: **615**
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
| `has_print_calls` | 98% | 608 / 615 |
| `has_main_guard` | 95% | 587 / 615 |
| `defines_main` | 86% | 531 / 615 |
| `uses_pathlib` | 76% | 469 / 615 |
| `has_shebang` | 68% | 422 / 615 |
| `uses_future_annotations` | 67% | 413 / 615 |
| `has_cp1252_guard` | 55% | 344 / 615 |
| `uses_json_dump` | 55% | 343 / 615 |
| `uses_sys_argv` | 52% | 323 / 615 |
| `uses_subprocess` | 32% | 200 / 615 |
| `has_module_docstring` | 29% | 183 / 615 |
| `subprocess_has_timeout` | 26% | 165 / 615 |
| `uses_argparse` | 15% | 96 / 615 |
| `reads_env_directly` | 10% | 63 / 615 |
| `passes_request_timeout` | 9% | 56 / 615 |
| `uses_requests_lib` | 5% | 32 / 615 |
| `uses_dotenv` | 2% | 17 / 615 |
| `calls_ai_chain` | 1% | 10 / 615 |
| `bypasses_chain_with_anthropic` | 0% | 3 / 615 |
| `uses_httpx` | 0% | 2 / 615 |
| `bypasses_chain_with_openai` | 0% | 2 / 615 |
| `uses_logging_module` | 0% | 0 / 615 |