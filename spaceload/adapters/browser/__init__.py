"""Browser adapter package for ctx."""

from spaceload.adapters.browser.base import BrowserAdapter, TabSet
from spaceload.adapters.browser.registry import BrowserAdapterRegistry

__all__ = ["BrowserAdapter", "TabSet", "BrowserAdapterRegistry"]
