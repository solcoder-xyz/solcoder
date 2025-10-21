"""Blueprint pipeline: /new <key> with optional wizard + render."""

from __future__ import annotations

from pathlib import Path
import tempfile
import shutil
import re
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core import RenderOptions, TemplateError, available_templates, render_template
from solcoder.cli.blueprints import load_registry, load_wizard_schema, prompt_wizard
import json

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


KNOWN_KEYS = {"counter", "token", "nft", "registry", "escrow"}


def _prompt_or_default(app: CLIApp, prompt: str, default: str) -> str:
    try:
        resp = app._prompt_text(f"{prompt} [{default}]")
        return resp.strip() or default
    except Exception:
        return default


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /new command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            keys = ", ".join(sorted(KNOWN_KEYS))
            return CommandResponse(messages=[("system", f"Usage: /new <key> [--dir <path>] [--program <name>] [--author <pubkey>] [--cluster <cluster>] [--program-id <id>] [--force]\nAvailable keys: {keys}")])

        key = args[0].strip().lower()
        # Parse flags
        dest: Path | None = None
        program_name: str | None = None
        author: str | None = None
        program_id: str | None = None
        cluster: str | None = None
        force = False

        i = 1
        while i < len(args):
            tok = args[i]
            if tok == "--dir" and i + 1 < len(args):
                dest = Path(args[i + 1]).expanduser()
                i += 2
                continue
            if tok == "--program" and i + 1 < len(args):
                program_name = args[i + 1]
                i += 2
                continue
            if tok == "--author" and i + 1 < len(args):
                author = args[i + 1]
                i += 2
                continue
            if tok == "--program-id" and i + 1 < len(args):
                program_id = args[i + 1]
                i += 2
                continue
            if tok == "--cluster" and i + 1 < len(args):
                cluster = args[i + 1]
                i += 2
                continue
            if tok == "--force":
                force = True
                i += 1
                continue
            return CommandResponse(messages=[("system", f"Unknown or misplaced argument '{tok}'.")])

        # Key mapping / selection
        templates = set(available_templates())
        registry = load_registry()
        if key not in KNOWN_KEYS:
            # Free-text: try LLM minimal selection first with strict JSON; fall back to prompt
            try:
                reg = load_registry()
                options_list = [e.key for e in reg if e.key]
                if not options_list:
                    options_list = sorted(KNOWN_KEYS)
                options_str = ", ".join(options_list)
                system = (
                    "You are a strict router. Select exactly one blueprint key from the provided list. "
                    "Respond ONLY with a minified JSON object of the form {\"key\":\"<value>\"} where <value> is one of the allowed keys."
                )
                user = (
                    f"Allowed keys: [{options_str}]\\n"
                    f"Request: {' '.join(args)}\\n"
                    "Return strictly: {\"key\":\"<one_of_allowed>\"}"
                )
                resp = app._llm.stream_chat(user, system_prompt=system, history=None)
                raw = (resp.text or "").strip()
                candidate_key: str | None = None
                # Try JSON parse first
                try:
                    obj = json.loads(raw)
                    val = obj.get("key") if isinstance(obj, dict) else None
                    if isinstance(val, str):
                        candidate_key = val.strip().lower()
                except Exception:
                    # Try to extract with a simple pattern
                    m = re.search(r'"key"\s*:\s*"([a-zA-Z0-9_-]+)"', raw)
                    if m:
                        candidate_key = m.group(1).lower()
                if candidate_key in KNOWN_KEYS:
                    key = candidate_key  # type: ignore[assignment]
                else:
                    raise ValueError("invalid llm selection JSON")
            except Exception:
                options = ", ".join(sorted(KNOWN_KEYS))
                chosen = _prompt_or_default(app, f"Select a blueprint key ({options})", "counter")
                key = chosen.strip().lower()
                if key not in KNOWN_KEYS:
                    return CommandResponse(messages=[("system", f"Invalid key '{key}'. Available: {options}")])

        # Wizard (load per-blueprint schema if available)
        defaults = app._default_template_metadata()
        wizard_qs = load_wizard_schema(key)
        answers: dict[str, any] = {}
        if wizard_qs:
            # seed defaults
            cfg_ctx = getattr(app, "config_context", None)
            network = None
            if cfg_ctx is not None and getattr(cfg_ctx, "config", None) is not None:
                network = getattr(cfg_ctx.config, "network", None)
            seed = {
                "program_name": program_name or defaults.get("program_name", key),
                "author_pubkey": author or defaults.get("author_pubkey", "CHANGEME"),
                "cluster": cluster or network or "devnet",
                "program_id": program_id or "replace-with-program-id",
            }
            answers = prompt_wizard(app, wizard_qs, seed)
            program_name = answers.get("program_name") or seed["program_name"]
            author = answers.get("author_pubkey") or seed["author_pubkey"]
            cluster = answers.get("cluster") or seed["cluster"]
            program_id = answers.get("program_id") or seed["program_id"]
        else:
            if program_name is None:
                program_name = _prompt_or_default(app, "Program name", defaults.get("program_name", key))
            if author is None:
                author = defaults.get("author_pubkey", "CHANGEME")
            if cluster is None:
                cfg = getattr(app, "config_context", None)
                cluster = getattr(getattr(cfg, "config", None), "network", "devnet")
            if program_id is None:
                program_id = "replace-with-program-id"

        # Destination base (used both for scaffold and for workspace detection)
        base_dir = dest or Path.cwd()

        # Detect existing Anchor workspace to insert program under programs/
        def _find_anchor_root(start: Path) -> Path | None:
            try:
                cur = start.resolve()
            except Exception:
                cur = start.expanduser()
            for parent in [cur, *cur.parents]:
                if (parent / "Anchor.toml").exists():
                    return parent
            return None

        workspace_root = _find_anchor_root(base_dir)

        # Resolve template path from registry if present; otherwise fallback to templates/
        template_path = None
        try:
            entry = next((e for e in registry if e.key == key), None)
            if entry is not None and entry.template_path:
                template_path = Path(entry.template_path).expanduser().resolve()
        except Exception:
            template_path = None
        if template_path is None and key not in templates:
            msg = (
                f"Blueprint '{key}' is not available locally. Available templates: {', '.join(sorted(templates)) or '(none)'}"
            )
            return CommandResponse(messages=[("system", msg)])

        if workspace_root is not None:
            # Hand off insertion to agent/CLI via /blueprint scaffold
            try:
                answers_json = json.dumps(answers or {
                    "program_name": program_name,
                    "author_pubkey": author,
                    "cluster": cluster or "devnet",
                    "program_id": program_id,
                }, separators=(",", ":"))
            except Exception:
                answers_json = "{}"
            import shlex as _shlex
            cmd_parts = [
                "/blueprint",
                "scaffold",
                "--key",
                key,
                "--target",
                str(workspace_root),
                "--workspace",
                str(workspace_root),
                "--answers-json",
                answers_json,
            ]
            dispatch = " ".join(_shlex.quote(p) for p in cmd_parts)
            # Execute immediately for synchronous behavior in CLI/tests
            routed = app.command_router.dispatch(app, dispatch[1:] if dispatch.startswith("/") else dispatch)
            return routed

        # Otherwise scaffold a fresh workspace at dest
        dest = base_dir if dest is not None else (Path.cwd() / f"{program_name}-workspace")
        options = RenderOptions(
            template=key,
            destination=dest,
            program_name=program_name,
            author_pubkey=author,
            program_id=program_id,
            cluster=cluster or "devnet",
            overwrite=force,
            template_path=template_path,
        )
        # Hand off fresh scaffold to agent/CLI via /blueprint scaffold
        try:
            answers_json = json.dumps(answers or {
                "program_name": program_name,
                "author_pubkey": author,
                "cluster": cluster or "devnet",
                "program_id": program_id,
            }, separators=(",", ":"))
        except Exception:
            answers_json = "{}"
        target_dir = dest
        import shlex as _shlex
        cmd_parts = [
            "/blueprint",
            "scaffold",
            "--key",
            key,
            "--target",
            str(target_dir),
            "--answers-json",
            answers_json,
        ]
        dispatch = " ".join(_shlex.quote(p) for p in cmd_parts)
        routed = app.command_router.dispatch(app, dispatch[1:] if dispatch.startswith("/") else dispatch)
        return routed

    router.register(
        SlashCommand(
            "new",
            handle,
            "Create a new blueprint: /new <key> [--dir <path>] [--program <name>] [--author <pubkey>] [--cluster <cluster>] [--program-id <id>] [--force]",
        )
    )


__all__ = ["register"]
