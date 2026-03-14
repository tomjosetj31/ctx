"""Terminal adapter for ctx."""

from ctx.adapters.terminal.base import TerminalAdapter, TerminalSession
from ctx.adapters.terminal.registry import TerminalAdapterRegistry

__all__ = ["TerminalAdapter", "TerminalSession", "TerminalAdapterRegistry"]
