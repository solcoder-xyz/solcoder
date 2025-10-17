import json
from pathlib import Path

import pytest

from solcoder.core.templates import RenderOptions, TemplateExistsError, available_templates, render_template


def test_available_templates_includes_counter() -> None:
    assert "counter" in available_templates()


def test_render_template_writes_placeholder_values(tmp_path: Path) -> None:
    destination = tmp_path / "demo"
    options = RenderOptions(
        template="counter",
        destination=destination,
        program_name="demo_counter",
        author_pubkey="Auth1111111111111111111111111111111111",
        program_id="Demo1111111111111111111111111111111111",
        cluster="devnet",
    )

    render_template(options)

    anchor_toml = (destination / "Anchor.toml").read_text()
    assert "demo_counter" in anchor_toml
    assert "Demo1111111111111111111111111111111111" in anchor_toml

    lib_rs = (destination / "programs" / "demo_counter" / "src" / "lib.rs").read_text()
    assert "demo_counter" in lib_rs

    test_ts = (destination / "tests" / "demo_counter.ts")
    assert test_ts.exists()


def test_render_template_requires_empty_destination(tmp_path: Path) -> None:
    destination = tmp_path / "demo"
    destination.mkdir()
    (destination / "dummy.txt").write_text("hello")

    options = RenderOptions(template="counter", destination=destination)

    with pytest.raises(TemplateExistsError):
        render_template(options)
