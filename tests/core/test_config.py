
from pathlib import Path
from typing import Any

import pytest
import tomli_w
import tomllib

from solcoder.core.config import (
    CONFIG_FILENAME,
    CREDENTIALS_FILENAME,
    ConfigContext,
    ConfigManager,
    ConfigurationError,
)


def make_manager(tmp_path: Path, **kwargs: Any) -> ConfigManager:
    return ConfigManager(config_dir=tmp_path, **kwargs)


def test_bootstrap_creates_config_and_credentials(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    context = manager.ensure(
        interactive=False,
        llm_base_url="https://api.example.com/v1",
        llm_model="demo-model",
        llm_api_key="secret-key",
        passphrase="passphrase",
    )

    assert isinstance(context, ConfigContext)
    assert context.config.llm_base_url == "https://api.example.com/v1"
    assert context.llm_api_key == "secret-key"
    assert context.config.llm_reasoning_effort == "medium"
    assert context.config.history_max_messages == 20
    assert context.config.history_summary_keep == 10
    assert context.config.history_summary_max_words == 200
    assert context.config.history_auto_compact_threshold == 0.95
    assert context.config.llm_input_token_limit == 272_000
    assert context.config.llm_output_token_limit == 128_000
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "credentials.json").exists()
    assert context.passphrase == "passphrase"


def test_subsequent_load_requires_passphrase(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.ensure(
        interactive=False,
        llm_api_key="secret",
        passphrase="passphrase",
    )

    manager2 = make_manager(tmp_path)
    with pytest.raises(ConfigurationError):
        manager2.ensure(interactive=False)

    context = manager2.ensure(interactive=False, passphrase="passphrase")
    assert context.llm_api_key == "secret"
    assert context.passphrase == "passphrase"


def test_llm_api_key_override_skips_passphrase_prompt(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.ensure(
        interactive=False,
        llm_api_key="persisted",
        passphrase="stored-pass",
    )

    manager2 = make_manager(tmp_path)
    context = manager2.ensure(interactive=False, llm_api_key="override")

    assert context.llm_api_key == "override"
    assert context.passphrase is None


def test_env_overrides_used_when_interactive_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOLCODER_LLM_BASE_URL", "https://api.fake/v1")
    monkeypatch.setenv("SOLCODER_LLM_MODEL", "fake-model")
    monkeypatch.setenv("SOLCODER_LLM_API_KEY", "env-secret")
    monkeypatch.setenv("SOLCODER_LLM_PASSPHRASE", "env-pass")
    monkeypatch.setenv("SOLCODER_LLM_REASONING", "high")

    manager = make_manager(tmp_path)
    context = manager.ensure(interactive=False)

    assert context.config.llm_base_url == "https://api.fake/v1"
    assert context.llm_api_key == "env-secret"
    assert context.passphrase == "env-pass"
    assert context.config.llm_reasoning_effort == "high"
    # ensure we can reload with env-provided passphrase
    manager2 = make_manager(tmp_path)
    context2 = manager2.ensure(interactive=False)
    assert context2.llm_api_key == "env-secret"
    assert context2.passphrase == "env-pass"
    assert context2.config.llm_reasoning_effort == "high"


def test_offline_mode_bootstrap_skips_credentials(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    context = manager.ensure(
        interactive=True,
        llm_model="offline-model",
        offline_mode=True,
    )

    assert context.llm_api_key == ""
    assert context.passphrase is None
    assert context.config.llm_model == "offline-model"
    assert (tmp_path / CONFIG_FILENAME).exists()
    assert not (tmp_path / CREDENTIALS_FILENAME).exists()


def test_update_llm_preferences_persists_additional_fields(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    context = manager.ensure(interactive=False, llm_api_key="secret", passphrase="pass")

    manager.update_llm_preferences(
        llm_model="gpt-5",
        llm_reasoning_effort="high",
        history_max_messages=30,
        history_summary_keep=6,
        history_summary_max_words=300,
        history_auto_compact_threshold=0.9,
        llm_input_token_limit=300_000,
        llm_output_token_limit=150_000,
    )

    reloaded = manager.ensure(interactive=False, passphrase="pass")
    assert reloaded.config.llm_model == "gpt-5"
    assert reloaded.config.llm_reasoning_effort == "high"
    assert reloaded.config.history_max_messages == 30
    assert reloaded.config.history_summary_keep == 6
    assert reloaded.config.history_summary_max_words == 300
    assert reloaded.config.history_auto_compact_threshold == 0.9
    assert reloaded.config.llm_input_token_limit == 300_000
    assert reloaded.config.llm_output_token_limit == 150_000


def test_ensure_updates_existing_config(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.ensure(
        interactive=False,
        llm_api_key="secret",
        passphrase="passphrase",
    )

    manager.ensure(
        interactive=False,
        llm_model="gpt-5",
        llm_reasoning="high",
        llm_base_url="https://api.example.com/v2",
        passphrase="passphrase",
    )

    reloaded = manager.ensure(interactive=False, passphrase="passphrase")
    assert reloaded.config.llm_model == "gpt-5"
    assert reloaded.config.llm_reasoning_effort == "high"
    assert reloaded.config.llm_base_url == "https://api.example.com/v2"


def test_project_config_overrides_global(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.ensure(interactive=False, llm_api_key="secret", passphrase="pass")

    global_config_path = tmp_path / CONFIG_FILENAME
    global_data = tomllib.loads(global_config_path.read_text())
    global_data["tool_controls"] = {"format": "allow"}
    global_config_path.write_text(tomli_w.dumps(global_data))

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config_path = project_dir / CONFIG_FILENAME
    project_config_path.write_text(
        tomli_w.dumps({
            "network": "mainnet",
            "auto_airdrop": False,
            "tool_controls": {"deploy": "deny"},
        })
    )

    manager_with_project = make_manager(
        tmp_path, project_config_path=project_config_path
    )
    context = manager_with_project.ensure(interactive=False, passphrase="pass")

    assert context.config.network == "mainnet"
    assert context.config.auto_airdrop is False
    assert context.config.tool_controls == {"format": "allow", "deploy": "deny"}


def test_override_config_path_wins(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.ensure(interactive=False, llm_api_key="secret", passphrase="pass")

    project_config = tmp_path / "project" / CONFIG_FILENAME
    project_config.parent.mkdir()
    project_config.write_text(tomli_w.dumps({"llm_model": "project-model"}))

    override_path = tmp_path / "custom.toml"
    override_path.write_text(tomli_w.dumps({"llm_model": "override-model"}))

    manager_override = make_manager(
        tmp_path,
        project_config_path=project_config,
        override_config_path=override_path,
    )
    context = manager_override.ensure(interactive=False, passphrase="pass")

    assert context.config.llm_model == "override-model"


def test_invalid_project_config_raises(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.ensure(interactive=False, llm_api_key="secret", passphrase="pass")
    bad_config = tmp_path / "project" / CONFIG_FILENAME
    bad_config.parent.mkdir()
    bad_config.write_text("invalid = [this is not toml")

    manager_with_bad = make_manager(tmp_path, project_config_path=bad_config)

    with pytest.raises(ConfigurationError):
        manager_with_bad.ensure(interactive=False, passphrase="pass")
