#!/usr/bin/env python3
"""Store API credentials locally without echoing or logging secret values."""

from __future__ import annotations

import argparse
import getpass
import os
import tempfile
from pathlib import Path

from experiment_config import parse_env_file


ROOT = Path(__file__).resolve().parents[1]


def configured_default_base_url() -> str:
    value = parse_env_file(ROOT / ".env.example").get("MODEL_BASE_URL", "").strip()
    if not value:
        raise SystemExit(".env.example must define a non-empty MODEL_BASE_URL")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--set-base-url",
        metavar="URL",
        help="update MODEL_BASE_URL without echoing secrets",
    )
    args = parser.parse_args()
    destination = args.env_file.resolve()
    if args.set_base_url:
        if not destination.is_file():
            raise SystemExit(f"{destination} does not exist")
        lines = destination.read_text(encoding="utf-8").splitlines()
        replacement = f"MODEL_BASE_URL={args.set_base_url}"
        for index, line in enumerate(lines):
            if line.startswith("MODEL_BASE_URL="):
                lines[index] = replacement
                break
        else:
            lines.append(replacement)
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(destination, 0o600)
        print(f"Updated MODEL_BASE_URL in {destination}; no secret was printed.")
        return
    if destination.exists() and not args.overwrite:
        raise SystemExit(
            f"{destination} already exists; rerun with --overwrite to replace it"
        )
    key = getpass.getpass("MODEL_API_KEY (hidden; input is not displayed): ").strip()
    if not key:
        raise SystemExit("No API key entered; nothing was written")
    default_base_url = configured_default_base_url()
    base_url = input(
        f"MODEL_BASE_URL (press Enter for {default_base_url}): "
    ).strip() or default_base_url
    print(
        "Judge uses the same model and key by default. Press Enter to inherit, "
        "or type a separate judge key (advanced)."
    )
    judge_key = getpass.getpass("JUDGE_API_KEY (hidden; optional): ").strip()
    judge_base_url = ""
    if judge_key:
        judge_base_url = input(
            f"JUDGE_BASE_URL (press Enter for {base_url}): "
        ).strip() or base_url
    lines = [
        "# Local secrets: never commit this file.",
        f"MODEL_API_KEY={key}",
        f"MODEL_BASE_URL={base_url}",
        f"JUDGE_API_KEY={judge_key}",
        f"JUDGE_BASE_URL={judge_base_url}",
        "",
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".env.", dir=destination.parent, text=True
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines))
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise
    print(f"Saved credentials to {destination} with mode 600; no secret was printed.")


if __name__ == "__main__":
    main()
