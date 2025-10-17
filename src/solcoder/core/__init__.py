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
from .templates import RenderOptions, TemplateError, TemplateExistsError, TemplateNotFoundError, available_templates, render_template
from .tool_registry import ToolRegistry, ToolRegistryError, ToolResult, build_default_registry

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
    "render_template",
    "available_templates",
    "RenderOptions",
    "TemplateError",
    "TemplateExistsError",
    "TemplateNotFoundError",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolResult",
    "build_default_registry",
]
