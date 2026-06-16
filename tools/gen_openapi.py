"""
OpenAPI Spec Generator (Maturity Phase 4 — A-layer capability, 2026-06-16).
============================================================================
Generates an OpenAPI 3.1 contract for the WorkHive Edge API from the SAME
source of truth the contract validator already enforces — `ALL_FUNCTIONS` +
`REQUIRED_FIELDS` in validate_edge_contracts.py. INVENT NOTHING: the spec is a
machine-readable VIEW of the contracts that already exist, not a new contract.

Every edge fn becomes:  POST /functions/v1/<fn>  with a requestBody carrying its
required fields, and the canonical envelope responses (200 ok / 4xx { error }).

Output:  openapi.json   (kept in sync by validate_openapi_sync.py)
Exit code: 0 (always — generator)
"""
from __future__ import annotations
import ast, io, json, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "openapi.json"

CHECK_NAMES = ["openapi_gen"]


def _extract_const(name: str):
    """Read a module-level literal (list/dict) from validate_edge_contracts.py via
    AST — no execution, so no stdout side-effects or validator_utils import."""
    tree = ast.parse((ROOT / "validate_edge_contracts.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    return None


def _load_contracts():
    return list(_extract_const("ALL_FUNCTIONS") or []), dict(_extract_const("REQUIRED_FIELDS") or {})


def main() -> int:
    all_fns, required = _load_contracts()

    paths = {}
    for fn in sorted(all_fns):
        req_fields = required.get(fn, [])
        props = {f: {"type": "string", "description": f"Required input: {f}"} for f in req_fields}
        request_body = {
            "required": bool(req_fields),
            "content": {"application/json": {"schema": {
                "type": "object",
                "properties": props or {"_": {"type": "object", "description": "no required fields"}},
                "required": req_fields,
            }}},
        }
        paths[f"/functions/v1/{fn}"] = {
            "post": {
                "operationId": fn.replace("-", "_"),
                "summary": f"Invoke the {fn} edge function",
                "tags": [fn.split("-")[0]],
                "requestBody": request_body,
                "responses": {
                    "200": {"description": "Success — canonical ok envelope",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/OkEnvelope"}}}},
                    "400": {"description": "Bad input", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}}},
                    "401": {"description": "Unauthenticated", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}}},
                    "403": {"description": "Forbidden (cross-tenant / role)", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}}},
                    "429": {"description": "Rate limited", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}}},
                },
            }
        }

    spec = {
        "openapi": "3.1.0",
        "info": {
            "title": "WorkHive Edge API",
            "version": datetime.now(timezone.utc).strftime("%Y.%m.%d"),
            "description": ("Auto-generated from validate_edge_contracts.py (ALL_FUNCTIONS + "
                            "REQUIRED_FIELDS). The contract source of truth is the validator; this "
                            "spec is a machine-readable view. Regenerate with tools/gen_openapi.py."),
        },
        "servers": [{"url": "https://{project}.supabase.co", "variables": {"project": {"default": "YOUR_PROJECT_REF"}}}],
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
            "schemas": {
                "OkEnvelope": {"type": "object", "properties": {
                    "ok": {"type": "boolean", "const": True},
                    "data": {"description": "fn-specific payload"},
                    "trace_id": {"type": "string"},
                }, "required": ["ok"]},
                "ErrorEnvelope": {"type": "object", "properties": {
                    "error": {"type": "string", "description": "human-readable error message"},
                    "ok": {"type": "boolean", "const": False},
                }, "required": ["error"]},
            },
        },
        "security": [{"bearerAuth": []}],
        "paths": paths,
    }

    OUT.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"OpenAPI 3.1 spec generated: {len(paths)} edge-fn paths → {OUT.name}")
    print(f"  with required-field request bodies: {sum(1 for f in all_fns if required.get(f))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
