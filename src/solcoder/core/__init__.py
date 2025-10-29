"""Core services for SolCoder."""

from .config import (
    DEFAULT_CONFIG_DIR,
    ConfigContext,
    ConfigManager,
    ConfigurationError,
    SolCoderConfig,
)
from .agent import (
    AgentDirective,
    AgentMessageError,
    AgentToolResult,
    build_tool_manifest,
    manifest_to_prompt_section,
    parse_agent_directive,
)
from .env_diag import DiagnosticResult, ToolRequirement, collect_environment_diagnostics
from .exec_ua import build_exec_ua_header, clear_exec_ua_cache
from .knowledge_base import KnowledgeBaseAnswer, KnowledgeBaseClient, KnowledgeBaseError
from .templates import RenderOptions, TemplateError, TemplateExistsError, TemplateNotFoundError, available_templates, render_template
from .tool_registry import (
    ToolRegistry,
    ToolRegistryError,
    ToolResult,
    Toolkit,
    ToolkitAlreadyRegisteredError,
    build_default_registry,
)
from .context import (
    ContextManager,
    HistoryCompactionStrategy,
    RollingHistoryStrategy,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_SUMMARY_KEEP,
    DEFAULT_SUMMARY_MAX_WORDS,
    DEFAULT_AUTO_COMPACT_THRESHOLD,
    DEFAULT_LLM_INPUT_LIMIT,
    DEFAULT_COMPACTION_COOLDOWN,
)
from .todo import TodoItem, TodoManager
from .wallet_state import fetch_balance, update_wallet_metadata

__all__ = [
    "AgentDirective",
    "AgentMessageError",
    "AgentToolResult",
    "build_tool_manifest",
    "manifest_to_prompt_section",
    "parse_agent_directive",
    "ConfigManager",
    "ConfigContext",
    "SolCoderConfig",
    "ConfigurationError",
    "DEFAULT_CONFIG_DIR",
    "collect_environment_diagnostics",
    "DiagnosticResult",
    "ToolRequirement",
    "KnowledgeBaseClient",
    "KnowledgeBaseAnswer",
    "KnowledgeBaseError",
    "build_exec_ua_header",
    "clear_exec_ua_cache",
    "render_template",
    "available_templates",
    "RenderOptions",
    "TemplateError",
    "TemplateExistsError",
    "TemplateNotFoundError",
    "ContextManager",
    "HistoryCompactionStrategy",
    "RollingHistoryStrategy",
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_SUMMARY_KEEP",
    "DEFAULT_SUMMARY_MAX_WORDS",
    "DEFAULT_AUTO_COMPACT_THRESHOLD",
    "DEFAULT_LLM_INPUT_LIMIT",
    "DEFAULT_COMPACTION_COOLDOWN",
    "TodoManager",
    "TodoItem",
    "update_wallet_metadata",
    "fetch_balance",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolResult",
    "Toolkit",
    "ToolkitAlreadyRegisteredError",
    "build_default_registry",
]
