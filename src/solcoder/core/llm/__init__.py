"""LLM client package.

This namespace hosts the high-level `LLMClient` along with supporting
types (`types.py`), transport helpers (`transport.py`), and offline
fallback responses (`offline.py`). Importing from this module keeps the
public surface stable while allowing the implementation to remain
modular for testing and future provider integrations.
"""

from .client import LLMClient
from .errors import LLMError
from .types import LLMResponse, LLMSettings

__all__ = ["LLMClient", "LLMError", "LLMResponse", "LLMSettings"]
