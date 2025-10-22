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
    # Optional absolute/relative path to the template root directory.
    # When provided, this path takes precedence over the default templates/ lookup.
    template_path: Path | None = None


_TEMPLATE_ROOT = Path(__file__).resolve().parents[3] / "templates"


def available_templates() -> list[str]:
    """Return a list of available template keys.

    Prefer the blueprint registry (src/solcoder/anchor/blueprints/registry.json). Fallback to
    legacy templates/ directory if the registry is unavailable (dev-only).
    """
    try:
        # Lazy import to avoid heavy CLI deps at module import time
        from solcoder.cli.blueprints import load_registry  # type: ignore

        entries = load_registry()
        keys = [e.key for e in entries if e.key]
        if keys:
            return sorted(set(keys))
    except Exception:
        pass
    if _TEMPLATE_ROOT.exists():
        return sorted(p.name for p in _TEMPLATE_ROOT.iterdir() if p.is_dir())
    return []


def render_template(options: RenderOptions) -> Path:
    """Render a template into the destination directory.

    Resolution order:
    1) Explicit options.template_path (if provided)
    2) Registry template_path for the given template key
    3) Legacy templates/<key> directory (dev-only fallback)
    """
    template_dir: Path | None = options.template_path
    if template_dir is None:
        # Try registry
        try:
            from solcoder.cli.blueprints import (
                load_registry,  # type: ignore
                resolve_registry_template_path,  # type: ignore
            )

            entry = next((e for e in load_registry() if e.key == options.template), None)
            if entry is not None and entry.template_path:
                resolved = resolve_registry_template_path(entry.template_path)
                if resolved is not None and resolved.exists():
                    template_dir = resolved
        except Exception:
            template_dir = None
    if template_dir is None:
        candidate = _TEMPLATE_ROOT / options.template
        if candidate.exists():
            template_dir = candidate
    if template_dir is None or not template_dir.exists():
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
    _rename_placeholder_paths(destination, replacements)
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


def _rename_placeholder_paths(root: Path, replacements: Dict[str, str]) -> None:
    """Rename any files or directories whose names contain {{PLACEHOLDER}} tokens.

    This supports new blueprint bundles that include templated path segments like
    programs/{{PROGRAM_NAME_SNAKE}}/...
    """
    # Collect all paths (files and dirs), sort by descending path length so we rename
    # deepest items first to avoid breaking parent traversal.
    all_paths = sorted((p for p in root.rglob("*")), key=lambda p: len(str(p)), reverse=True)
    for path in all_paths:
        name = path.name
        if "{{" not in name or "}}" not in name:
            continue
        new_name = name
        for key, value in replacements.items():
            new_name = new_name.replace(f"{{{{{key}}}}}", value)
        if new_name != name:
            target = path.with_name(new_name)
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                path.rename(target)
            except Exception:
                # Best-effort; ignore if rename fails for any reason
                pass
