"""Workspace replayer — executes recorded action sequences.

Phase 1: stub implementation that prints actions without executing them.
"""

from __future__ import annotations

from typing import Any


class Replayer:
    """Replays a list of workspace actions."""

    def __init__(self, workspace_name: str, actions: list[dict[str, Any]]) -> None:
        self.workspace_name = workspace_name
        self.actions = actions

    def replay(self) -> None:
        """Execute all recorded actions in order.

        Phase 1 stub — logs each action without performing real system calls.
        """
        print(f"[ctx] Replaying workspace '{self.workspace_name}' ({len(self.actions)} actions)")
        for i, action in enumerate(self.actions, start=1):
            action_type = action.get("type", "unknown")
            data = action.get("data", {})
            print(f"  [{i:>3}] {action_type}: {data}")
        print("[ctx] Replay complete (stub mode — no real actions performed)")
