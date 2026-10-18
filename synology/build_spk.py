#!/usr/bin/env python3
"""
ReadFlow Synology SPK Package Builder
-------------------------------------
Packages ReadFlow into a standard Synology DSM 7.x/6.x SPK file.
Usage:
    python3 synology/build_spk.py
"""

import os
import sys
import tarfile
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SYNOLOGY_DIR = ROOT_DIR / "synology"
DIST_DIR = ROOT_DIR / "dist"

def build():
    print("=" * 60)
    print("📦 Building ReadFlow Synology NAS Package (.spk)...")
    print("=" * 60)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    spk_name = "readflow_1.0.0_noarch.spk"
    spk_path = DIST_DIR / spk_name
    package_tgz_path = SYNOLOGY_DIR / "package.tgz"

    # 1. Build package.tgz containing application files
    print("[1/3] Packaging application payload into package.tgz...")
    with tarfile.open(package_tgz_path, "w:gz") as tar:
        # Files to include
        for f in ["main.py", "requirements.txt", ".env.example", "LICENSE", "README.md"]:
            p = ROOT_DIR / f
            if p.exists():
                tar.add(p, arcname=f)

        # Directories to include
        for d in ["src"]:
            p = ROOT_DIR / d
            if p.exists():
                tar.add(p, arcname=d, filter=lambda ti: None if "__pycache__" in ti.name else ti)

    # 2. Package everything into .spk (which is a standard tar archive)
    print("[2/3] Assembling SPK archive...")
    items_to_pack = [
        "INFO",
        "PACKAGE_ICON.PNG",
        "PACKAGE_ICON_256.PNG",
        "package.tgz",
        "conf",
        "scripts",
        "ui",
        "WIZARD_UIFILES"
    ]

    with tarfile.open(spk_path, "w") as spk:
        for item in items_to_pack:
            p = SYNOLOGY_DIR / item
            if p.exists():
                if p.is_dir():
                    spk.add(p, arcname=item)
                else:
                    spk.add(p, arcname=item)
            else:
                print(f"[!] Warning: missing {item}")

    # Clean up intermediate package.tgz
    if package_tgz_path.exists():
        package_tgz_path.unlink()

    spk_size_mb = round(spk_path.stat().st_size / (1024 * 1024), 2)
    print(f"[3/3] ✅ SPK build completed successfully!")
    print(f"👉 Target SPK: {spk_path} ({spk_size_mb} MB)")
    print("=" * 60)

if __name__ == "__main__":
    build()
