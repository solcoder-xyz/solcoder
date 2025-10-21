from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BLUEPRINTS_ROOT = Path(__file__).resolve().parents[1] / "anchor" / "blueprints"
REGISTRY_PATH = BLUEPRINTS_ROOT / "registry.json"


@dataclass
class BlueprintEntry:
    key: str
    name: str
    description: str
    template_path: str
    tags: list[str]
    required_tools: list[str]


def load_registry() -> list[BlueprintEntry]:
    if not REGISTRY_PATH.exists():
        return []
    data = json.loads(REGISTRY_PATH.read_text())
    out: list[BlueprintEntry] = []
    for item in data.get("blueprints", []):
        out.append(
            BlueprintEntry(
                key=item.get("key", ""),
                name=item.get("name", ""),
                description=item.get("description", ""),
                template_path=item.get("template_path", ""),
                tags=item.get("tags") or [],
                required_tools=item.get("required_tools") or [],
            )
        )
    return out


def load_wizard_schema(key: str) -> list[dict[str, Any]]:
    schema_path = BLUEPRINTS_ROOT / key / "wizard.json"
    if not schema_path.exists():
        return []
    data = json.loads(schema_path.read_text())
    return list(data.get("questions") or [])


def prompt_wizard(app, questions: list[dict[str, Any]], defaults: dict[str, str]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for q in questions:
        key = q.get("key")
        prompt = q.get("prompt") or key
        default = q.get("default")
        pattern = q.get("pattern")
        if key is None or prompt is None:
            continue
        if key in defaults:
            default = defaults[key]
        val = app._prompt_text(f"{prompt}") if default is None else app._prompt_text(f"{prompt} [{default}]")
        val = (val or "").strip() or (str(default) if default is not None else "")
        if pattern and not re.match(pattern, val):
            app.console.print(f"[yellow]Value for {key} does not match expected pattern; using default.[/yellow]")
            val = str(default) if default is not None else val
        answers[key] = val
    return answers


def persist_answers_readme(root: Path, answers: dict[str, Any]) -> None:
    readme = root / "README.md"
    if not readme.exists():
        return
    existing = readme.read_text()
    lines = [existing.rstrip(), "\n", "### Wizard Answers", "\n"]
    for k, v in answers.items():
        lines.append(f"- {k}: {v}")
    readme.write_text("\n".join(lines) + "\n")


def normalise_program_name(name: str) -> str:
    base = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip())
    base = base.lower().strip("_")
    return base or "counter"
