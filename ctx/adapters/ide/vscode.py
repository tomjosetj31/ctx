"""Visual Studio Code IDE adapter for ctx."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ctx.adapters.ide.base import IDEAdapter

# VS Code stores recently opened workspaces in these locations on macOS
_STORAGE_CANDIDATES = [
    Path.home() / "Library/Application Support/Code/User/globalStorage/storage.json",
    Path.home() / "Library/Application Support/VSCodium/User/globalStorage/storage.json",
]


def _parse_vscode_storage(storage_path: Path) -> list[str]:
    """Return workspace paths from VS Code's storage.json."""
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


class VSCodeAdapter(IDEAdapter):
    """Adapter for Visual Studio Code on macOS."""

    @property
    def name(self) -> str:
        return "vscode"

    def is_available(self) -> bool:
        return shutil.which("code") is not None

    def get_open_projects(self) -> list[str]:
        for storage in _STORAGE_CANDIDATES:
            if storage.exists():
                return _parse_vscode_storage(storage)
        return []

    def open_project(self, path: str) -> bool:
        result = subprocess.run(
            ["code", path],
            capture_output=True,
        )
        return result.returncode == 0
