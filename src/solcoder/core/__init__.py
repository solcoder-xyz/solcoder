"""Core services for SolCoder."""

from .config import (
    DEFAULT_CONFIG_DIR,
    ConfigContext,
    ConfigManager,
    ConfigurationError,
    SolCoderConfig,
)
from .env_diag import DiagnosticResult, ToolRequirement, collect_environment_diagnostics
from .templates import RenderOptions, TemplateError, TemplateExistsError, TemplateNotFoundError, available_templates, render_template

__all__ = [
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
]
