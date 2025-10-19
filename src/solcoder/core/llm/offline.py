"""Offline LLM helpers."""

from __future__ import annotations

import json


def offline_response(prompt: str, system_prompt: str | None) -> str:
    """Return a deterministic stub response for offline mode."""

    prompt = prompt.strip()
    if not prompt:
        return json.dumps({
            "type": "reply",
            "message": "[offline stub] No prompt provided."
        })

    lowered = prompt.lower()
    if lowered.startswith("{") or lowered.startswith("["):
        try:
            data = json.loads(prompt)
        except json.JSONDecodeError:
            data = None
        else:
            if isinstance(data, dict) and data.get("type") == "tool_result":
                return json.dumps({
                    "type": "plan",
                    "message": "Offline stub plan.",
                    "steps": [
                        "Review the latest tool result.",
                        "Summarize findings for the user."
                    ],
                })

    words = prompt.split()
    if len(words) >= 4:
        steps = [
            f"Break down the request: {prompt[:60]}…",
            "Provide a helpful summary."
        ]
        return json.dumps({
            "type": "plan",
            "message": "Offline stub plan.",
            "steps": steps,
        })

    return json.dumps({
        "type": "reply",
        "message": f"[offline stub] {prompt}",
    })


__all__ = ["offline_response"]
