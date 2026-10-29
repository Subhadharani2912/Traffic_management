#!/usr/bin/env python3
"""Resume-friendly download of the Roboflow YOLOv8 zip (retries on drop)."""
from __future__ import annotations

import os
import sys
import time
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_ZIP = ROOT / "dataset" / "emergency_indian.zip"
EXTRACT_DIR = ROOT / "dataset" / "emergency_indian"

# Pass a fresh Roboflow export URL: set ROBOFLOW_ZIP_URL or pass it as argv[1].
DEFAULT_URL = ""


def human(n: int) -> str:
    return f" {n / (1024 * 1024):.1f} MB"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "traffic-management-resume/1.0"})

    for attempt in range(1, 41):
        already = dest.stat().st_size if dest.exists() else 0
        headers = {"Range": f"bytes={already}-"} if already else {}
        print(f"[Attempt {attempt}/40] {human(already)} already on disk, resuming...")
        try:
            with session.get(url, stream=True, headers=headers, timeout=90) as resp:
                if resp.status_code == 416:
                    print("Server says file is already complete.")
                    return
                if resp.status_code not in (200, 206):
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

                mode = "ab" if already and resp.status_code == 206 else "wb"
                if mode == "wb" and already:
                    print("Server does not support resume; restarting this attempt from 0.")
                    already = 0

                total = already
                cl = resp.headers.get("Content-Length")
                if cl and resp.status_code == 206:
                    expected = already + int(cl)
                elif cl:
                    expected = int(cl)
                else:
                    expected = 0

                written_this = 0
                with open(dest, mode) as fh:
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        written_this += len(chunk)
                        total += len(chunk)
                        if written_this % (8 * 1024 * 1024) < 256 * 1024:
                            extra = f" / {human(expected)}" if expected else ""
                            print(f"  {human(total)}{extra}", flush=True)

            size = dest.stat().st_size
            if expected and size < expected:
                raise RuntimeError(f"Incomplete: {human(size)} of {human(expected)}")
            if size < 10 * 1024 * 1024:
                raise RuntimeError(f"File too small ({human(size)}); download likely failed.")
            print(f"Download finished: {human(size)}")
            return
        except Exception as exc:
            print(f"  Dropped: {exc}")
            time.sleep(min(30, 3 * attempt))

    raise SystemExit("Download failed after 40 retries. Re-run this script.")


def unzip(dest: Path, out_dir: Path) -> None:
    print(f"Unzipping to {out_dir} ...")
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "r") as zf:
        zf.testzip()
        zf.extractall(out_dir)
    print("Unzip complete.")
    yaml = list(out_dir.rglob("data.yaml"))
    if yaml:
        print(f"Found {yaml[0]}")
    else:
        print("Warning: data.yaml not found yet. Check the unzipped folder.")


def main() -> None:
    url = os.environ.get("ROBOFLOW_ZIP_URL", DEFAULT_URL)
    if len(sys.argv) > 1:
        url = sys.argv[1]
    download(url, OUT_ZIP)
    unzip(OUT_ZIP, EXTRACT_DIR)


if __name__ == "__main__":
    main()
