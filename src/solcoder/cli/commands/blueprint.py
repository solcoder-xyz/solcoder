"""Internal blueprint scaffolder invoked via agent dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core import RenderOptions, TemplateError, render_template
from solcoder.cli.blueprints import (
    persist_answers_readme,
    normalise_program_name,
    resolve_registry_template_path,
)
from solcoder.solana import deploy as deploy_mod
import re
import shutil

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args or args[0] != "scaffold":
            return CommandResponse(messages=[("system", "Usage: /blueprint scaffold --key <key> --target <dir> [--workspace <dir>] --answers-json <json>")])
        key: str | None = None
        target: Path | None = None
        workspace: Path | None = None
        answers_json: str | None = None
        force: bool = False

        i = 1
        while i < len(args):
            tok = args[i]
            if tok == "--key" and i + 1 < len(args):
                key = args[i + 1]
                i += 2
                continue
            if tok == "--target" and i + 1 < len(args):
                target = Path(args[i + 1]).expanduser()
                i += 2
                continue
            if tok == "--workspace" and i + 1 < len(args):
                ws_arg = args[i + 1]
                if ws_arg.strip().lower() == "auto":
                    # Resolve from active project or Anchor.toml upward from CWD
                    active = getattr(app.session_context.metadata, "active_project", None)
                    if active and (Path(active).expanduser() / "Anchor.toml").exists():
                        workspace = Path(active).expanduser()
                    else:
                        # Try detect from current working directory
                        def _find_anchor_root(start: Path) -> Path | None:
                            try:
                                cur = start.resolve()
                            except Exception:
                                cur = start.expanduser()
                            for parent in [cur, *cur.parents]:
                                if (parent / "Anchor.toml").exists():
                                    return parent
                            return None
                        detected = _find_anchor_root(Path.cwd())
                        if detected is not None:
                            workspace = detected
                        else:
                            workspace = None
                else:
                    workspace = Path(ws_arg).expanduser()
                i += 2
                continue
            if tok == "--answers-json" and i + 1 < len(args):
                answers_json = args[i + 1]
                i += 2
                continue
            if tok == "--force":
                force = True
                i += 1
                continue
            return CommandResponse(messages=[("system", f"Unknown or misplaced arg '{tok}'.")])

        if not key or target is None or answers_json is None:
            return CommandResponse(messages=[("system", "Missing required args. See /blueprint scaffold --help")])
        try:
            answers = json.loads(answers_json)
        except json.JSONDecodeError:
            return CommandResponse(messages=[("system", "Invalid answers JSON.")])

        program_name = answers.get("program_name") or key
        author = answers.get("author_pubkey") or getattr(app.wallet_manager.status(), "public_key", None) or "CHANGEME"
        cfg_ctx = getattr(app, "config_context", None)
        network = None
        if cfg_ctx is not None and getattr(cfg_ctx, "config", None) is not None:
            network = getattr(cfg_ctx.config, "network", None)
        cluster = answers.get("cluster") or network or "devnet"
        program_id = answers.get("program_id") or "replace-with-program-id"

        # Insertion into existing workspace if provided
        if workspace is not None and (workspace / "Anchor.toml").exists():
            with app.console.status(f"Adding '{program_name}' to Anchor workspace…", spinner="dots"):
                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir_str:
                    tmpdir = Path(tmpdir_str)
                    staging_root = tmpdir / "scaffold"
                    # Attempt to resolve registry template path if available
                    from solcoder.cli.blueprints import load_registry

                    reg = {e.key: e for e in load_registry()}
                    tpl_path = None
                    if key in reg and reg[key].template_path:
                        tpl_path = resolve_registry_template_path(reg[key].template_path)
                    opts = RenderOptions(
                        template=key,
                        destination=staging_root,
                        program_name=program_name,
                        author_pubkey=author,
                        cluster=cluster,
                        program_id=program_id,
                        overwrite=force,
                        template_path=tpl_path,
                    )
                    render_template(opts)
                    src_prog = staging_root / "programs" / normalise_program_name(program_name)
                    dst_prog = workspace / "programs" / src_prog.name
                    if dst_prog.exists():
                        if not force:
                            return CommandResponse(messages=[("system", f"Program '{src_prog.name}' already exists. Re-run with --force to overwrite.")])
                        shutil.rmtree(dst_prog)
                    shutil.copytree(src_prog, dst_prog)
                    # copy tests
                    (workspace / "tests").mkdir(parents=True, exist_ok=True)
                    for test_file in (staging_root / "tests").glob("*.ts"):
                        shutil.copy2(test_file, workspace / "tests" / test_file.name)
                    # copy scripts (helper demos)
                    src_scripts = staging_root / "scripts"
                    if src_scripts.exists():
                        (workspace / "scripts").mkdir(parents=True, exist_ok=True)
                        for script_file in src_scripts.glob("*"):
                            if script_file.is_file():
                                shutil.copy2(script_file, workspace / "scripts" / script_file.name)
                    # patch Anchor.toml
                    anchor_toml = workspace / "Anchor.toml"
                    text = anchor_toml.read_text()
                    sect = f"[programs.{cluster}]"
                    prog_line = f"{src_prog.name} = \"{program_id}\""
                    if sect in text:
                        if prog_line not in text:
                            text = re.sub(rf"(?m)^\[programs\.{re.escape(cluster)}\]\s*$", f"\\g<0>\n{prog_line}", text)
                    else:
                        text = text.rstrip() + f"\n\n{sect}\n{prog_line}\n"
                    anchor_toml.write_text(text)
                    try:
                        cfg = deploy_mod.load_anchor_config(anchor_toml)
                        deploy_mod.ensure_toolchain_version(
                            anchor_toml,
                            cfg,
                            anchor_version=deploy_mod.detect_anchor_cli_version(),
                        )
                    except Exception:
                        pass
                    # patch Cargo.toml
                    cargo = workspace / "Cargo.toml"
                    ctext = cargo.read_text() if cargo.exists() else ""
                    member = f"\"programs/{src_prog.name}\""
                    if member not in ctext:
                        if re.search(r"(?s)\[workspace\].*members\s*=\s*\[", ctext):
                            ctext = re.sub(r"(?s)(members\s*=\s*\[)(.*?)(\])", lambda m: m.group(1) + (m.group(2).rstrip() + (",\n    " if m.group(2).strip() else "\n    ") + member) + "\n]", ctext)
                        else:
                            ctext += f"\n[workspace]\nmembers = [\n    {member},\n]\n"
                        cargo.write_text(ctext)
                    persist_answers_readme(workspace, answers)

            app.session_context.metadata.active_project = str(workspace)
            app.session_manager.save(app.session_context)
            return CommandResponse(messages=[("system", f"Program '{program_name}' added to workspace {workspace}.")])

        # Otherwise, scaffold fresh workspace at target
        with app.console.status(f"Scaffolding '{key}' blueprint…", spinner="dots"):
            try:
                from solcoder.cli.blueprints import load_registry
                reg = {e.key: e for e in load_registry()}
                tpl_path = None
                if key in reg and reg[key].template_path:
                    tpl_path = resolve_registry_template_path(reg[key].template_path)
                opts = RenderOptions(
                    template=key,
                    destination=target,
                    program_name=program_name,
                    author_pubkey=author,
                    cluster=cluster,
                    program_id=program_id,
                    overwrite=force,
                    template_path=tpl_path,
                )
                output = render_template(opts)
            except TemplateError as exc:
                return CommandResponse(messages=[("system", f"Template error: {exc}")])
        persist_answers_readme(target, answers)
        try:
            (target / "blueprint.answers.json").write_text(json.dumps(answers, indent=2))
        except Exception:
            pass
        app.session_context.metadata.active_project = str(target)
        app.session_manager.save(app.session_context)
        try:
            anchor_path = target / "Anchor.toml"
            if anchor_path.exists():
                cfg = deploy_mod.load_anchor_config(anchor_path)
                deploy_mod.ensure_toolchain_version(
                    anchor_path,
                    cfg,
                    anchor_version=deploy_mod.detect_anchor_cli_version(),
                )
        except Exception:
            pass
        return CommandResponse(messages=[("system", f"Blueprint '{key}' rendered to {target}")])

    router.register(SlashCommand("blueprint", handle, "Internal blueprint scaffolder"))


__all__ = ["register"]
