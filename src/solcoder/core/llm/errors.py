"""LLM errors."""

from __future__ import annotations


class LLMError(RuntimeError):
    """Raised when the LLM client cannot complete a request."""


__all__ = ["LLMError"]
