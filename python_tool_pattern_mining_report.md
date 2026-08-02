# Python Tool Pattern Mining Report

- Files scanned: **609**
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
| `has_print_calls` | 98% | 602 / 609 |
| `has_main_guard` | 95% | 581 / 609 |
| `defines_main` | 86% | 526 / 609 |
| `uses_pathlib` | 76% | 467 / 609 |
| `has_shebang` | 68% | 418 / 609 |
| `uses_future_annotations` | 67% | 410 / 609 |
| `has_cp1252_guard` | 56% | 344 / 609 |
| `uses_json_dump` | 56% | 342 / 609 |
| `uses_sys_argv` | 52% | 318 / 609 |
| `uses_subprocess` | 32% | 197 / 609 |
| `has_module_docstring` | 29% | 181 / 609 |
| `subprocess_has_timeout` | 26% | 162 / 609 |
| `uses_argparse` | 15% | 95 / 609 |
| `reads_env_directly` | 10% | 63 / 609 |
| `passes_request_timeout` | 8% | 54 / 609 |
| `uses_requests_lib` | 5% | 32 / 609 |
| `uses_dotenv` | 2% | 17 / 609 |
| `calls_ai_chain` | 1% | 10 / 609 |
| `bypasses_chain_with_anthropic` | 0% | 3 / 609 |
| `uses_httpx` | 0% | 2 / 609 |
| `bypasses_chain_with_openai` | 0% | 2 / 609 |
| `uses_logging_module` | 0% | 0 / 609 |