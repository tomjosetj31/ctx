"""Workspace replayer — executes recorded action sequences.

Phase 1: stub implementation that prints actions without executing them.
Phase 2: adds VPN connect/disconnect replay via the VPN adapter registry.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def _retry_vpn_action(fn, retries: int = 3, delay: float = 2.0) -> bool:
    """Call *fn* up to *retries* times with *delay* seconds between attempts.

    Returns True if any attempt succeeds, False otherwise.
    """
    for attempt in range(retries):
        if fn():
            return True
        if attempt < retries - 1:
            time.sleep(delay)
    return False


class Replayer:
    """Replays a list of workspace actions."""

    def __init__(self, workspace_name: str, actions: list[dict[str, Any]]) -> None:
        self.workspace_name = workspace_name
        self.actions = actions
        self._registry = None  # lazy-loaded

    def _get_registry(self):
        """Return a VPNAdapterRegistry, initialising it on first call."""
        if self._registry is None:
            from ctx.adapters.vpn.registry import VPNAdapterRegistry
            self._registry = VPNAdapterRegistry()
        return self._registry

    def replay(self) -> None:
        """Execute all recorded actions in order."""
        print(f"[ctx] Replaying workspace '{self.workspace_name}' ({len(self.actions)} actions)")
        for i, action in enumerate(self.actions, start=1):
            action_type = action.get("type", "unknown")
            data = action.get("data", {})

            if action_type == "vpn_connect":
                self._handle_vpn_connect(i, action)
            elif action_type == "vpn_disconnect":
                self._handle_vpn_disconnect(i, action)
            else:
                print(f"  [{i:>3}] {action_type}: {data}")

        print("[ctx] Replay complete")

    # ------------------------------------------------------------------
    # VPN action handlers
    # ------------------------------------------------------------------

    def _handle_vpn_connect(self, index: int, action: dict[str, Any]) -> None:
        """Replay a vpn_connect action using the appropriate adapter."""
        client = action.get("client", "")
        profile = action.get("profile")
        print(f"  [{index:>3}] vpn_connect: client={client!r} profile={profile!r}")

        registry = self._get_registry()
        adapter = registry.get_adapter(client)

        if adapter is None:
            logger.warning(
                "Replayer: no adapter found for VPN client %r — skipping vpn_connect", client
            )
            print(f"         [warn] No adapter for '{client}' — skipping")
            return

        config = dict(action)  # pass full action dict as config

        def _attempt() -> bool:
            return adapter.connect(config)

        success = _retry_vpn_action(_attempt)
        if success:
            print(f"         [ok] Connected via {client}")
        else:
            logger.warning(
                "Replayer: vpn_connect via %r failed after 3 retries", client
            )
            print(f"         [warn] vpn_connect via '{client}' failed after 3 retries — continuing")

    def _handle_vpn_disconnect(self, index: int, action: dict[str, Any]) -> None:
        """Replay a vpn_disconnect action using the appropriate adapter."""
        client = action.get("client", "")
        print(f"  [{index:>3}] vpn_disconnect: client={client!r}")

        registry = self._get_registry()
        adapter = registry.get_adapter(client)

        if adapter is None:
            logger.warning(
                "Replayer: no adapter found for VPN client %r — skipping vpn_disconnect", client
            )
            print(f"         [warn] No adapter for '{client}' — skipping")
            return

        success = adapter.disconnect()
        if success:
            print(f"         [ok] Disconnected via {client}")
        else:
            logger.warning("Replayer: vpn_disconnect via %r failed", client)
            print(f"         [warn] vpn_disconnect via '{client}' failed — continuing")
