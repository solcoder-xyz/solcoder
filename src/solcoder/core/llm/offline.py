"""Offline LLM helpers."""

from __future__ import annotations


def offline_response(prompt: str, system_prompt: str | None) -> str:
    """Return a deterministic stub response for offline mode."""

    pieces = ["[offline stub]"]
    if system_prompt:
        pieces.append(f"(system: {system_prompt.strip()[:120]})")
    trimmed_prompt = prompt.strip()
    if len(trimmed_prompt) > 160:
        trimmed_prompt = f"{trimmed_prompt[:157]}…"
    pieces.append(trimmed_prompt or "<empty prompt>")
    return " ".join(pieces)


__all__ = ["offline_response"]
