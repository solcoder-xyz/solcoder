"""SolCoder CLI branding helpers and Solana-inspired styling."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from typing import Any

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

SOLCODER_THEME = Theme(
    {
        # Banner & Branding
        "solcoder.banner.primary": "bold #9945FF",
        "solcoder.banner.secondary": "bold #14F195",
        "solcoder.prompt": "bold #A855F7",

        # Chat Panels
        "solcoder.user.border": "#A855F7",
        "solcoder.user.text": "#E6FFFA",
        "solcoder.user.header": "bold #A855F7",
        "solcoder.agent.border": "#14F195",
        "solcoder.agent.text": "#E6FFFA",
        "solcoder.agent.header": "bold #14F195",

        # System Messages (Legacy - kept for compatibility)
        "solcoder.system.border": "#F472B6",
        "solcoder.system.text": "#FDE68A",
        "solcoder.system.header": "bold #F472B6",

        # Semantic States
        "solcoder.info.border": "#38BDF8",
        "solcoder.info.text": "#E6FFFA",
        "solcoder.info.header": "bold #38BDF8",
        "solcoder.info.bg": "on #0A2540",

        "solcoder.success.border": "#14F195",
        "solcoder.success.text": "#E6FFFA",
        "solcoder.success.header": "bold #14F195",
        "solcoder.success.bg": "on #052E16",

        "solcoder.warning.border": "#FBBF24",
        "solcoder.warning.text": "#FEF3C7",
        "solcoder.warning.header": "bold #FBBF24",
        "solcoder.warning.bg": "on #422006",

        "solcoder.error.border": "#FB7185",
        "solcoder.error.text": "#FEE2E2",
        "solcoder.error.header": "bold #FB7185",
        "solcoder.error.bg": "on #450A0A",

        # Typography Hierarchy
        "solcoder.text.primary": "#E6FFFA",
        "solcoder.text.secondary": "#94A3B8",
        "solcoder.text.tertiary": "#64748B",
        "solcoder.text.dim": "dim #64748B",

        # TODO & Planning
        "solcoder.todo.border": "#38BDF8",
        "solcoder.todo.pending": "#38BDF8",
        "solcoder.todo.done": "#14F195",
        "solcoder.todo.progress": "#FBBF24",
        "solcoder.plan.text": "#38BDF8",

        # Status & Logs
        "solcoder.status.spinner": "#14F195",
        "solcoder.status.text": "#94A3B8",
        "solcoder.log.info": "#38BDF8",
        "solcoder.log.warn": "#FBBF24",
        "solcoder.log.error": "#FB7185",
    }
)

BANNER_LINES: tuple[str, ...] = (
    "[#0E0E0E]",
    "[#0E0E0E]",
    "[#9945FF] @@@@@@    @@@@@@   @@@        @@@@@@@   @@@@@@   @@@@@@@   @@@@@@@@  @@@@@@@   ",
    "[#8264FF]@@@@@@@   @@@@@@@@  @@@       @@@@@@@@  @@@@@@@@  @@@@@@@@  @@@@@@@@  @@@@@@@@  ",
    "[#6E8CFF]!@@       @@!  @@@  @@!       !@@       @@!  @@@  @@!  @@@  @@!       @@!  @@@  ",
    "[#55B4F5]!@!       !@!  @!@  !@!       !@!       !@!  @!@  !@!  @!@  !@!       !@!  @!@  ",
    "[#3CDCE1]!!@@!!    @!@  !@!  @!!       !@!       @!@  !@!  @!@  !@!  @!!!:!    @!@!!@!   ",
    "[#28F0C8] !!@!!!   !@!  !!!  !!!       !!!       !@!  !!!  !@!  !!!  !!!!!:    !!@!@!    ",
    "[#19F5A5]     !:!  !!:  !!!  !!:       :!!       !!:  !!!  !!:  !!!  !!:       !!: :!!   ",
    "[#14F58C]    !:!   :!:  !:!   :!:      :!:       :!:  !:!  :!:  !:!  :!:       :!:  !:!  ",
    "[#14F195]:::: ::   ::::: ::   :: ::::   ::: :::  ::::: ::   :::: ::   :: ::::  ::   :::  ",
    "[#14F195]:: : :     : :  :   : :: : :   :: :: :   : :  :   :: :  :   : :: ::    :   : :  ",
    "[#0E0E0E]",
)


def themed_console(**kwargs: object) -> Console:
    """Return a Console configured with the SolCoder theme."""
    return Console(theme=SOLCODER_THEME, **kwargs)


def banner_lines() -> Iterable[Text]:
    """Yield Rich Text segments representing the SolCoder banner."""
    for line in BANNER_LINES:
        text = Text.from_markup(line)
        yield text


def render_banner(console: Console, *, animate: bool = True) -> None:
    """Render the SolCoder banner with optional animation."""
    if os.environ.get("SOLCODER_DISABLE_BANNER"):
        animate = False

    delay = 0.05 if animate and console.is_terminal else 0.0
    for line in banner_lines():
        console.print(line, overflow="ignore", crop=False)
        if delay:
            time.sleep(delay)
    console.print()


def create_chat_panel(
    role: str,
    message: str,
    *,
    use_markdown: bool = False,
) -> Panel:
    """Create a modern chat panel for user, agent, or system messages.

    Args:
        role: One of "user", "agent", or "system"
        message: The message content
        use_markdown: Whether to render message as Markdown (for agent responses)

    Returns:
        A Rich Panel configured with appropriate styling
    """
    if role == "user":
        header = "🟣 You"
        border_style = "solcoder.user.border"
        title_style = "solcoder.user.header"
        text_style = "solcoder.user.text"
    elif role == "agent":
        header = "🟢 SolCoder"
        border_style = "solcoder.agent.border"
        title_style = "solcoder.agent.header"
        text_style = "solcoder.agent.text"
    else:
        # System messages use semantic panel style
        header = f"🔔 {role.title()}"
        border_style = "solcoder.info.border"
        title_style = "solcoder.info.header"
        text_style = "solcoder.info.text"

    # Render content with consistent styling
    if use_markdown and role == "agent":
        # Use a Solana-themed code highlighter
        content: Any = Markdown(message, code_theme="monokai", inline_code_theme="purple")
    else:
        content = Text(message, style=text_style)

    return Panel(
        content,
        title=f"[{title_style}]{header}[/]",
        title_align="left",
        border_style=border_style,
        box=box.ROUNDED,  # Consistent rounded boxes
        padding=(1, 2),   # Consistent comfortable padding
        expand=False,
    )


def create_semantic_panel(
    message: str,
    *,
    panel_type: str = "info",
    title: str | None = None,
) -> Panel:
    """Create a semantic panel for info, success, warning, or error messages.

    Args:
        message: The message content
        panel_type: One of "info", "success", "warning", "error"
        title: Optional custom title (defaults based on type)

    Returns:
        A Rich Panel configured with appropriate semantic styling
    """
    # Define panel configurations
    configs = {
        "info": {
            "icon": "ℹ️",
            "default_title": "Info",
            "border_style": "solcoder.info.border",
            "title_style": "solcoder.info.header",
            "text_style": "solcoder.info.text",
        },
        "success": {
            "icon": "✓",
            "default_title": "Success",
            "border_style": "solcoder.success.border",
            "title_style": "solcoder.success.header",
            "text_style": "solcoder.success.text",
        },
        "warning": {
            "icon": "⚠️",
            "default_title": "Warning",
            "border_style": "solcoder.warning.border",
            "title_style": "solcoder.warning.header",
            "text_style": "solcoder.warning.text",
        },
        "error": {
            "icon": "✗",
            "default_title": "Error",
            "border_style": "solcoder.error.border",
            "title_style": "solcoder.error.header",
            "text_style": "solcoder.error.text",
        },
    }

    config = configs.get(panel_type, configs["info"])
    panel_title = title or config["default_title"]
    header = f"{config['icon']} {panel_title}"

    content = Text(message, style=config["text_style"])

    return Panel(
        content,
        title=f"[{config['title_style']}]{header}[/]",
        title_align="left",
        border_style=config["border_style"],
        box=box.ROUNDED,
        padding=(1, 2),
        expand=False,
    )


def create_todo_panel(tasks: list[dict[str, Any]]) -> Panel:
    """Create a modern Rich panel for displaying the TODO list.

    Args:
        tasks: List of task dictionaries with 'id', 'title', 'description', 'status'

    Returns:
        A Rich Panel with styled TODO items
    """
    from rich.progress import BarColumn, Progress, TextColumn
    from rich.table import Table

    if not tasks:
        empty_text = Text("✨ All clear! No pending tasks.", style="dim italic solcoder.text.secondary")
        return Panel(
            empty_text,
            title="[solcoder.todo.border]📋 TODO List[/]",
            border_style="solcoder.todo.border",
            box=box.ROUNDED,
            padding=(1, 2),
        )

    # Count pending and completed
    pending = sum(1 for t in tasks if t.get("status") != "done")
    completed = len(tasks) - pending
    total = len(tasks)
    progress_pct = (completed / total * 100) if total > 0 else 0

    # Create progress bar
    progress = Progress(
        TextColumn("[solcoder.text.secondary]{task.description}"),
        BarColumn(complete_style="solcoder.todo.done", finished_style="solcoder.todo.done", pulse_style="solcoder.todo.progress"),
        TextColumn("[solcoder.text.secondary]{task.percentage:>3.0f}%"),
        expand=False,
    )
    progress.add_task(f"{completed}/{total} complete", total=total, completed=completed)

    # Create a table for tasks
    table = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    table.add_column("Status", style="bold", width=3)
    table.add_column("ID", style="solcoder.text.tertiary", width=5)
    table.add_column("Task", style="solcoder.text.primary")

    for task in tasks:
        status = task.get("status", "todo")
        task_id = task.get("id", "")
        title = task.get("title", "")
        description = task.get("description")

        # Choose icon and color based on status
        if status == "done":
            icon = Text("✅", style="solcoder.todo.done")
            title_style = "dim solcoder.text.tertiary strike"
        else:
            icon = Text("⬜", style="solcoder.todo.pending")
            title_style = "solcoder.text.primary"

        # Format title with description if present
        task_text = Text(title, style=title_style)
        if description and status != "done":
            task_text.append("\n   ", style="dim")
            task_text.append(f"→ {description}", style="dim italic solcoder.text.secondary")

        table.add_row(icon, task_id, task_text)

    # Combine progress and table
    from rich.console import Group
    content = Group(progress, Text(""), table)  # Empty Text() adds spacing

    # Create subtitle with stats
    subtitle = f"[solcoder.text.secondary]{pending} pending"
    if completed > 0:
        subtitle += f" • {completed} completed"
    subtitle += f" • {progress_pct:.0f}% done[/]"

    return Panel(
        content,
        title="[bold solcoder.todo.border]📋 TODO List[/]",
        subtitle=subtitle,
        subtitle_align="right",
        border_style="solcoder.todo.border",
        box=box.ROUNDED,
        padding=(1, 2),
    )


__all__ = [
    "render_banner",
    "themed_console",
    "create_chat_panel",
    "create_semantic_panel",
    "create_todo_panel",
    "SOLCODER_THEME",
    "BANNER_LINES",
]
