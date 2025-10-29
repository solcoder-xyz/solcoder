#!/usr/bin/env python3
"""
Unpack the Solana LightRAG knowledge pack into var/lightrag/solana/.
"""

from __future__ import annotations

import argparse
import shutil
import tarfile
from pathlib import Path


DEFAULT_TARBALL = Path("third_party/solana-rag/solana-knowledge-pack.tgz")
DEFAULT_DEST = Path("var/lightrag/solana")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tarball",
        type=Path,
        default=DEFAULT_TARBALL,
        help=f"Location of the knowledge pack archive (default: {DEFAULT_TARBALL})",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"Directory to unpack into (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the destination if it already contains data.",
    )
    return parser.parse_args()


def unpack_knowledge_pack(tarball: Path, dest: Path, force: bool) -> None:
    if not tarball.exists():
        raise FileNotFoundError(f"Knowledge pack not found at {tarball}")

    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    # Remove existing contents if forced; otherwise ensure directory is empty.
    contents = list(dest.iterdir())
    if contents:
        if not force:
            raise FileExistsError(
                f"Destination {dest} is not empty; use --force to overwrite."
            )
        for path in contents:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    with tarfile.open(tarball, mode="r:gz") as archive:
        extract_kwargs = {}
        if hasattr(tarfile, "data_filter"):
            extract_kwargs["filter"] = "data"
        archive.extractall(dest, **extract_kwargs)

    print(f"Knowledge pack unpacked to {dest}")


def main() -> None:
    args = parse_args()
    unpack_knowledge_pack(args.tarball, args.dest, args.force)


if __name__ == "__main__":
    main()
