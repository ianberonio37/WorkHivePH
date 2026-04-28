"""
Shared validator utilities — WorkHive Platform Guardian
=======================================================
Reusable functions for all validators. Provides:

  compile_check(path)
    — run py_compile on a .py file; returns error string or None

  smoke_test(module_file, function_name, inputs, extra_sys_path)
    — import a .py file and call function(inputs)
    — returns (result, None) on success
    — returns (None, "SKIP:msg") when a third-party package is missing locally
    — returns (None, "FAIL:msg") on any real failure

  check_shape(result, shape_spec)
    — verify a result dict has required keys (optionally nested)
    — returns list of issue strings (empty = all good)

  extract_js_array(content, var_name)
    — extract values from: const NAME = ['a', 'b', ...]

  extract_js_object_keys(content, var_name)
    — extract top-level keys from: const NAME = { key: ... }

  read_file(path)
    — read a file; returns None if not found
"""
import sys, os, re, py_compile, importlib.util

# Third-party packages that live in Docker/Render but not necessarily locally.
# Missing these → SKIP (env issue), not FAIL (code issue).
_THIRD_PARTY = {
    "pandas", "numpy", "scipy", "sklearn", "statsmodels",
    "matplotlib", "fastapi", "pydantic", "uvicorn", "httpx",
    "supabase", "groq", "openai", "anthropic",
}


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def compile_check(path):
    """
    Run py_compile on a Python file.
    Returns None on success, error string on failure.
    """
    if not os.path.exists(path):
        return f"File not found: {path}"
    try:
        py_compile.compile(path, doraise=True)
        return None
    except py_compile.PyCompileError as e:
        return str(e)
    except Exception as e:
        return str(e)


def smoke_test(module_file, function_name, test_inputs, extra_sys_path=None):
    """
    Import a Python module from file path, call function_name(test_inputs).

    Returns:
      (result, None)        — function ran successfully
      (None, "SKIP:msg")    — missing third-party package (env issue, not code)
      (None, "FAIL:msg")    — real failure (syntax error, logic bug, missing key, crash)
    """
    if not os.path.exists(module_file):
        return None, f"FAIL:File not found: {module_file}"

    old_path = sys.path[:]
    try:
        paths = extra_sys_path if isinstance(extra_sys_path, list) else \
                ([extra_sys_path] if extra_sys_path else [])
        for p in paths:
            if p and p not in sys.path:
                sys.path.insert(0, p)

        module_name = "_smoke_" + os.path.splitext(os.path.basename(module_file))[0]
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if not spec or not spec.loader:
            return None, f"FAIL:Cannot create module spec for {module_file}"

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        fn = getattr(mod, function_name, None)
        if fn is None:
            return None, f"FAIL:'{function_name}' not found in {module_file}"

        result = fn(test_inputs)
        return result, None

    except ImportError as e:
        pkg = str(e).replace("No module named ", "").strip("'\"").split(".")[0]
        if pkg in _THIRD_PARTY:
            return None, f"SKIP:'{pkg}' not in local env — runs in Docker/Render (install with pip if needed)"
        return None, f"FAIL:ImportError: {e}"

    except Exception as e:
        import traceback
        tb = traceback.format_exc().strip().splitlines()
        detail = tb[-1] if tb else str(e)
        return None, f"FAIL:{type(e).__name__}: {detail}"

    finally:
        sys.path = old_path


def check_shape(result, shape_spec, label="result"):
    """
    Verify a result dict has required keys, optionally checking sub-keys.

    shape_spec formats:
      list — ["key1", "key2"]               checks top-level keys only
      dict — {"key1": ["sub1","sub2"],       checks keys + sub-keys
               "key2": []}

    Returns list of issue strings (empty list = all good).
    """
    if result is None:
        return [f"{label}: result is None — smoke test may have been skipped or failed"]
    if not isinstance(result, dict):
        return [f"{label}: expected dict, got {type(result).__name__}"]

    issues = []
    keys = shape_spec.keys() if isinstance(shape_spec, dict) else shape_spec

    for key in keys:
        if key not in result:
            issues.append(f"{label} missing key '{key}'")
        elif isinstance(shape_spec, dict) and shape_spec[key]:
            sub = result[key]
            if isinstance(sub, dict):
                for subkey in shape_spec[key]:
                    if subkey not in sub:
                        issues.append(f"{label}['{key}'] missing sub-key '{subkey}'")
            elif sub is None:
                issues.append(f"{label}['{key}'] is None — may indicate a crash in that sub-function")

    return issues


def extract_js_array(content, var_name):
    """Extract string values from: const NAME = ['a', 'b', ...]"""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\[([^\]]+)\]",
        content, re.DOTALL
    )
    if not m:
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))


def extract_js_object_keys(content, var_name):
    """Extract top-level keys from: const NAME = { key: ... }"""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\{{",
        content
    )
    if not m:
        return set()
    start = m.end() - 1
    depth = 0
    for i in range(start, min(start + 10000, len(content))):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                block = content[start + 1:i]
                return set(re.findall(
                    r"^\s*['\"]?(\w[^'\":,\n]*?)['\"]?\s*:",
                    block, re.MULTILINE
                ))
    return set()


def format_result(check_names, check_labels, issues):
    """
    Print PASS / SKIP / FAIL for each check and return (n_pass, n_skip, n_fail).
    Issues with skip=True show as SKIP (yellow), others as FAIL (red).
    Callers are responsible for setting up sys.stdout encoding before calling this.
    """
    def c(code, text): return f"\033[{code}m{text}\033[0m"

    failing = {i["check"] for i in issues if not i.get("skip")}
    skipping = {i["check"] for i in issues if i.get("skip")}

    for check in check_names:
        label = check_labels.get(check, check)
        if check in failing:
            print(f"  {c('91','FAIL')}  {label}")
        elif check in skipping:
            print(f"  {c('93','SKIP')}  {label}")
        else:
            print(f"  {c('92','PASS')}  {label}")

    n_fail = len(failing)
    n_skip = len(skipping)
    n_pass = len(check_names) - n_fail - n_skip

    if issues:
        print(f"\n{c('91','Issues:') if n_fail else c('93','Notes:')}")
        for iss in issues:
            tag = c("93", "SKIP") if iss.get("skip") else c("91", "FAIL")
            print(f"  [{tag}] [{iss['check']}]  {iss['reason']}")

    return n_pass, n_skip, n_fail
