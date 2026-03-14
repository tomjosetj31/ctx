"""Terminal adapter for ctx."""

from spaceload.adapters.terminal.base import TerminalAdapter, TerminalSession
from spaceload.adapters.terminal.registry import TerminalAdapterRegistry

__all__ = ["TerminalAdapter", "TerminalSession", "TerminalAdapterRegistry"]
