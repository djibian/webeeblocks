#!/usr/bin/env python3
"""Fill the exact historical Boost support archive without apt metadata.

The canonical historical jobs consume a verified local archive. This helper is
only the cache-fill path: if the exact archive is already present it performs no
network access; if it is absent it downloads one fixed Ubuntu archive URL into a
temporary file, verifies the exact pinned size and SHA-256 through the same
preparer contract, and only then atomically exposes it at the cache path.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
from urllib.error import URLError
from urllib.request import urlopen

from prepare_historical_boost import PACKAGE_NAME, SupportError, verify_archive

PACKAGE_URL = (
    "https://archive.ubuntu.com/ubuntu/pool/main/b/boost1.74/"
    + PACKAGE_NAME
)


def fetch(output: Path) -> Path:
    output = output.resolve()
    if output.exists():
        verify_archive(output)
        return output

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=output.name + ".download.", dir=output.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            with urlopen(PACKAGE_URL, timeout=60) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    temporary.write(chunk)
        verify_archive(temporary_path)
        temporary_path.replace(output)
        temporary_path = None
        verify_archive(output)
        return output
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".ci-support") / PACKAGE_NAME,
    )
    args = parser.parse_args()
    try:
        path = fetch(args.output)
    except (OSError, SupportError, URLError) as exc:
        raise SystemExit(f"FAIL exact historical Boost archive acquisition: {exc}") from exc
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
