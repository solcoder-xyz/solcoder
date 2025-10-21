"""Initialize an Anchor workspace at a target directory."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def _find_anchor_root(start: Path) -> Path | None:
    """Search upwards from start for an Anchor.toml, return its parent if found."""
    try:
        cur = start.resolve()
    except Exception:
        cur = start.expanduser()
    for parent in [cur, *cur.parents]:
        if (parent / "Anchor.toml").exists():
            return parent
    return None


def _dir_non_empty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _offline_scaffold(root: Path, *, name: str, force: bool) -> None:
    if _dir_non_empty(root) and not force:
        raise FileExistsError(
            f"Directory {root} is not empty. Use --force to scaffold minimal workspace."
        )
    root.mkdir(parents=True, exist_ok=True)
    # Minimal Anchor.toml & Cargo.toml
    anchor_toml = (
        "[workspace]\n"
        "\n[provider]\ncluster = \"devnet\"\n"
        "\n[programs.devnet]\n"
        f"{name} = \"replace-with-program-id\"\n"
    )
    cargo_toml = (
        "[workspace]\n"
        "members = [\n]\n"
    )
    gitignore = (
        "target/\nnode_modules/\n.DS_Store\n.marshal-cache/\n"  # common
    )
    readme = (
        f"# {name} — Anchor Workspace\n\n"
        "This is a minimal Anchor workspace scaffold.\n\n"
        "Next steps:\n\n"
        "- Install Anchor: `/env install anchor`\n"
        "- Build: `anchor build`\n"
        "- Use `/new <key>` to add a program under `programs/`\n"
    )
    _write_file(root / "Anchor.toml", anchor_toml)
    _write_file(root / "Cargo.toml", cargo_toml)
    _write_file(root / ".gitignore", gitignore)
    _write_file(root / "README.md", readme)
    (root / "programs").mkdir(parents=True, exist_ok=True)


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /init command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        # Parse flags: /init [DIRECTORY] [--name <workspace_name>] [--force] [--offline]
        target: Path | None = None
        name: str | None = None
        force = False
        offline = False

        i = 0
        while i < len(args):
            tok = args[i]
            if tok == "--name" and i + 1 < len(args):
                name = args[i + 1]
                i += 2
                continue
            if tok == "--force":
                force = True
                i += 1
                continue
            if tok == "--offline":
                offline = True
                i += 1
                continue
            if tok.startswith("--"):
                return CommandResponse(messages=[("system", f"Unknown option '{tok}'.")])
            # first non-flag is directory
            if target is None:
                target = Path(tok).expanduser()
                i += 1
                continue
            return CommandResponse(messages=[("system", "Unexpected extra argument.")])

        if target is None:
            target = Path.cwd()

        # Resolve name default
        if name is None:
            try:
                name = target.resolve().name or "anchor_workspace"
            except Exception:
                name = target.name or "anchor_workspace"

        # If Anchor workspace already exists (Anchor.toml up the tree), set active project and exit
        existing_root = _find_anchor_root(target)
        if existing_root is not None:
            app.session_context.metadata.active_project = str(existing_root)
            app.session_manager.save(app.session_context)
            app.log_event("build", f"Anchor workspace detected at {existing_root}")
            return CommandResponse(
                messages=[
                    (
                        "system",
                        f"Anchor workspace already initialized at {existing_root}. Active project set. Use `/new <key>` to add a program.",
                    )
                ]
            )

        # Prefer anchor CLI if available and not offline, creating the directory if necessary
        if not offline and shutil.which("anchor") is not None:
            parent = target.parent if not target.exists() else target
            create_in_parent = not target.exists()
            project_name = name
            try:
                if create_in_parent:
                    parent.mkdir(parents=True, exist_ok=True)
                    # Run `anchor init <name>` in parent, which creates <name>/
                    cmd = ["anchor", "init", project_name]
                    result = subprocess.run(cmd, cwd=str(parent), capture_output=True, text=True, check=False)
                    if result.returncode != 0:
                        err = result.stderr.strip() or result.stdout.strip() or "anchor init failed"
                        return CommandResponse(messages=[("system", f"Anchor init failed: {err}")])
                    workspace_root = parent / project_name
                else:
                    # Directory exists; scaffold offline to avoid anchor refusing to overwrite
                    _offline_scaffold(target, name=project_name, force=force)
                    workspace_root = target
            except FileExistsError as exc:
                return CommandResponse(messages=[("system", str(exc))])
        else:
            # Offline scaffold path
            try:
                _offline_scaffold(target, name=name, force=force)
            except FileExistsError as exc:
                return CommandResponse(messages=[("system", str(exc))])
            workspace_root = target

        # Persist active project and return summary
        app.session_context.metadata.active_project = str(workspace_root)
        app.session_manager.save(app.session_context)
        app.log_event("build", f"Anchor workspace initialized at {workspace_root}")
        summary = (
            f"Anchor workspace initialized at {workspace_root}.\n"
            "Next steps:\n"
            "  - /new counter (or token, nft, registry, escrow)\n"
            "  - /deploy once ready to build and deploy"
        )
        return CommandResponse(messages=[("system", summary)])

    router.register(
        SlashCommand(
            "init",
            handle,
            "Initialize an Anchor workspace: /init [DIRECTORY] [--name <workspace>] [--force] [--offline]",
        )
    )


__all__ = ["register"]

