"""Helpers for template-related CLI commands."""

from __future__ import annotations

from pathlib import Path

from solcoder.core import RenderOptions


def parse_template_tokens(
    template_name: str,
    tokens: list[str],
    defaults: dict[str, str],
) -> tuple[RenderOptions | None, str | None]:
    destination: Path | None = None
    program_name = defaults["program_name"]
    author = defaults["author_pubkey"]
    program_id = "replace-with-program-id"
    cluster = "devnet"
    overwrite = False

    idx = 0
    while idx < len(tokens):
        option = tokens[idx]
        if option == "--force":
            overwrite = True
            idx += 1
            continue
        if option == "--program" and idx + 1 < len(tokens):
            program_name = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--program="):
            program_name = option.split("=", 1)[1]
            idx += 1
            continue
        if option == "--author" and idx + 1 < len(tokens):
            author = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--author="):
            author = option.split("=", 1)[1]
            idx += 1
            continue
        if option == "--program-id" and idx + 1 < len(tokens):
            program_id = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--program-id="):
            program_id = option.split("=", 1)[1]
            idx += 1
            continue
        if option == "--cluster" and idx + 1 < len(tokens):
            cluster = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--cluster="):
            cluster = option.split("=", 1)[1]
            idx += 1
            continue
        if option.startswith("-"):
            return None, f"Unknown option '{option}'."
        if destination is None:
            destination = Path(option)
            idx += 1
            continue
        return None, "Unexpected extra argument."

    if destination is None:
        return None, "Destination path is required."

    options = RenderOptions(
        template=template_name,
        destination=destination,
        program_name=program_name,
        author_pubkey=author,
        program_id=program_id,
        cluster=cluster,
        overwrite=overwrite,
    )
    return options, None


__all__ = ["parse_template_tokens"]
