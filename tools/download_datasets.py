"""
Azure $200 sprint — Day 1 dataset downloads.

Downloads the public industrial datasets used by Layers 3, 4, 6:
- KolektorSDD2  (metal surface defects, ~1 GB, direct)        -> Layer 3 detector 1
- MIMII          (industrial machine sound, ~10 GB, Zenodo)   -> Layer 4 + Layer 6
- NASA C-MAPSS   (predictive baseline reference, <100 MB)     -> reference only
- Microsoft DNS  (noise suppression base, ~partial sample)    -> Layer 6 base

Form-gated (NOT automated -- prints manual instructions):
- MVTec AD       (requires email registration)                -> Layer 3 detector 1
- Roboflow arc/spark/smoke datasets (account-gated)           -> Layer 3 detectors 2-3

Datasets are saved to WH_DATASETS_DIR from .env.azure (default c:/wh-datasets).
This directory must be OUTSIDE the project repo to avoid git bloat.

Usage:
    python tools/download_datasets.py
    python tools/download_datasets.py --only mimii
    python tools/download_datasets.py --list
"""
import os
import sys
import argparse
import urllib.request
import urllib.error
from pathlib import Path


# Direct-downloadable datasets. (label, url, filename, approx_mb, notes)
DIRECT_DATASETS = [
    {
        "label": "KolektorSDD2",
        "url": "https://www.vicos.si/Downloads/KolektorSDD2.zip",
        "filename": "KolektorSDD2.zip",
        "approx_mb": 1000,
        "notes": "Metal surface defects. Used by Layer 3 detector 1.",
    },
    {
        "label": "MIMII",
        "url": "https://zenodo.org/records/3384388/files/-6_dB_fan.zip",
        "filename": "MIMII_-6dB_fan.zip",
        "approx_mb": 1900,
        "notes": "Industrial machine sound (fan subset, -6dB SNR). Used by Layers 4 + 6. Full dataset has 6 SNR levels x 4 machine types -- start with one subset to validate pipeline.",
    },
    {
        "label": "NASA C-MAPSS",
        "url": "https://data.nasa.gov/api/views/ff5v-kuh6/files/dataverse_files.zip",
        "filename": "NASA_C-MAPSS.zip",
        "approx_mb": 100,
        "notes": "Turbofan engine degradation. Reference only -- not used directly this sprint.",
    },
]


# Datasets that require manual steps (account/form). Just print instructions.
MANUAL_DATASETS = [
    {
        "label": "MVTec AD",
        "url": "https://www.mvtec.com/company/research/datasets/mvtec-ad",
        "approx_mb": 5000,
        "notes": (
            "Industrial anomaly / surface defect benchmark. License: CC BY-NC-SA (non-commercial).\n"
            "  1) Visit the URL above\n"
            "  2) Fill the email-registration form\n"
            "  3) Download all category archives (~5 GB total) into the datasets folder\n"
            "  4) Extract each category into its own folder"
        ),
    },
    {
        "label": "Microsoft DNS Challenge",
        "url": "https://github.com/microsoft/DNS-Challenge",
        "approx_mb": 30000,
        "notes": (
            "Noise suppression base model + training data. Generated, not direct-downloaded.\n"
            "  1) git clone https://github.com/microsoft/DNS-Challenge.git\n"
            "  2) Read the README -- training data is synthesized from clean speech + noise libraries via the included scripts\n"
            "  3) For Layer 6 fine-tuning, you may only need the pretrained baseline model (much smaller than full dataset)\n"
            "  4) Look for pretrained_models/ in the repo and download those instead of the full 30 GB"
        ),
    },
    {
        "label": "Roboflow Universe (arc/spark, industrial smoke)",
        "url": "https://universe.roboflow.com/search?q=arc%20flash",
        "approx_mb": 500,
        "notes": (
            "Free account required (universe.roboflow.com).\n"
            "  Search terms to try: 'arc flash', 'industrial smoke', 'oil leak', 'corrosion'\n"
            "  Download as Tensorflow / COCO / YOLOv8 format depending on Custom Vision import format\n"
            "  Used by Layer 3 detectors 2 (arc/spark) and 3 (smoke/steam/leak)"
        ),
    },
]


def load_env(env_path: Path) -> dict:
    if not env_path.exists():
        return {}
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def download_with_progress(url: str, dest: Path, label: str):
    """urlretrieve with simple progress bar. No third-party deps."""
    print(f"\n[{label}] downloading {url}")
    print(f"  destination: {dest}")
    if dest.exists():
        print(f"  already exists ({dest.stat().st_size // (1024*1024)} MB) -- skipping")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_pct = -1

    def hook(block_num: int, block_size: int, total_size: int):
        nonlocal last_pct
        if total_size <= 0:
            return
        downloaded = block_num * block_size
        pct = min(100, int(downloaded * 100 / total_size))
        if pct != last_pct and pct % 5 == 0:
            mb = downloaded // (1024 * 1024)
            total_mb = total_size // (1024 * 1024)
            print(f"  {pct:3d}%  ({mb} MB / {total_mb} MB)")
            last_pct = pct

    try:
        urllib.request.urlretrieve(url, dest, reporthook=hook)
        size_mb = dest.stat().st_size // (1024 * 1024)
        print(f"  done ({size_mb} MB)")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"  exception: {e}")
        if dest.exists() and dest.stat().st_size < 1024:
            dest.unlink()  # remove partial


def print_manual_instructions():
    print()
    print("=" * 70)
    print("MANUAL DOWNLOADS REQUIRED (account or form-gated)")
    print("=" * 70)
    for d in MANUAL_DATASETS:
        print(f"\n[{d['label']}]  (~{d['approx_mb']} MB)")
        print(f"  URL: {d['url']}")
        print(f"  {d['notes']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None, help="Download only one dataset by label (e.g. mimii)")
    parser.add_argument("--list", action="store_true", help="List all datasets and exit")
    parser.add_argument("--datasets-dir", default=None, help="Override WH_DATASETS_DIR")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    env = load_env(here.parent / ".env.azure")
    datasets_dir = Path(args.datasets_dir or env.get("WH_DATASETS_DIR") or "c:/wh-datasets")

    if args.list:
        print(f"Datasets directory: {datasets_dir}")
        print("\nDirect downloads:")
        for d in DIRECT_DATASETS:
            print(f"  - {d['label']:18s} (~{d['approx_mb']} MB)  {d['notes']}")
        print_manual_instructions()
        return

    print(f"Datasets directory: {datasets_dir}")
    datasets_dir.mkdir(parents=True, exist_ok=True)

    only = (args.only or "").lower()
    targets = [d for d in DIRECT_DATASETS if (not only or only in d["label"].lower())]
    if only and not targets:
        print(f"No dataset matching '{args.only}'. Use --list to see options.")
        sys.exit(2)

    for d in targets:
        dest = datasets_dir / d["filename"]
        download_with_progress(d["url"], dest, d["label"])

    if not only:
        print_manual_instructions()

    print("\nDirect downloads complete. Address manual downloads above before Day 3.")


if __name__ == "__main__":
    main()
