#!/usr/bin/env python3
"""Setup script for job-filter-py — downloads Obscura headless browser.

Run once after cloning:
   python setup.py

Obscura is a ~55 MB headless browser (Rust + V8) required for job searching.
The binary is downloaded from GitHub Releases and saved to bin/.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

OBSCURA_VERSION = "v0.1.8"
OBSCURA_REPO = "h4ckf0r0day/obscura"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(PROJECT_ROOT, "bin")


def _detect_platform() -> str:
    system = platform.system().lower()
    if "windows" in system:
        return "windows"
    if "linux" in system:
        return "linux"
    if "darwin" in system:
        return "macos"
    raise RuntimeError(f"Unsupported platform: {system}")


def _download_file(url: str, dest: str) -> None:
    print(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, dest)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    plat = _detect_platform()

    if plat != "windows":
        print(f"Obscura currently only ships Windows binaries.")
        print(f"Your platform ({plat}) may need to build from source:")
        print(f"  https://github.com/{OBSCURA_REPO}")
        sys.exit(1)

    # Check if already installed
    obscura_exe = os.path.join(BIN_DIR, "obscura.exe")
    worker_exe = os.path.join(BIN_DIR, "obscura-worker.exe")
    if os.path.exists(obscura_exe) and os.path.exists(worker_exe):
        result = subprocess.run([obscura_exe, "--version"], capture_output=True, text=True)
        print(f"Obscura already installed: {result.stdout.strip()}")
        return

    # Download
    os.makedirs(BIN_DIR, exist_ok=True)
    zip_name = f"obscura-x86_64-windows.zip"
    zip_url = f"https://github.com/{OBSCURA_REPO}/releases/download/{OBSCURA_VERSION}/{zip_name}"

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, zip_name)
        _download_file(zip_url, zip_path)

        print("Extracting ...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)

        # Copy binaries
        for name in ("obscura.exe", "obscura-worker.exe"):
            src = os.path.join(tmp, name)
            dst = os.path.join(BIN_DIR, name)
            if os.path.exists(src):
                shutil.move(src, dst)
                print(f"  Installed {name} ({os.path.getsize(dst):,} bytes)")

    # Verify
    result = subprocess.run([obscura_exe, "--version"], capture_output=True, text=True)
    print(f"\nDone! {result.stdout.strip()}")


if __name__ == "__main__":
    main()
