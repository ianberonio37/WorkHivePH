"""
Backfill CHECK_NAMES declaration into each validator that doesn't have one.
The sentinel coverage matcher binds Playwright `test('<check_name>: ...')`
to L0 validators via this list. Validators without CHECK_NAMES show up
in the coverage report with checks=[] → can't be bound to any sentinel.

Run once on the 16 L0 validators shipped 2026-05-20 in commit a91b5a6.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (validator file, check name) — one platform-wide check per validator.
TARGETS = [
    ("validate_aria_label_coverage.py",            "aria_label_coverage"),
    ("validate_css_class_existence.py",            "css_class_existence"),
    ("validate_event_listener_cleanup.py",          "event_listener_cleanup"),
    ("validate_filter_case_consistency.py",         "filter_case_consistency"),
    ("validate_getelementbyid_orphan_setter.py",    "getelementbyid_orphan_setter"),
    ("validate_heading_hierarchy.py",               "heading_hierarchy"),
    ("validate_inline_onclick_handler.py",          "inline_onclick_handler"),
    ("validate_innerhtml_eschtml.py",               "innerhtml_eschtml"),
    ("validate_link_target_existence.py",           "link_target_existence"),
    ("validate_localstorage_key_consistency.py",    "localstorage_key_consistency"),
    ("validate_query_column_existence.py",          "query_column_existence"),
    ("validate_role_string_consistency.py",         "role_string_consistency"),
    ("validate_rpc_argument_consistency.py",        "rpc_argument_consistency"),
    ("validate_time_window_consistency.py",         "time_window_consistency"),
    ("validate_unbounded_query.py",                 "unbounded_query"),
    ("validate_realtime_subscription_consistency.py","realtime_subscription_consistency"),
    ("validate_realtime_payload_columns.py",        "realtime_payload_columns"),
    ("validate_realtime_channel_cleanup.py",        "realtime_channel_cleanup"),
    ("validate_orphan_kpi_tiles.py",                "orphan_kpi_tiles"),
    ("validate_kpi_count_query_safety.py",          "kpi_count_query_safety"),
    ("validate_source_chip_truth.py",               "source_chip_truth"),
    ("validate_audit_scanner_scope.py",             "audit_scanner_scope"),
    ("validate_truth_view_signal_trust.py",         "truth_view_signal_trust"),
    ("validate_image_asset_existence.py",           "image_asset_existence"),
    ("validate_service_worker_shell.py",            "service_worker_shell"),
    ("validate_edge_function_invoke.py",            "edge_function_invoke"),
    ("validate_env_variable_existence.py",          "env_variable_existence"),
    ("validate_playwright_selector_existence.py",   "playwright_selector_existence"),
    ("validate_pg_cron_target_existence.py",        "pg_cron_target_existence"),
    ("validate_trigger_function_existence.py",      "trigger_function_existence"),
    ("validate_meta_description_coverage.py",       "meta_description_coverage"),
    ("validate_sitemap_page_existence.py",          "sitemap_page_existence"),
    ("validate_canonical_url_consistency.py",       "canonical_url_consistency"),
]


def main() -> int:
    patched = 0
    skipped = 0
    for fname, check_name in TARGETS:
        p = ROOT / fname
        if not p.exists():
            print(f"  - skip (missing): {fname}")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^CHECK_NAMES\s*=", text, re.MULTILINE):
            skipped += 1
            continue
        # Insert before the `def main(` line.
        snippet = f"\n# Sentinel binding: name the L2 test `test('{check_name}: ...')` for coverage credit.\nCHECK_NAMES = [\"{check_name}\"]\n"
        new = re.sub(
            r"(\ndef main\(\s*\)\s*->)", snippet + r"\n\1", text, count=1
        )
        if new == text:
            print(f"  ? could not find `def main(` in {fname}")
            continue
        p.write_text(new, encoding="utf-8")
        patched += 1
        print(f"  + {fname}  CHECK_NAMES = [\"{check_name}\"]")
    print(f"\nPatched {patched} · skipped {skipped} (already had CHECK_NAMES).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
