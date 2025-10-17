"""Module descriptors for SolCoder tools."""

from .plan import plan_module
from .code import code_module
from .review import review_module
from .deploy import deploy_module
from .diagnostics import diagnostics_module
from .knowledge import knowledge_module
from .command import command_module

DEFAULT_MODULE_FACTORIES = [
    plan_module,
    code_module,
    review_module,
    deploy_module,
    diagnostics_module,
    knowledge_module,
    command_module,
]

__all__ = ["DEFAULT_MODULE_FACTORIES"]
