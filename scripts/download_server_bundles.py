#!/usr/bin/env python3
"""Download, verify, and safely extract the evolved MCP server bundles."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


BUNDLES = {
    "middle": {
        "filename": "iter3_servers.zip",
        "directory": "iter3_servers",
        "url": "https://huggingface.co/datasets/anonymous2233/evol-servers/resolve/main/iter3_servers.zip?download=true",
        "size": 1_088_423_924,
        "sha256": "18ef1f0c693b4d84730992211f0663817973f3fb6b436e2e77f7c082137e2391",
    },
    "late": {
        "filename": "iter5_servers.zip",
        "directory": "iter5_servers",
        "url": "https://huggingface.co/datasets/anonymous2233/evol-servers/resolve/main/iter5_servers.zip?download=true",
        "size": 1_088_574_402,
        "sha256": "67cc5adc6959acfa978ee67a0b53cc02f2fb064b16811d7a300a505117acaad1",
    },
}


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected_size: int, expected_sha256: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise ValueError(f"{path}: size {actual_size}, expected {expected_size}")
    actual_hash = sha256(path)
    if actual_hash != expected_sha256:
        raise ValueError(f"{path}: SHA-256 {actual_hash}, expected {expected_sha256}")


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "mcpevol-reproducible-setup/1.0"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        if offset and response.status != 206:
            partial.unlink()
            offset = 0
            return download(url, destination)
        mode = "ab" if offset else "wb"
        total = response.headers.get("Content-Length")
        total_bytes = offset + int(total) if total else None
        copied = offset
        with partial.open(mode) as output:
            while chunk := response.read(8 * 1024 * 1024):
                output.write(chunk)
                copied += len(chunk)
                if total_bytes:
                    print(f"\r{destination.name}: {copied / total_bytes:.1%}", end="", flush=True)
    print()
    partial.replace(destination)


def safe_extract(archive: Path, destination: Path) -> None:
    if destination.exists():
        if any(destination.iterdir()):
            print(f"Already extracted: {destination}")
            return
        destination.rmdir()
    staging = destination.with_name(destination.name + ".extracting")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    root = staging.resolve()
    try:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                target = (staging / member.filename).resolve()
                if root not in target.parents and target != root:
                    raise ValueError(f"Unsafe archive member: {member.filename}")
            bundle.extractall(staging)
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def process_bundle(name: str, root: Path, verify_only: bool, no_extract: bool) -> None:
    spec = BUNDLES[name]
    archive = root / "archives" / str(spec["filename"])
    if not archive.exists():
        if verify_only:
            raise FileNotFoundError(archive)
        print(f"Downloading {name} bundle (~1.1 GB)...")
        download(str(spec["url"]), archive)
    print(f"Verifying {archive.name}...")
    verify(archive, int(spec["size"]), str(spec["sha256"]))
    print(f"SHA-256 OK: {spec['sha256']}")
    if not verify_only and not no_extract:
        safe_extract(archive, root / str(spec["directory"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("external/servers"))
    parser.add_argument("--versions", nargs="+", choices=sorted(BUNDLES), default=["middle", "late"])
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--no-extract", action="store_true")
    args = parser.parse_args()
    try:
        for name in args.versions:
            process_bundle(name, args.root, args.verify_only, args.no_extract)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
