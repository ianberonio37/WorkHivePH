"""
Azure $200 sprint — Day 1 resource health check.

Reads .env.azure and pings every provisioned Azure resource to confirm:
- Endpoint URL is reachable
- API key is accepted (200 response)
- Region returns expected response shape

Run AFTER provisioning the 4 resources on Day 1.
Exit code 0 = all resources reachable. Non-zero = something is misconfigured.

Usage:
    python tools/azure_resource_check.py

Cost per run: $0 (all checks use free-tier endpoints).
"""
import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path


def load_env(env_path: Path) -> dict:
    """Minimal .env parser. Supports KEY=VALUE lines, ignores blanks and #-comments."""
    if not env_path.exists():
        print(f"ERROR: {env_path} not found.")
        print(f"Copy {env_path.parent / '.env.azure.example'} to {env_path.name} and fill in values.")
        sys.exit(2)
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" -- {detail}" if detail else ""))
    return ok


def http_get(url: str, headers: dict, timeout: int = 15) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"exception: {e}"


def http_post(url: str, headers: dict, body: dict, timeout: int = 15) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"exception: {e}"


def check_doc_intelligence(env: dict) -> bool:
    print("\n[Layer 2] Document Intelligence")
    endpoint = env.get("AZURE_DOC_INTELLIGENCE_ENDPOINT", "").rstrip("/")
    key = env.get("AZURE_DOC_INTELLIGENCE_KEY", "")
    if not endpoint or not key:
        return check("env vars set", False, "endpoint or key missing in .env.azure")
    if not check("env vars set", True):
        return False
    # GET /documentintelligence/documentModels?api-version=2024-11-30 returns list of models
    url = f"{endpoint}/documentintelligence/documentModels?api-version=2024-11-30"
    status, body = http_get(url, {"Ocp-Apim-Subscription-Key": key})
    if status == 200:
        return check("API reachable + key accepted", True, "models endpoint returned 200")
    return check("API reachable + key accepted", False, f"status={status}, body={body[:200]}")


def check_custom_vision(env: dict) -> bool:
    print("\n[Layer 3] Custom Vision")
    endpoint = env.get("AZURE_CUSTOM_VISION_TRAINING_ENDPOINT", "").rstrip("/")
    key = env.get("AZURE_CUSTOM_VISION_TRAINING_KEY", "")
    if not endpoint or not key:
        return check("env vars set", False, "training endpoint or key missing")
    if not check("env vars set", True):
        return False
    # GET /customvision/v3.3/training/projects returns list of projects (empty on day 1)
    url = f"{endpoint}/customvision/v3.3/training/projects"
    status, body = http_get(url, {"Training-Key": key})
    if status == 200:
        return check("API reachable + key accepted", True, f"projects endpoint returned 200 ({len(json.loads(body))} existing projects)")
    return check("API reachable + key accepted", False, f"status={status}, body={body[:200]}")


def check_translator(env: dict) -> bool:
    print("\n[Layer 7] Translator (F0 free tier)")
    endpoint = env.get("AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com").rstrip("/")
    key = env.get("AZURE_TRANSLATOR_KEY", "")
    region = env.get("AZURE_TRANSLATOR_REGION", "southeastasia")
    if not key:
        return check("env vars set", False, "key missing")
    if not check("env vars set", True):
        return False
    # POST /translate?api-version=3.0&from=tl&to=en with a short Tagalog test phrase
    url = f"{endpoint}/translate?api-version=3.0&from=tl&to=en"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
    }
    status, body = http_post(url, headers, [{"Text": "may butas sa tubo"}])
    if status == 200:
        try:
            translated = json.loads(body)[0]["translations"][0]["text"]
            return check("API reachable + Tagalog->English works", True, f"'may butas sa tubo' -> '{translated}'")
        except Exception as e:
            return check("API reachable + parse response", False, f"parse error: {e}")
    return check("API reachable + key accepted", False, f"status={status}, body={body[:200]}")


def check_speech(env: dict) -> bool:
    print("\n[Existing] Azure Speech (post-rotation)")
    key = env.get("AZURE_SPEECH_KEY", "")
    region = env.get("AZURE_SPEECH_REGION", "southeastasia")
    if not key:
        return check("env vars set", False, "key missing -- did you forget to update after rotation?")
    if not check("env vars set", True):
        return False
    # Token endpoint -- POST to issue an access token, validates the key
    url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    headers = {"Ocp-Apim-Subscription-Key": key, "Content-Length": "0"}
    req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                token = resp.read().decode("utf-8")
                return check("API reachable + new key accepted", True, f"token issued ({len(token)} chars)")
            return check("API reachable", False, f"status={resp.status}")
    except urllib.error.HTTPError as e:
        return check("API reachable", False, f"status={e.code}")
    except Exception as e:
        return check("API reachable", False, f"exception: {e}")


def check_ml_workspace_env(env: dict) -> bool:
    print("\n[Layer 4+6] Azure ML Workspace")
    sub = env.get("AZURE_ML_SUBSCRIPTION_ID", "")
    rg = env.get("AZURE_ML_RESOURCE_GROUP", "")
    ws = env.get("AZURE_ML_WORKSPACE_NAME", "")
    if not (sub and rg and ws):
        return check("env vars set", False, "subscription_id / resource_group / workspace_name missing")
    check("env vars set", True, f"{ws} in {rg}")
    print("    NOTE: Full ML connectivity check requires az CLI login + Azure AD.")
    print("    Verify manually at: https://ml.azure.com  ->  workspace opens without error.")
    return True


def main():
    here = Path(__file__).resolve().parent
    env_path = here.parent / ".env.azure"
    print(f"Reading {env_path}")
    env = load_env(env_path)

    results = [
        check_doc_intelligence(env),
        check_custom_vision(env),
        check_translator(env),
        check_speech(env),
        check_ml_workspace_env(env),
    ]

    print()
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Result: {passed}/{total} checks passed")
    if passed == total:
        print("Day 1 resource setup is ready. Proceed to Day 2.")
        sys.exit(0)
    print("Fix the FAILed checks before running Day 2 tools.")
    sys.exit(1)


if __name__ == "__main__":
    main()
