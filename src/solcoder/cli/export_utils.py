"""Formatting helpers for CLI export commands."""

from __future__ import annotations

from typing import Any


def format_export_text(export_data: dict[str, Any]) -> str:
    """Render session export metadata and transcript as plain text."""
    metadata = export_data.get("metadata", {})
    transcript = export_data.get("transcript", [])
    lines = ["Session Export", "=============="]
    if isinstance(metadata, dict):
        for key in (
            "session_id",
            "created_at",
            "updated_at",
            "active_project",
            "wallet_status",
            "wallet_balance",
            "spend_amount",
        ):
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
                timestamp = entry.get("timestamp")
                prefix = f"{timestamp} " if timestamp else ""
                lines.append(f"{prefix}[{role}] {message}")
                tool_calls = entry.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tool_call in tool_calls:
                        if not isinstance(tool_call, dict):
                            continue
                        call_type = tool_call.get("type", "tool")
                        name = tool_call.get("name") or ""
                        status = tool_call.get("status") or ""
                        summary = tool_call.get("summary") or ""
                        details = " • ".join(part for part in (name, status, summary) if part)
                        lines.append(f"    ↳ {call_type}: {details}")
            else:
                lines.append(str(entry))
    else:
        lines.append("(no transcript available)")
    return "\n".join(lines)


__all__ = ["format_export_text"]
