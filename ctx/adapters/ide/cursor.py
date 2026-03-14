"""Cursor IDE adapter for ctx."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ctx.adapters.ide.base import IDEAdapter

_STORAGE_PATH = (
    Path.home() / "Library/Application Support/Cursor/User/globalStorage/storage.json"
)


def _parse_cursor_storage(storage_path: Path) -> list[str]:
    """Return workspace paths from Cursor's storage.json."""
    try:
        data = json.loads(storage_path.read_text())
    except Exception:
        return []
    entries = data.get("openedPathsList", {}).get("workspaces3", [])
    paths = []
    for entry in entries:
        uri = entry.get("folderUri", "") or entry.get("fileUri", "")
        if uri.startswith("file://"):
            path = uri[len("file://"):]
            if Path(path).exists():
                paths.append(path)
    return paths


class CursorAdapter(IDEAdapter):
    """Adapter for the Cursor IDE on macOS."""

    @property
    def name(self) -> str:
        return "cursor"

    def is_available(self) -> bool:
        return shutil.which("cursor") is not None

    def get_open_projects(self) -> list[str]:
        if _STORAGE_PATH.exists():
            return _parse_cursor_storage(_STORAGE_PATH)
        return []

    def open_project(self, path: str) -> bool:
        result = subprocess.run(
            ["cursor", path],
            capture_output=True,
        )
        return result.returncode == 0
