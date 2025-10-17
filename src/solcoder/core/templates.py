"""Template rendering utilities."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


class TemplateError(RuntimeError):
    """Base error for template operations."""


class TemplateNotFoundError(TemplateError):
    """Raised when the requested template does not exist."""


class TemplateExistsError(TemplateError):
    """Raised when attempting to render into an existing directory without force."""


@dataclass
class RenderOptions:
    template: str
    destination: Path
    program_name: str = "counter"
    author_pubkey: str = "CHANGEME"
    program_id: str = "replace-with-program-id"
    cluster: str = "devnet"
    overwrite: bool = False


_TEMPLATE_ROOT = Path(__file__).resolve().parents[3] / "templates"


def available_templates() -> list[str]:
    if not _TEMPLATE_ROOT.exists():
        return []
    return sorted(p.name for p in _TEMPLATE_ROOT.iterdir() if p.is_dir())


def render_template(options: RenderOptions) -> Path:
    template_dir = _TEMPLATE_ROOT / options.template
    if not template_dir.exists():
        raise TemplateNotFoundError(f"Template '{options.template}' not found.")

    destination = options.destination.expanduser().resolve()
    if destination.exists():
        if not options.overwrite:
            raise TemplateExistsError(f"Destination '{destination}' already exists.")
        if any(destination.iterdir()):
            raise TemplateExistsError(
                f"Destination '{destination}' must be empty when overwriting."
            )
        shutil.rmtree(destination)

    program_snake = _normalise_program_name(options.program_name)
    program_pascal = "".join(part.capitalize() for part in re.split(r"[_\\-\\s]+", program_snake) if part)
    program_title = program_pascal.replace("_", " ")
    replacements: Dict[str, str] = {
        "PROGRAM_NAME_SNAKE": program_snake,
        "PROGRAM_NAME_PASCAL": program_pascal,
        "PROGRAM_NAME_TITLE": program_title,
        "PROGRAM_NAME_RAW": options.program_name,
        "AUTHOR_PUBKEY": options.author_pubkey,
        "PROGRAM_ID": options.program_id,
        "CLUSTER": options.cluster,
    }

    shutil.copytree(template_dir, destination)
    _apply_replacements(destination, replacements)
    _rename_paths(destination, program_snake)
    return destination


def _normalise_program_name(name: str) -> str:
    base = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip())
    base = base.lower().strip("_")
    return base or "counter"


def _apply_replacements(root: Path, replacements: Dict[str, str]) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            text = path.read_text()
            for key, value in replacements.items():
                text = text.replace(f"{{{{{key}}}}}", value)
            path.write_text(text)


def _rename_paths(root: Path, program_snake: str) -> None:
    renames = {
        root / "programs" / "counter": root / "programs" / program_snake,
        root / "tests" / "counter.ts": root / "tests" / f"{program_snake}.ts",
    }
    for source, target in renames.items():
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
