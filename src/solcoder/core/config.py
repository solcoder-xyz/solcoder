
"""Configuration and credential management for SolCoder."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from pathlib import Path

import tomli_w
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, ValidationError

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import typer

DEFAULT_CONFIG_DIR = Path(os.environ.get("SOLCODER_HOME", Path.home() / ".solcoder"))
CONFIG_FILENAME = "config.toml"
CREDENTIALS_FILENAME = "credentials.json"
PBKDF_ITERATIONS = 390_000


class ConfigurationError(RuntimeError):
    """Raised when configuration or credential loading fails."""


class SolCoderConfig(BaseModel):
    """Persisted SolCoder configuration settings."""

    config_version: int = 1
    network: str = "devnet"
    rpc_url: str = "https://api.devnet.solana.com"
    max_session_spend: float = 0.2
    auto_airdrop: bool = True
    auto_airdrop_threshold: float = 0.5
    auto_airdrop_cooldown_secs: int = 30
    # New names for auto-airdrop policy (preferred going forward)
    auto_airdrop_min_balance: float = 0.5
    auto_airdrop_amount: float = 1.0
    airdrop_cooldown_secs: int = 30
    telemetry: bool = False
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-5-codex"
    tool_controls: dict[str, str] | None = None
    llm_reasoning_effort: str = "medium"
    history_max_messages: int = 20
    history_summary_keep: int = 10
    history_summary_max_words: int = 200
    history_auto_compact_threshold: float = 0.95
    llm_input_token_limit: int = 272_000
    llm_output_token_limit: int = 128_000
    history_compaction_cooldown: int = 10


@dataclass
class ConfigContext:
    """Represents an initialized configuration and decrypted secrets."""

    config: SolCoderConfig
    llm_api_key: str
    passphrase: str | None


class CredentialStore:
    """Encrypts/decrypts API keys using a passphrase-derived key."""

    def __init__(self, credentials_path: Path) -> None:
        self.credentials_path = credentials_path

    def save(self, passphrase: str, api_key: str) -> None:
        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        token = Fernet(key).encrypt(api_key.encode("utf-8"))
        payload = {
            "salt": base64.b64encode(salt).decode("ascii"),
            "ciphertext": base64.b64encode(token).decode("ascii"),
            "iterations": PBKDF_ITERATIONS,
        }
        self.credentials_path.write_text(json.dumps(payload, indent=2))

    def load(self, passphrase: str) -> str:
        data = json.loads(self.credentials_path.read_text())
        salt = base64.b64decode(data["salt"])
        ciphertext = base64.b64decode(data["ciphertext"])
        key = self._derive_key(passphrase, salt)
        try:
            decrypted = Fernet(key).decrypt(ciphertext)
        except InvalidToken as exc:  # pragma: no cover - exercised in tests
            raise ConfigurationError("Invalid passphrase for SolCoder credentials") from exc
        return decrypted.decode("utf-8")

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


class ConfigManager:
    """Handles loading, prompting, and persisting SolCoder configuration."""

    def __init__(
        self,
        config_dir: Path | None = None,
        prompt_fn: Callable[..., str] | None = None,
        echo_fn: Callable[[str], None] | None = None,
        project_config_path: Path | None = None,
        override_config_path: Path | None = None,
    ) -> None:
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / CONFIG_FILENAME
        self.credentials_path = self.config_dir / CREDENTIALS_FILENAME
        self._credential_store = CredentialStore(self.credentials_path)
        self._prompt = prompt_fn or self._default_prompt
        self._echo = echo_fn or typer.echo
        self.project_config_path = project_config_path
        self.override_config_path = override_config_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ensure(
        self,
        *,
        interactive: bool = True,
        llm_base_url: str | None = None,
        llm_model: str | None = None,
        llm_reasoning: str | None = None,
        llm_api_key: str | None = None,
        passphrase: str | None = None,
        offline_mode: bool = False,
    ) -> ConfigContext:
        """Ensure configuration and credentials exist; return decrypted context."""

        if offline_mode:
            if self.config_path.exists():
                config = self._load_config()
            else:
                config = SolCoderConfig()
                self._save_config(config)

            updates: dict[str, str] = {}
            if llm_base_url and config.llm_base_url != llm_base_url:
                updates["llm_base_url"] = llm_base_url
            if llm_model and config.llm_model != llm_model:
                updates["llm_model"] = llm_model
            if llm_reasoning and config.llm_reasoning_effort != llm_reasoning:
                updates["llm_reasoning_effort"] = llm_reasoning
            if updates:
                self.update_llm_preferences(**updates)
                config = self._load_config()

            return ConfigContext(
                config=config,
                llm_api_key=llm_api_key or "",
                passphrase=passphrase,
            )

        if self.config_path.exists() and self.credentials_path.exists():
            config = self._load_config()
            updates: dict[str, str] = {}
            if llm_base_url and config.llm_base_url != llm_base_url:
                config.llm_base_url = llm_base_url
                updates["llm_base_url"] = llm_base_url
            if llm_model and config.llm_model != llm_model:
                config.llm_model = llm_model
                updates["llm_model"] = llm_model
            if llm_reasoning and config.llm_reasoning_effort != llm_reasoning:
                config.llm_reasoning_effort = llm_reasoning
                updates["llm_reasoning_effort"] = llm_reasoning
            if updates:
                self.update_llm_preferences(**updates)

            if llm_api_key is not None:
                return ConfigContext(
                    config=config,
                    llm_api_key=llm_api_key,
                    passphrase=passphrase,
                )

            api_key, used_passphrase = self._load_api_key(
                config,
                passphrase=passphrase,
                interactive=interactive,
            )
            return ConfigContext(config=config, llm_api_key=api_key, passphrase=used_passphrase)

        return self._bootstrap_config(
            interactive=interactive,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_reasoning=llm_reasoning,
            llm_api_key=llm_api_key,
            passphrase=passphrase,
        )

    # ------------------------------------------------------------------
    # Bootstrap flow
    # ------------------------------------------------------------------
    def _bootstrap_config(
        self,
        *,
        interactive: bool,
        llm_base_url: str | None,
        llm_model: str | None,
        llm_reasoning: str | None,
        llm_api_key: str | None,
        passphrase: str | None,
    ) -> ConfigContext:
        self._echo("\n🔧 First-time SolCoder setup")

        base_url = llm_base_url or os.environ.get("SOLCODER_LLM_BASE_URL") or "https://api.openai.com/v1"
        if interactive:
            base_url = self._prompt("LLM base URL", default=base_url)

        model = llm_model or os.environ.get("SOLCODER_LLM_MODEL") or "gpt-5-codex"
        if interactive:
            model = self._prompt("LLM model", default=model)

        reasoning = llm_reasoning or os.environ.get("SOLCODER_LLM_REASONING") or "medium"
        if interactive:
            reasoning = self._prompt("LLM reasoning effort", default=reasoning)

        api_key = llm_api_key or os.environ.get("SOLCODER_LLM_API_KEY")
        if not api_key:
            if not interactive:
                raise ConfigurationError("LLM API key required for non-interactive configuration")
            api_key = self._prompt("Enter LLM API key", hide_input=True)

        passphrase_value = passphrase or os.environ.get("SOLCODER_LLM_PASSPHRASE")
        if not passphrase_value:
            if not interactive:
                raise ConfigurationError("Passphrase required for non-interactive configuration")
            passphrase_value = self._prompt(
                "Create a passphrase to secure your SolCoder credentials",
                hide_input=True,
                confirmation_prompt=True,
            )

        base_config_data = {
            "llm_base_url": base_url,
            "llm_model": model,
            "llm_reasoning_effort": reasoning,
        }
        self.update_llm_preferences(**base_config_data)
        merged_config = self._load_config()
        self._credential_store.save(passphrase_value, api_key)
        self._echo("✅ SolCoder configuration saved to " + str(self.config_path))
        return ConfigContext(config=merged_config, llm_api_key=api_key, passphrase=passphrase_value)


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_config(self) -> SolCoderConfig:
        data: dict[str, Any] = self._read_config_dict(self.config_path)
        if self.project_config_path:
            data = self._merge_dicts(data, self._read_config_dict(self.project_config_path))
        if self.override_config_path:
            data = self._merge_dicts(data, self._read_config_dict(self.override_config_path))
        try:
            return SolCoderConfig(**data)
        except ValidationError as exc:
            raise ConfigurationError(str(exc)) from exc

    def _save_config(self, config: SolCoderConfig) -> None:
        self.config_path.write_text(tomli_w.dumps(config.model_dump(exclude_none=True)))

    def _update_base_config(self, **updates: object) -> None:
        current = self._read_config_dict(self.config_path)
        current = current.copy() if current else {}
        current.update(updates)
        base_config = SolCoderConfig(**current)
        self._save_config(base_config)

    def update_llm_preferences(
        self,
        *,
        llm_base_url: str | None = None,
        llm_model: str | None = None,
        llm_reasoning_effort: str | None = None,
        history_max_messages: int | None = None,
        history_summary_keep: int | None = None,
        history_summary_max_words: int | None = None,
        history_auto_compact_threshold: float | None = None,
        llm_input_token_limit: int | None = None,
        llm_output_token_limit: int | None = None,
        history_compaction_cooldown: int | None = None,
    ) -> None:
        updates: dict[str, str] = {}
        if llm_base_url is not None:
            updates["llm_base_url"] = llm_base_url
        if llm_model is not None:
            updates["llm_model"] = llm_model
        if llm_reasoning_effort is not None:
            updates["llm_reasoning_effort"] = llm_reasoning_effort
        if history_max_messages is not None:
            updates["history_max_messages"] = history_max_messages
        if history_summary_keep is not None:
            updates["history_summary_keep"] = history_summary_keep
        if history_summary_max_words is not None:
            updates["history_summary_max_words"] = history_summary_max_words
        if history_auto_compact_threshold is not None:
            updates["history_auto_compact_threshold"] = history_auto_compact_threshold
        if llm_input_token_limit is not None:
            updates["llm_input_token_limit"] = llm_input_token_limit
        if llm_output_token_limit is not None:
            updates["llm_output_token_limit"] = llm_output_token_limit
        if history_compaction_cooldown is not None:
            updates["history_compaction_cooldown"] = history_compaction_cooldown
        if updates:
            self._update_base_config(**updates)

    def update_wallet_policy(
        self,
        *,
        max_session_spend: float | None = None,
        auto_airdrop: bool | None = None,
        auto_airdrop_threshold: float | None = None,
        auto_airdrop_cooldown_secs: int | None = None,
    ) -> None:
        updates: dict[str, object] = {}
        if max_session_spend is not None:
            updates["max_session_spend"] = float(max_session_spend)
        if auto_airdrop is not None:
            updates["auto_airdrop"] = bool(auto_airdrop)
        if auto_airdrop_threshold is not None:
            updates["auto_airdrop_threshold"] = float(auto_airdrop_threshold)
        if auto_airdrop_cooldown_secs is not None:
            updates["auto_airdrop_cooldown_secs"] = int(auto_airdrop_cooldown_secs)
        if updates:
            self._update_base_config(**updates)

    def _read_config_dict(self, path: Path | None) -> dict[str, Any]:
        if path is None:
            return {}
        if not path.exists():
            return {}
        try:
            return tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(f"Failed to load config from {path}: {exc}") from exc

    def _merge_dicts(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    def _load_api_key(
        self,
        config: SolCoderConfig,
        *,
        passphrase: str | None,
        interactive: bool,
    ) -> tuple[str, str]:
        attempts = 3
        while True:
            pwd = passphrase or os.environ.get("SOLCODER_LLM_PASSPHRASE")
            if not pwd:
                if not interactive:
                    raise ConfigurationError("Passphrase required to decrypt SolCoder credentials")
                pwd = self._prompt("Enter SolCoder passphrase", hide_input=True)
            try:
                key = self._credential_store.load(pwd)
                return key, pwd
            except ConfigurationError as exc:
                if not interactive:
                    raise
                attempts -= 1
                if attempts <= 0:
                    raise exc
                self._echo("❌ Invalid passphrase. Please try again.")
                passphrase = None

    @staticmethod
    def _default_prompt(
        message: str,
        *,
        hide_input: bool = False,
        confirmation_prompt: bool = False,
        default: str | None = None,
    ) -> str:
        if default is not None:
            return typer.prompt(message, default=default, hide_input=hide_input, confirmation_prompt=confirmation_prompt)
        return typer.prompt(message, hide_input=hide_input, confirmation_prompt=confirmation_prompt)


__all__ = ["ConfigManager", "ConfigContext", "SolCoderConfig", "ConfigurationError"]
