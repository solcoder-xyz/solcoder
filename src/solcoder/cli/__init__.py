"""CLI package for SolCoder."""

from __future__ import annotations

import json
import logging
import os
import sys
from importlib import metadata
from pathlib import Path
from typing import Optional

import click
import typer
import typer.rich_utils
from typer.core import TyperOption

from solcoder.core import (
    DEFAULT_CONFIG_DIR,
    ConfigContext,
    ConfigManager,
    TemplateError,
    render_template,
)
from solcoder.core.config import CONFIG_FILENAME
from solcoder.core.llm import LLMClient, LLMError, LLMSettings
from solcoder.session import SessionLoadError, SessionManager
from solcoder.session.manager import MAX_SESSIONS
from solcoder.solana import SolanaRPCClient, WalletError, WalletManager
from datetime import UTC, datetime
import time

from .app import CLIApp
from .template_utils import parse_template_tokens
from .branding import themed_console

typer.rich_utils.USE_RICH = False

_original_make_metavar = TyperOption.make_metavar
if _original_make_metavar.__code__.co_argcount == 2:  # Click>=8.3 signature requires ctx
    def _patched_make_metavar(self: TyperOption, ctx: click.Context | None = None) -> str:
        if ctx is None:
            ctx = click.Context(click.Command(name=self.name or "option"))
        return _original_make_metavar(self, ctx)

    TyperOption.make_metavar = _patched_make_metavar  # type: ignore[assignment]

_rich_print_options_panel = typer.rich_utils._print_options_panel


def _compat_print_options_panel(*, name, params, ctx, markup_mode, console) -> None:
    patched: list[click.Parameter] = []
    for param in params:
        if getattr(param, "_solcoder_make_metavar_patched", False):
            continue
        original = param.make_metavar

        def _wrap_make_metavar(orig=original) -> callable:
            def _inner() -> str:
                try:
                    return orig()
                except TypeError:
                    return orig(ctx)

            return _inner

        param.make_metavar = _wrap_make_metavar()  # type: ignore[assignment]
        param._solcoder_make_metavar_patched = True
        patched.append(param)

    return _rich_print_options_panel(
        name=name,
        params=params,
        ctx=ctx,
        markup_mode=markup_mode,
        console=console,
    )


typer.rich_utils._print_options_panel = _compat_print_options_panel  # type: ignore[assignment]


app = typer.Typer(invoke_without_command=True, help="SolCoder CLI agent", no_args_is_help=False)

CLI_CONSOLE = themed_console()
setattr(CLI_CONSOLE, "_solcoder_theme_applied", True)


def styled_echo(message: str = "", *, nl: bool = True) -> None:
    """Print using the SolCoder themed console."""
    CLI_CONSOLE.print(message, end="" if not nl else "\n")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"", "0", "false", "no"}


def _parse_direct_launch_args(args: list[str]) -> tuple[bool, str | None, bool, Path | None] | str | None:
    verbose = _env_flag("SOLCODER_DEBUG", default=False)
    session: str | None = None
    new_session = False
    config_path: Path | None = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"--help", "-h"}:
            return None
        if arg in {"--version", "-V"}:
            return "version"
        if arg in {"--verbose", "-v"}:
            verbose = True
            i += 1
            continue
        if arg == "--new-session":
            new_session = True
            i += 1
            continue
        if arg.startswith("--new-session="):
            value = arg.split("=", 1)[1]
            new_session = value.strip().lower() not in {"", "0", "false", "no"}
            i += 1
            continue
        if arg == "--session":
            if i + 1 >= len(args):
                styled_echo("❌ Option '--session' requires a session id.")
                raise typer.Exit(code=2)
            session = args[i + 1]
            i += 2
            continue
        if arg.startswith("--session="):
            session = arg.split("=", 1)[1]
            i += 1
            continue
        if arg == "--config":
            if i + 1 >= len(args):
                styled_echo("❌ Option '--config' requires a file path.")
                raise typer.Exit(code=2)
            config_path = Path(args[i + 1]).expanduser()
            i += 2
            continue
        if arg.startswith("--config="):
            config_path = Path(arg.split("=", 1)[1]).expanduser()
            i += 1
            continue
        if arg.startswith("-"):
            return None
        return None
    return verbose, session, new_session, config_path


def _render_template_cli(template_name: str, tokens: list[str]) -> None:
    defaults = {"program_name": template_name, "author_pubkey": "CHANGEME"}
    options, error = parse_template_tokens(template_name, tokens, defaults)
    if error or options is None:
        styled_echo(f"❌ {error or 'Unable to render template.'}")
        raise typer.Exit(code=2)
    try:
        output = render_template(options)
    except TemplateError as exc:
        styled_echo(f"❌ {exc}")
        raise typer.Exit(code=1)
    styled_echo(f"✅ Template '{template_name}' rendered to {output}")


def _configure_logging(verbose: bool, log_dir: Path | None) -> None:
    root_logger = logging.getLogger()
    if verbose:
        if not root_logger.handlers:
            logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        root_logger.setLevel(logging.DEBUG)
    else:
        if root_logger.handlers:
            root_logger.setLevel(logging.WARNING)
        else:
            logging.basicConfig(level=logging.WARNING, format="%(message)s")
    if verbose and log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_dir / "solcoder.log", encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)


def _format_session_text(export_data: dict[str, object]) -> str:
    metadata = export_data.get("metadata", {})
    transcript = export_data.get("transcript", [])
    lines = ["Session Export", "=============="]
    if isinstance(metadata, dict):
        for key in ("session_id", "created_at", "updated_at", "active_project", "wallet_status", "wallet_balance", "spend_amount"):
            value = metadata.get(key)
            if value is not None:
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
    lines.append("")
    lines.append("Transcript (most recent first):")
    if isinstance(transcript, list) and transcript:
        for entry in transcript:
            if isinstance(entry, dict):
                role = entry.get("role", "?")
                message = entry.get("message", "")
                lines.append(f"[{role}] {message}")
            else:
                lines.append(str(entry))
    else:
        lines.append("(no transcript available)")
    return "\n".join(lines)


def _candidate_session_roots() -> list[Path]:
    """Return session directories to search, prioritizing project scope."""
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        expanded = path.expanduser()
        resolved = expanded.resolve()
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    add(Path.cwd() / ".solcoder" / "sessions")
    env_home = os.environ.get("SOLCODER_HOME")
    if env_home:
        add(Path(env_home) / "sessions")
    add(DEFAULT_CONFIG_DIR / "sessions")
    add(Path.home() / ".solcoder" / "sessions")
    return candidates


def _handle_dump_session(session_id: str, fmt: str, output: Path | None) -> None:
    fmt_normalized = fmt.lower()
    if fmt_normalized not in {"json", "text"}:
        styled_echo(f"❌ Unsupported dump format '{fmt}'. Use 'json' or 'text'.")
        raise typer.Exit(code=1)

    export_data: dict[str, object] | None = None
    searched_roots: list[Path] = []
    try:
        for root in _candidate_session_roots():
            manager = SessionManager(root=root)
            try:
                export_data = manager.export_session(session_id, redact=True)
                break
            except FileNotFoundError:
                searched_roots.append(root)
                continue
        if export_data is None:
            raise FileNotFoundError
    except FileNotFoundError:
        styled_echo(
            f"⚠️ Session '{session_id}' not found. Only the most recent {MAX_SESSIONS} sessions are retained."
        )
        if searched_roots:
            locations = ", ".join(str(path) for path in searched_roots)
            styled_echo(f"   Checked locations: {locations}")
        styled_echo("   Start a new session or increase retention via MAX_SESSIONS if needed.")
        raise typer.Exit(code=1)
    except SessionLoadError as exc:
        styled_echo(f"❌ Failed to load session '{session_id}': {exc}")
        raise typer.Exit(code=1)

    if fmt_normalized == "json":
        payload = json.dumps(export_data, indent=2)
    else:
        payload = _format_session_text(export_data)

    if output is not None:
        destination = output.expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload)
        try:
            os.chmod(destination, 0o600)
        except PermissionError:
            pass
        styled_echo(f"✅ Session {session_id} exported to {destination}")
    else:
        styled_echo(payload)

    raise typer.Exit()


def _resolve_project_paths() -> tuple[Path, Path, Path]:
    project_root = Path.cwd()
    project_home = project_root / ".solcoder"
    project_home.mkdir(parents=True, exist_ok=True)
    global_home = DEFAULT_CONFIG_DIR
    global_home.mkdir(parents=True, exist_ok=True)
    return project_root, project_home, global_home


def _show_balance(rpc_client: SolanaRPCClient | None, public_key: str | None) -> None:
    if rpc_client is None or not public_key:
        return
    try:
        balance = rpc_client.get_balance(public_key)
    except Exception as exc:  # noqa: BLE001
        styled_echo(f"[solcoder.log.warn]⚠️  Unable to fetch wallet balance[/] ({exc}).")
        return
    styled_echo(f"[#14F195]💰 Balance[/]: [#E6FFFA]{balance:.3f} SOL")


def _prompt_unlock(wallet_manager: WalletManager) -> None:
    attempts = 3
    while attempts > 0:
        passphrase = typer.prompt("Wallet passphrase", hide_input=True)
        try:
            wallet_manager.unlock_wallet(passphrase)
            styled_echo("🔓 Wallet unlocked.")
            return
        except WalletError:
            attempts -= 1
            if attempts > 0:
                styled_echo(f"❌ Incorrect passphrase. {attempts} attempts remaining.")
            else:
                styled_echo("⚠️  Wallet remains locked.")


def _bootstrap_wallet(
    wallet_manager: WalletManager,
    rpc_client: SolanaRPCClient | None,
    master_passphrase: str | None,
) -> datetime | None:
    def _ensure_passphrase(prompt: str = "Enter your SolCoder passphrase") -> str:
        nonlocal master_passphrase
        while not master_passphrase:
            master_passphrase = typer.prompt(prompt, hide_input=True)
        return master_passphrase

    if not wallet_manager.wallet_exists():
        styled_echo("\n🔐 No SolCoder wallet found. Let's create or restore one before continuing.")
        if master_passphrase:
            styled_echo("We'll reuse the passphrase you just set for SolCoder to keep everything in sync.")
        else:
            styled_echo("You'll secure the wallet with your SolCoder passphrase.")
        while True:
            choice = (
                typer.prompt("Create new wallet or restore existing? [c/r]", default="c")
                .strip()
                .lower()
            )
            if choice in {"c", "create"}:
                styled_echo("\nWe'll generate a recovery phrase. Store it securely—anyone with the phrase controls your funds.")
                status, mnemonic = wallet_manager.create_wallet(_ensure_passphrase(), force=True)
                styled_echo("✅ Wallet created and unlocked.")
                _show_balance(rpc_client, status.public_key)
                styled_echo("\n📝 Recovery phrase (write it down, keep it offline):")
                styled_echo(mnemonic)
                break
            if choice in {"r", "restore"}:
                method = (
                    typer.prompt("Restore from recovery phrase or backup file? [phrase/file]", default="phrase")
                    .strip()
                    .lower()
                )
                if method in {"file", "f"}:
                    path_input = typer.prompt("Path to wallet backup file")
                    secret_path = Path(path_input).expanduser()
                    if not secret_path.exists():
                        styled_echo("❌ File not found. Please try again.")
                        continue
                    secret = secret_path.read_text().strip()
                else:
                    secret = typer.prompt("Enter recovery phrase or JSON/base58 secret")
                try:
                    status, mnemonic = wallet_manager.restore_wallet(
                        secret,
                        _ensure_passphrase("Enter the SolCoder passphrase to encrypt your wallet"),
                        overwrite=True,
                    )
                except WalletError as exc:
                    styled_echo(f"❌ {exc}")
                    continue
                styled_echo("✅ Wallet restored.")
                try:
                    wallet_manager.unlock_wallet(_ensure_passphrase())
                    styled_echo("🔓 Wallet unlocked.")
                except WalletError:
                    styled_echo("⚠️  Unable to unlock wallet with provided passphrase; it will remain locked.")
                _show_balance(rpc_client, status.public_key)
                if mnemonic:
                    styled_echo("Recovery phrase stored from your input.")
                break

            else:
                styled_echo("Please choose 'c' (create) or 'r' (restore).")
        return None

    status = wallet_manager.status()
    if not status.is_unlocked:
        if master_passphrase:
            try:
                wallet_manager.unlock_wallet(master_passphrase)
            except WalletError:
                if typer.confirm("Stored passphrase didn't unlock the wallet. Enter it manually?", default=True):
                    _prompt_unlock(wallet_manager)
        else:
            if typer.confirm("Stored passphrase didn't unlock the wallet. Enter it manually?", default=True):
                _prompt_unlock(wallet_manager)

    airdrop_time: datetime | None = None
    # Offer a faucet airdrop on devnet/testnet if balance is 0
    try:
        endpoint = (rpc_client.endpoint if rpc_client else "").lower()
    except Exception:
        endpoint = ""
    is_test_cluster = ("devnet" in endpoint) or ("testnet" in endpoint)
    if rpc_client is not None and status.public_key and is_test_cluster:
        try:
            current_balance = rpc_client.get_balance(status.public_key)
        except Exception:
            current_balance = None
        if not current_balance or current_balance <= 0:
            if typer.confirm("No SOL found. Request 2 SOL airdrop now?", default=True):
                amount = 2.0
                with CLI_CONSOLE.status(f"Requesting {amount:.3f} SOL airdrop…", spinner="dots") as status_indicator:
                    # Retry a few times on faucet/internal errors
                    attempts = 3
                    delay = 2.0
                    sig = None
                    last_err = None
                    for i in range(attempts):
                        try:
                            sig = rpc_client.request_airdrop(status.public_key, amount)
                            last_err = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_err = exc
                            if i < attempts - 1:
                                status_indicator.update("Faucet busy; retrying shortly…")
                                time.sleep(delay)
                                delay *= 1.5
                                continue
                    if sig is None:
                        styled_echo(f"❌ Airdrop failed: {last_err}. Try again later or with a smaller amount.")
                        return None
                    deadline = time.time() + 30.0
                    final_balance = current_balance
                    while time.time() < deadline:
                        time.sleep(1.0)
                        try:
                            now = rpc_client.get_balance(status.public_key)
                        except Exception:
                            continue
                        final_balance = now
                        if (current_balance is None) or (now > (current_balance or 0.0)):
                            break
                        status_indicator.update("Waiting for airdrop confirmation…")
                if final_balance is not None:
                    styled_echo(f"✅ Airdrop submitted (sig: {sig}). New balance: {final_balance:.3f} SOL")
                    airdrop_time = datetime.now(UTC)
                else:
                    styled_echo("✅ Airdrop submitted. Balance will update shortly.")
                    airdrop_time = datetime.now(UTC)

    return airdrop_time

def _prepare_llm_client(
    config_manager: ConfigManager,
    config_context: ConfigContext,
    *,
    provider_override: str | None = None,
    base_url_override: str | None = None,
    model_override: str | None = None,
    reasoning_override: str | None = None,
    api_key_override: str | None = None,
    offline_mode: bool = False,
) -> LLMClient:
    updated = False
    if provider_override:
        config_context.config.llm_provider = provider_override
        updated = True
    if base_url_override:
        config_context.config.llm_base_url = base_url_override
        updated = True
    if model_override:
        config_context.config.llm_model = model_override
        updated = True
    if reasoning_override:
        config_context.config.llm_reasoning_effort = reasoning_override
        updated = True
    if api_key_override:
        config_context.llm_api_key = api_key_override

    offline = offline_mode or not config_context.llm_api_key
    api_key = None if offline else config_context.llm_api_key

    settings = LLMSettings(
        provider=config_context.config.llm_provider,
        base_url=config_context.config.llm_base_url,
        model=config_context.config.llm_model,
        api_key=api_key,
        offline_mode=offline,
        reasoning_effort=config_context.config.llm_reasoning_effort,
    )
    if updated:
        config_manager.update_llm_preferences(
            llm_base_url=config_context.config.llm_base_url,
            llm_model=config_context.config.llm_model,
            llm_reasoning_effort=config_context.config.llm_reasoning_effort,
        )
    return LLMClient(settings)


def _run_llm_dry_run(
    config_manager: ConfigManager,
    *,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    reasoning: str | None = None,
    api_key: str | None = None,
    offline_mode: bool = False,
) -> None:
    styled_echo("🔍 SolCoder LLM dry run")
    config_context = config_manager.ensure(
        interactive=True,
        llm_base_url=base_url,
        llm_model=model,
        llm_reasoning=reasoning,
        llm_api_key=api_key,
        offline_mode=offline_mode,
    )
    llm_client = _prepare_llm_client(
        config_manager,
        config_context,
        provider_override=provider,
        base_url_override=base_url,
        model_override=model,
        reasoning_override=reasoning,
        api_key_override=api_key,
        offline_mode=offline_mode,
    )

    tokens: list[str] = []

    def _on_chunk(chunk: str) -> None:
        tokens.append(chunk)
        styled_echo(chunk, nl=False)

    try:
        result = llm_client.stream_chat(
            "Say hello from SolCoder in one sentence.",
            history=(),
            on_chunk=_on_chunk,
        )
    except LLMError as exc:
        styled_echo(f"❌ LLM error: {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        llm_client.close()

    if tokens:
        styled_echo()
    status = "cached" if result.cached else "live"
    styled_echo(
        f"✅ LLM dry run completed in {result.latency_seconds:.2f}s using {config_context.config.llm_provider}:{config_context.config.llm_model} ({status}, reasoning={config_context.config.llm_reasoning_effort})"
    )
    raise typer.Exit()


def _launch_shell(
    verbose: bool,
    session: str | None,
    new_session: bool,
    config_file: Path | None,
    *,
    llm_provider: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    llm_reasoning: str | None = None,
    llm_api_key: str | None = None,
    offline_mode: bool = False,
    dry_run_llm: bool = False,
) -> None:
    project_root, project_home, global_home = _resolve_project_paths()
    _configure_logging(verbose, log_dir=project_home / "logs")

    config_override_path: Path | None = None
    if config_file is not None:
        config_override_path = config_file.expanduser()
        if not config_override_path.exists():
            styled_echo(f"❌ Config file '{config_override_path}' not found.")
            raise typer.Exit(code=1)
        config_override_path = config_override_path.resolve()

    project_config_path: Path | None = None
    if config_override_path is None:
        candidate = project_home / CONFIG_FILENAME
        if candidate.exists():
            project_config_path = candidate

    config_manager = ConfigManager(
        config_dir=global_home,
        project_config_path=project_config_path,
        override_config_path=config_override_path,
    )

    if dry_run_llm:
        _run_llm_dry_run(
            config_manager,
            provider=llm_provider,
            base_url=llm_base_url,
            model=llm_model,
            reasoning=llm_reasoning,
            api_key=llm_api_key,
            offline_mode=offline_mode,
        )
        return

    config_context = config_manager.ensure(
        interactive=True,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_reasoning=llm_reasoning,
        llm_api_key=llm_api_key,
        offline_mode=offline_mode,
    )

    llm_client: LLMClient | None = None
    try:
        llm_client = _prepare_llm_client(
            config_manager,
            config_context,
            provider_override=llm_provider,
            base_url_override=llm_base_url,
            model_override=llm_model,
            reasoning_override=llm_reasoning,
            api_key_override=llm_api_key,
            offline_mode=offline_mode,
        )
    except LLMError as exc:
        styled_echo(f"❌ Unable to initialize LLM client: {exc}")
        raise typer.Exit(code=1) from exc

    session_manager = SessionManager(root=project_home / "sessions")
    wallet_manager = WalletManager(keys_dir=global_home / "keys")
    rpc_client = SolanaRPCClient(endpoint=config_context.config.rpc_url)
    airdrop_time = _bootstrap_wallet(wallet_manager, rpc_client, config_context.passphrase)
    resume_id = None if new_session else session
    if resume_id:
        try:
            session_context = session_manager.start(resume_id, active_project=str(project_root))
        except FileNotFoundError:
            styled_echo(f"⚠️  Session '{resume_id}' not found; starting a new session.")
            session_context = session_manager.start(active_project=str(project_root))
        except SessionLoadError as exc:
            styled_echo(f"⚠️  {exc}. Starting a new session.")
            session_context = session_manager.start(active_project=str(project_root))
    else:
        session_context = session_manager.start(active_project=str(project_root))

    # Persist bootstrap airdrop timestamp if any
    if airdrop_time is not None:
        try:
            session_context.metadata.last_airdrop_at = airdrop_time
            session_manager.save(session_context)
        except Exception:
            pass

    try:
        CLIApp(
            config_context=config_context,
            config_manager=config_manager,
            session_context=session_context,
            session_manager=session_manager,
            wallet_manager=wallet_manager,
            rpc_client=rpc_client,
            llm=llm_client,
        ).run()
    finally:
        if llm_client is not None:
            llm_client.close()
        session_manager.save(session_context)


@app.command()
def run(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),  # noqa: B008
    session: str | None = typer.Option(None, "--session", help="Resume the given session ID"),  # noqa: B008
    new_session: bool = typer.Option(False, "--new-session", help="Start a fresh session"),  # noqa: B008
    config: Path | None = typer.Option(None, "--config", help="Use an alternate config file and skip project overrides"),  # noqa: B008
    llm_provider: str | None = typer.Option(None, "--llm-provider", help="Override the configured LLM provider"),  # noqa: B008
    llm_base_url: str | None = typer.Option(None, "--llm-base-url", help="Override the LLM base URL"),  # noqa: B008
    llm_model: str | None = typer.Option(None, "--llm-model", help="Override the LLM model"),  # noqa: B008
    llm_reasoning: str | None = typer.Option(None, "--llm-reasoning", help="Override the LLM reasoning effort (low|medium|high)"),  # noqa: B008
    llm_api_key: str | None = typer.Option(None, "--llm-api-key", help="Use this API key for the current run without persisting it"),  # noqa: B008
    offline_mode: bool = typer.Option(False, "--offline-mode", help="Force offline stubbed LLM responses", is_flag=True),  # noqa: B008
    dry_run_llm: bool = typer.Option(False, "--dry-run-llm", help="Send a single LLM request and exit"),  # noqa: B008
) -> None:
    """Launch the SolCoder interactive shell."""
    _launch_shell(
        verbose,
        session,
        new_session,
        config,
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_reasoning=llm_reasoning,
        llm_api_key=llm_api_key,
        offline_mode=offline_mode,
        dry_run_llm=dry_run_llm,
    )


@app.command()
def version() -> None:
    """Show CLI version."""
    try:
        pkg_version = metadata.version("solcoder")
    except metadata.PackageNotFoundError:
        pkg_version = "0.0.0"
    styled_echo(f"SolCoder CLI version {pkg_version}")


def _extract_dump_args(args: list[str]) -> tuple[str | None, str, Path | None, list[str]]:
    session_id: str | None = None
    dump_format = "json"
    dump_output: Path | None = None
    remaining: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--dump-session"):
            value: str | None = None
            if arg == "--dump-session":
                if i + 1 >= len(args):
                    styled_echo("❌ Option '--dump-session' requires a session id.")
                    raise typer.Exit(code=2)
                value = args[i + 1]
                i += 2
            else:
                value = arg.split("=", 1)[1]
                i += 1
            if not value:
                styled_echo("❌ Session id for '--dump-session' cannot be empty.")
                raise typer.Exit(code=2)
            session_id = value
            continue
        if arg.startswith("--dump-format"):
            if arg == "--dump-format":
                if i + 1 >= len(args):
                    styled_echo("❌ Option '--dump-format' requires a value (json or text).")
                    raise typer.Exit(code=2)
                dump_format = args[i + 1]
                i += 2
            else:
                dump_format = arg.split("=", 1)[1]
                i += 1
            continue
        if arg.startswith("--dump-output"):
            if arg == "--dump-output":
                if i + 1 >= len(args):
                    styled_echo("❌ Option '--dump-output' requires a file path.")
                    raise typer.Exit(code=2)
                dump_output = Path(args[i + 1]).expanduser()
                i += 2
            else:
                dump_output = Path(arg.split("=", 1)[1]).expanduser()
                i += 1
            continue
        remaining.append(arg)
        i += 1
    return session_id, dump_format, dump_output, remaining


def main() -> None:
    """Poetry entrypoint."""
    args = sys.argv[1:]
    dump_session, dump_format, dump_output, remaining = _extract_dump_args(args)
    if dump_session:
        _handle_dump_session(dump_session, dump_format, dump_output)
        return

    direct = _parse_direct_launch_args(remaining)
    if direct == "version":
        app(args=["version"])
        return
    if isinstance(direct, tuple):
        verbose, session, new_session, config_path = direct
        _launch_shell(verbose, session, new_session, config_path)
        return
    if remaining and remaining[0] == "--template":
        if len(remaining) < 2:
            styled_echo("❌ Option '--template' requires a template name.")
            raise typer.Exit(code=2)
        template_name = remaining[1]
        _render_template_cli(template_name, remaining[2:])
        return
    if remaining and remaining[0].startswith("-") and remaining[0] not in {"--help", "-h"}:
        app(args=["run", *remaining])
        return
    app(args=remaining or None)


__all__ = ["CLIApp", "app", "main"]
