"""Unix socket recorder daemon for ctx.

Run as a subprocess by `ctx record <name>`. Listens for JSON messages on a
Unix domain socket, accumulates actions in memory, and flushes them to the
SQLite store on a stop command.

Usage (internal — spawned by the CLI):
    python -m ctx.daemon.server <workspace_name> [--db <db_path>]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# Make sure the project root is importable when run as __main__
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ctx.store.workspace_store import WorkspaceStore
from ctx.adapters.vpn.registry import VPNAdapterRegistry

_CTX_DIR = Path.home() / ".ctx"
_SOCKET_PATH = _CTX_DIR / "daemon.sock"
_PID_PATH = _CTX_DIR / "daemon.pid"

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VPNPoller:
    """Background thread that polls VPN state and appends events to the action log.

    Polls every *poll_interval* seconds. On a state transition
    (None→connected or connected→None) it appends a ``vpn_connect`` or
    ``vpn_disconnect`` action dict to the shared *actions* list.
    """

    def __init__(
        self,
        actions: list[dict],
        poll_interval: float = 2.0,
    ) -> None:
        self._actions = actions
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_state: bool | None = None  # None = unknown, True = connected
        self._last_client: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the polling thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="vpn-poller")
        self._thread.start()

    def stop(self) -> None:
        """Signal the polling thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval + 1)

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop — runs in a background thread."""
        try:
            registry = VPNAdapterRegistry()
        except Exception as exc:
            logger.warning("VPNPoller: could not initialise registry: %s", exc)
            return

        while not self._stop_event.is_set():
            try:
                self._poll(registry)
            except Exception as exc:
                logger.warning("VPNPoller: poll error: %s", exc)
            self._stop_event.wait(timeout=self._poll_interval)

    def _poll(self, registry) -> None:
        """Check current VPN state and emit an event if it changed."""
        result = registry.detect_active()
        if result is not None:
            _adapter, state = result
            currently_connected = True
            client = state.client
            profile = state.profile
        else:
            currently_connected = False
            client = self._last_client
            profile = None

        if self._last_state is None:
            # First poll — record baseline without emitting an event
            self._last_state = currently_connected
            self._last_client = client
            return

        if currently_connected and not self._last_state:
            # Transition: disconnected → connected
            self._actions.append(
                {
                    "type": "vpn_connect",
                    "client": client,
                    "profile": profile,
                    "timestamp": _now_iso(),
                }
            )
            self._last_client = client
        elif not currently_connected and self._last_state:
            # Transition: connected → disconnected
            self._actions.append(
                {
                    "type": "vpn_disconnect",
                    "client": self._last_client,
                    "timestamp": _now_iso(),
                }
            )

        self._last_state = currently_connected
        if currently_connected:
            self._last_client = client


class RecorderDaemon:
    """In-process Unix socket server that records workspace actions."""

    def __init__(self, workspace_name: str, db_path: Path) -> None:
        self.workspace_name = workspace_name
        self.db_path = db_path
        self._actions: list[dict] = []
        self._running = False
        self._sock: socket.socket | None = None
        self._workspace_id: int | None = None
        self._vpn_poller: VPNPoller | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise the store entry, write PID, and start the event loop."""
        _CTX_DIR.mkdir(parents=True, exist_ok=True)

        # Write PID file
        _PID_PATH.write_text(str(os.getpid()))

        # Create workspace in the store
        store = WorkspaceStore(self.db_path)
        self._workspace_id = store.create_workspace(self.workspace_name)
        store.close()

        # Remove stale socket file
        if _SOCKET_PATH.exists():
            _SOCKET_PATH.unlink()

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(_SOCKET_PATH))
        self._sock.listen(5)
        self._sock.settimeout(1.0)  # allows periodic checks of self._running

        self._running = True

        # Handle SIGTERM for clean shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Start VPN poller
        self._vpn_poller = VPNPoller(self._actions)
        self._vpn_poller.start()

        self._loop()

    def _handle_signal(self, signum: int, frame: object) -> None:
        self._shutdown()

    def _loop(self) -> None:
        """Accept connections and process messages until stopped."""
        assert self._sock is not None
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self._handle_connection(conn)
            finally:
                conn.close()

        self._cleanup()

    def _handle_connection(self, conn: socket.socket) -> None:
        """Read a JSON message from a connection and respond."""
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        if not data:
            return

        try:
            msg = json.loads(data.decode().strip())
        except json.JSONDecodeError:
            conn.sendall(b'{"status": "error", "reason": "invalid JSON"}\n')
            return

        command = msg.get("command")

        if command == "stop":
            action_count = self._flush_to_store()
            response = {
                "status": "ok",
                "workspace": self.workspace_name,
                "action_count": action_count,
            }
            conn.sendall((json.dumps(response) + "\n").encode())
            self._running = False

        elif command == "status":
            response = {
                "status": "ok",
                "workspace": self.workspace_name,
                "action_count": len(self._actions),
            }
            conn.sendall((json.dumps(response) + "\n").encode())

        elif command == "record_action":
            action = msg.get("action", {})
            self._actions.append(action)
            conn.sendall(b'{"status": "ok"}\n')

        else:
            conn.sendall(b'{"status": "error", "reason": "unknown command"}\n')

    # ------------------------------------------------------------------
    # Store flushing
    # ------------------------------------------------------------------

    def _flush_to_store(self) -> int:
        """Write accumulated actions to the store. Returns action count."""
        store = WorkspaceStore(self.db_path)
        try:
            if self._workspace_id is not None:
                store.save_actions(self._workspace_id, self._actions)
            return len(self._actions)
        finally:
            store.close()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _shutdown(self) -> None:
        self._running = False

    def _cleanup(self) -> None:
        # Stop the VPN poller first
        if self._vpn_poller is not None:
            self._vpn_poller.stop()

        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if _SOCKET_PATH.exists():
            _SOCKET_PATH.unlink(missing_ok=True)
        if _PID_PATH.exists():
            _PID_PATH.unlink(missing_ok=True)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ctx recorder daemon")
    parser.add_argument("workspace_name", help="Name of the workspace being recorded")
    parser.add_argument(
        "--db",
        default=str(_CTX_DIR / "ctx.db"),
        help="Path to the SQLite database (default: ~/.ctx/ctx.db)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    daemon = RecorderDaemon(
        workspace_name=args.workspace_name,
        db_path=Path(args.db),
    )
    daemon.start()
