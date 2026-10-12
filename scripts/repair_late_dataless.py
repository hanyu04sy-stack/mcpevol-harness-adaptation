#!/usr/bin/env python3
"""Idempotently restore Late bundle files from its pinned verified archive."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from download_server_bundles import BUNDLES, repair_extract, verify


def needs_restore(target: Path, member: zipfile.ZipInfo) -> bool:
    if not target.is_file():
        return True
    stat = target.stat()
    return stat.st_size != member.file_size or (
        member.file_size > 0 and hasattr(stat, "st_blocks") and stat.st_blocks == 0
    )


def inspect_repair(archive: Path, destination: Path) -> dict[str, Any]:
    if not archive.is_file():
        return {"archive": str(archive), "destination": str(destination), "archive_present": False, "files_to_restore": None}
    count = 0
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            if not member.is_dir() and needs_restore(destination / member.filename, member):
                count += 1
    return {"archive": str(archive), "destination": str(destination), "archive_present": True, "files_to_restore": count}


def repair_late(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    spec = BUNDLES["late"]
    archive = root / "archives" / str(spec["filename"])
    destination = root / str(spec["directory"])
    plan = inspect_repair(archive, destination)
    plan["dry_run"] = dry_run
    plan["repaired_files"] = 0
    if dry_run:
        return plan
    verify(archive, int(spec["size"]), str(spec["sha256"]))
    repaired = repair_extract(archive, destination)
    plan["repaired_files"] = plan["files_to_restore"] if repaired < 0 else repaired
    plan["files_to_restore"] = 0
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair Late macOS/iCloud dataless files")
    parser.add_argument("--root", type=Path, default=Path("external/servers"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = repair_late(args.root, dry_run=args.dry_run)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"LATE REPAIR ERROR: {exc}") from exc
    print(json.dumps(result, indent=2))
    if not args.dry_run:
        print(f"[repair] Late dataless file fixed: {result['destination']}")


if __name__ == "__main__":
    main()
