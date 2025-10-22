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

def resolve_registry_template_path(path_str: str) -> Path | None:
    """Resolve a registry template path relative to the installed package.

    The registry stores relative paths like "src/solcoder/anchor/blueprints/token/template". When SolCoder
    is launched from an arbitrary CWD, resolving relative to CWD breaks. This helper
    resolves against package roots so pip-installed users work reliably.
    """
    p = Path(path_str)
    if p.is_absolute():
        return p if p.exists() else None
    # Candidate bases: package root (…/solcoder), its parent (…/src), and repo root (parent of src)
    candidates: list[Path] = []
    try:
        pkg_root = BLUEPRINTS_ROOT.parent.parent  # …/solcoder
        candidates.append(pkg_root)
        candidates.append(pkg_root.parent)        # …/src
        candidates.append(pkg_root.parent.parent) # repo root
    except Exception:
        pass
    for base in candidates:
        try:
            candidate = (base / p).resolve()
        except Exception:
            continue
        if candidate.exists():
            return candidate
    return None


def _should_ask_question(
    question: dict[str, Any],
    answers: dict[str, Any],
    defaults: dict[str, Any],
) -> bool:
    condition = question.get("when")
    if not condition:
        return True
    key = condition.get("key")
    if not key:
        return True
    expected = condition.get("equals")
    value = answers.get(key, defaults.get(key))
    if expected is None:
        return value is not None
    if isinstance(expected, list):
        normalized_expected = {str(item).lower() for item in expected}
    else:
        normalized_expected = {str(expected).lower()}
    if value is None:
        return False
    return str(value).lower() in normalized_expected


def prompt_wizard(app, questions: list[dict[str, Any]], defaults: dict[str, Any]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for q in questions:
        key = q.get("key")
        prompt = q.get("prompt") or key
        default = q.get("default")
        pattern = q.get("pattern")
        if key is None or prompt is None:
            continue
        if not _should_ask_question(q, answers, defaults):
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
