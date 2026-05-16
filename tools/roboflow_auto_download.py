#!/usr/bin/env python3
"""
Automated Roboflow downloader for Layer 3 vision detectors.
Reads API key from .env.roboflow
Downloads arc flash, industrial smoke, oil leak datasets in YOLOv8 format.
Skips datasets < 50 images.
"""

import os
import sys
import io
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load API key from .env.roboflow
env_path = Path(__file__).parent.parent / ".env.roboflow"
load_dotenv(env_path)
api_key = os.getenv("ROBOFLOW_API_KEY")

if not api_key:
    print(f"ERROR: ROBOFLOW_API_KEY not found in {env_path}")
    sys.exit(1)

try:
    from roboflow import Roboflow
except ImportError:
    print("ERROR: roboflow not installed. Run: pip install roboflow")
    sys.exit(1)

# Initialize Roboflow
try:
    rf = Roboflow(api_key=api_key)
    print("[OK] Roboflow authenticated\n")
except Exception as e:
    print(f"ERROR: Authentication failed: {e}")
    sys.exit(1)

# Dataset configuration
base_dir = Path(r"c:\wh-datasets")
base_dir.mkdir(parents=True, exist_ok=True)

datasets_config = [
    {
        "search": "arc flash",
        "folder": "roboflow-arc-spark",
        "detector": "Layer 3.2 (arc/spark detection)",
        "examples": ["arc flash detection", "electrical arc", "arc welding defect", "spark detection", "electrical hazard"]
    },
    {
        "search": "industrial smoke",
        "folder": "roboflow-smoke-leak",
        "detector": "Layer 3.3 (smoke/steam/leak detection)",
        "examples": ["industrial smoke", "smoke detection", "steam leak", "factory smoke", "thermal anomaly"]
    },
    {
        "search": "oil leak",
        "folder": "roboflow-oil-leak",
        "detector": "Layer 3.3 (smoke/steam/leak detection)",
        "examples": ["oil leak", "fluid leak", "coolant leak", "hydraulic leak", "lubrication failure"]
    }
]

print("="*80)
print("ROBOFLOW DATASET SEARCH & DOWNLOAD")
print("="*80)
print(f"API Key loaded: {api_key[:20]}...")
print(f"Base directory: {base_dir}\n")

downloaded_count = 0

for config in datasets_config:
    search_term = config["search"]
    folder_name = config["folder"]
    detector = config["detector"]
    examples = config["examples"]
    output_path = base_dir / folder_name
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"SEARCH: {search_term.upper()}")
    print(f"Use: {detector}")
    print(f"Output: {output_path}")
    print(f"{'='*80}")

    # Roboflow API doesn't have a direct "search" endpoint, so we use workspace/project approach
    # User must provide workspace/project/version or we guide them
    print(f"\nSearching for datasets matching: {search_term}")
    print(f"Example search terms: {', '.join(examples)}\n")

    print(f"Manual download required:")
    print(f"  1. Visit: https://universe.roboflow.com/search?q={search_term.replace(' ', '%20')}")
    print(f"  2. Filter: Industrial / Anomaly Detection / Defect")
    print(f"  3. Pick dataset with 50+ images")
    print(f"  4. Export as YOLOv8 format")
    print(f"  5. Copy the workspace/project/version format")
    print(f"  6. Provide below\n")

    project_ref = input(f"Enter project ref (workspace/project/version) or SKIP: ").strip()

    if project_ref.lower() == "skip" or not project_ref:
        print(f"  [SKIP] SKIPPED\n")
        continue

    try:
        parts = project_ref.split("/")
        if len(parts) < 2:
            print(f"  ERROR: Invalid format. Use: workspace/project/version")
            print(f"  SKIPPED\n")
            continue

        workspace = parts[0]
        project_name = parts[1]
        version = parts[2] if len(parts) > 2 else "1"

        print(f"\n  Downloading: {workspace}/{project_name}/{version}...")

        # Access workspace and project
        project = rf.workspace(workspace).project(project_name)
        dataset = project.version(int(version)).download("yolov8")

        print(f"  [OK] Downloaded to: {dataset.location}")
        print(f"  Files: {len(list(Path(dataset.location).rglob('*')))} total files")
        print(f"  \n  -> Move contents to: {output_path}")
        print(f"     Run: xcopy \"{dataset.location}\" \"{output_path}\" /E /I /Y\n")

        downloaded_count += 1

    except Exception as e:
        print(f"  ERROR: {e}")
        print(f"  Try manual download: https://universe.roboflow.com/search?q={search_term.replace(' ', '%20')}\n")

print("\n" + "="*80)
print(f"SUMMARY: {downloaded_count}/3 datasets downloaded")
print("="*80)
print("Next: Copy downloaded datasets to c:\\wh-datasets\\roboflow-*\\ folders")
print("Then: Ready for Custom Vision training on Day 3\n")
