"""SolCoder CLI branding helpers and Solana-inspired styling."""

from __future__ import annotations

import os
import time
from typing import Iterable

from rich.console import Console
from rich.text import Text
from rich.theme import Theme

SOLCODER_THEME = Theme(
    {
        "solcoder.banner.primary": "bold #9945FF",
        "solcoder.banner.secondary": "bold #14F195",
        "solcoder.prompt": "bold #A855F7",
        "solcoder.user.border": "#7C3AED",
        "solcoder.user.text": "#D8B4FE",
        "solcoder.agent.border": "#14F195",
        "solcoder.agent.text": "#E6FFFA",
        "solcoder.system.border": "#F472B6",
        "solcoder.system.text": "#FDE68A",
        "solcoder.plan.text": "#38BDF8",
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


__all__ = ["render_banner", "themed_console", "SOLCODER_THEME", "BANNER_LINES"]
