#!/usr/bin/env python3
"""
Roboflow dataset downloader for Layer 3 vision detectors.
Searches for arc flash, industrial smoke, oil leak datasets.
Requires: pip install roboflow
"""

import os
import sys
from pathlib import Path

try:
    from roboflow import Roboflow
except ImportError:
    print("ERROR: roboflow not installed. Run: pip install roboflow")
    sys.exit(1)

# Get API key from user (not exposed in chat)
api_key = input("Paste your Roboflow API key: ").strip()
if not api_key:
    print("ERROR: API key required")
    sys.exit(1)

# Initialize Roboflow
try:
    rf = Roboflow(api_key=api_key)
except Exception as e:
    print(f"ERROR: Authentication failed: {e}")
    sys.exit(1)

# Dataset base directory
base_dir = Path(r"c:\wh-datasets")
base_dir.mkdir(parents=True, exist_ok=True)

# Search terms and output folders
searches = [
    ("arc flash", "roboflow-arc-spark"),
    ("industrial smoke", "roboflow-smoke-leak"),
    ("oil leak", "roboflow-oil-leak"),
]

print("\n" + "="*70)
print("Searching Roboflow for industrial anomaly datasets...")
print("="*70)

for search_term, folder_name in searches:
    print(f"\n[{search_term}]")
    output_path = base_dir / folder_name
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # Search for dataset (workspace required; user picks from results)
        print(f"  Searching for: '{search_term}'...")
        print(f"  Output folder: {output_path}")
        print(f"  Visit: https://universe.roboflow.com/search?q={search_term.replace(' ', '%20')}")
        print(f"  1. Find a dataset with 100+ images")
        print(f"  2. Export as YOLOv8")
        print(f"  3. Copy the workspace/{project} name")
        print(f"  Example: user123/industrial-smoke-detection/1")

        project_ref = input(f"  Enter project ref (workspace/project/version) or SKIP: ").strip()
        if project_ref.lower() == "skip" or not project_ref:
            print(f"  SKIPPED")
            continue

        parts = project_ref.split("/")
        if len(parts) < 2:
            print(f"  ERROR: Invalid format. Expected: workspace/project/version")
            continue

        workspace = parts[0]
        project = parts[1]
        version = parts[2] if len(parts) > 2 else "1"

        print(f"  Downloading {workspace}/{project}/{version}...")

        project = rf.workspace(workspace).project(project)
        dataset = project.version(int(version)).download("yolov8")

        print(f"  ✓ Downloaded to: {dataset.location}")
        print(f"  Next: Copy contents to {output_path}")

    except Exception as e:
        print(f"  ERROR: {e}")
        print(f"  Manual download: https://universe.roboflow.com/search?q={search_term.replace(' ', '%20')}")

print("\n" + "="*70)
print("Manual workflow (alternative):")
print("1. Visit https://universe.roboflow.com")
print("2. Search: 'arc flash', 'industrial smoke', 'oil leak'")
print("3. Export as YOLOv8 format")
print("4. Save to c:\\wh-datasets\\roboflow-*\\")
print("="*70)
