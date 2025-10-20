"""Toolkit descriptors for SolCoder tools."""

from .code import code_toolkit
from .command import command_toolkit
from .deploy import deploy_toolkit
from .diagnostics import diagnostics_toolkit
from .knowledge import knowledge_toolkit
from .plan import plan_toolkit
from .review import review_toolkit
from .session import session_toolkit
from .wallet import wallet_toolkit

DEFAULT_TOOLKIT_FACTORIES = [
    plan_toolkit,
    code_toolkit,
    review_toolkit,
    deploy_toolkit,
    diagnostics_toolkit,
    knowledge_toolkit,
    session_toolkit,
    command_toolkit,
    wallet_toolkit,
]

__all__ = ["DEFAULT_TOOLKIT_FACTORIES"]
