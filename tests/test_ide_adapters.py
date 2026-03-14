"""Unit tests for IDE adapters (mocked subprocess and filesystem calls)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ctx.adapters.ide.base import IDEAdapter, ProjectSet
from ctx.adapters.ide.vscode import VSCodeAdapter, _parse_vscode_storage
from ctx.adapters.ide.cursor import CursorAdapter, _parse_cursor_storage
from ctx.adapters.ide.zed import ZedAdapter
from ctx.adapters.ide.registry import IDEAdapterRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_process(returncode=0):
    mock = MagicMock()
    mock.returncode = returncode
    return mock


def _make_storage_json(paths: list[str]) -> str:
    workspaces = [{"folderUri": f"file://{p}"} for p in paths]
    return json.dumps({"openedPathsList": {"workspaces3": workspaces}})


# ---------------------------------------------------------------------------
# _parse_vscode_storage helper
# ---------------------------------------------------------------------------

class TestParseVscodeStorage:
    def test_returns_existing_paths(self, tmp_path):
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        storage = tmp_path / "storage.json"
        storage.write_text(_make_storage_json([str(project_dir)]))

        result = _parse_vscode_storage(storage)
        assert str(project_dir) in result

    def test_skips_nonexistent_paths(self, tmp_path):
        storage = tmp_path / "storage.json"
        storage.write_text(_make_storage_json(["/does/not/exist"]))

        result = _parse_vscode_storage(storage)
        assert result == []

    def test_returns_empty_on_invalid_json(self, tmp_path):
        storage = tmp_path / "storage.json"
        storage.write_text("not json")
        assert _parse_vscode_storage(storage) == []

    def test_skips_entries_without_uri(self, tmp_path):
        storage = tmp_path / "storage.json"
        storage.write_text(json.dumps({"openedPathsList": {"workspaces3": [{}]}}))
        assert _parse_vscode_storage(storage) == []


# ---------------------------------------------------------------------------
# VSCodeAdapter
# ---------------------------------------------------------------------------

class TestVSCodeAdapter:
    def setup_method(self):
        self.adapter = VSCodeAdapter()

    def test_name(self):
        assert self.adapter.name == "vscode"

    def test_is_available_when_binary_present(self):
        with patch("shutil.which", return_value="/usr/local/bin/code"):
            assert self.adapter.is_available() is True

    def test_is_available_when_binary_missing(self):
        with patch("shutil.which", return_value=None):
            assert self.adapter.is_available() is False

    def test_get_open_projects_reads_storage(self, tmp_path):
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        storage = tmp_path / "storage.json"
        storage.write_text(_make_storage_json([str(project_dir)]))

        with patch("ctx.adapters.ide.vscode._STORAGE_CANDIDATES", [storage]):
            result = self.adapter.get_open_projects()
        assert str(project_dir) in result

    def test_get_open_projects_returns_empty_when_no_storage(self, tmp_path):
        missing = tmp_path / "missing.json"
        with patch("ctx.adapters.ide.vscode._STORAGE_CANDIDATES", [missing]):
            assert self.adapter.get_open_projects() == []

    def test_open_project_success(self):
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            result = self.adapter.open_project("/path/to/project")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "code" in args
        assert "/path/to/project" in args

    def test_open_project_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            assert self.adapter.open_project("/path/to/project") is False


# ---------------------------------------------------------------------------
# CursorAdapter
# ---------------------------------------------------------------------------

class TestCursorAdapter:
    def setup_method(self):
        self.adapter = CursorAdapter()

    def test_name(self):
        assert self.adapter.name == "cursor"

    def test_is_available_when_binary_present(self):
        with patch("shutil.which", return_value="/usr/local/bin/cursor"):
            assert self.adapter.is_available() is True

    def test_is_available_when_binary_missing(self):
        with patch("shutil.which", return_value=None):
            assert self.adapter.is_available() is False

    def test_get_open_projects_reads_storage(self, tmp_path):
        project_dir = tmp_path / "cursorproject"
        project_dir.mkdir()
        storage = tmp_path / "storage.json"
        storage.write_text(_make_storage_json([str(project_dir)]))

        with patch("ctx.adapters.ide.cursor._STORAGE_PATH", storage):
            result = self.adapter.get_open_projects()
        assert str(project_dir) in result

    def test_get_open_projects_returns_empty_when_no_storage(self, tmp_path):
        missing = tmp_path / "missing.json"
        with patch("ctx.adapters.ide.cursor._STORAGE_PATH", missing):
            assert self.adapter.get_open_projects() == []

    def test_open_project_success(self):
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            result = self.adapter.open_project("/path/to/project")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "cursor" in args

    def test_open_project_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            assert self.adapter.open_project("/path/to/project") is False


# ---------------------------------------------------------------------------
# ZedAdapter
# ---------------------------------------------------------------------------

class TestZedAdapter:
    def setup_method(self):
        self.adapter = ZedAdapter()

    def test_name(self):
        assert self.adapter.name == "zed"

    def test_is_available_when_binary_present(self):
        with patch("shutil.which", return_value="/usr/local/bin/zed"):
            assert self.adapter.is_available() is True

    def test_is_available_when_binary_missing(self):
        with patch("shutil.which", return_value=None):
            assert self.adapter.is_available() is False

    def test_get_open_projects_reads_recent_projects(self, tmp_path):
        project_dir = tmp_path / "zedproject"
        project_dir.mkdir()
        recent = tmp_path / "recent_projects.json"
        recent.write_text(json.dumps([{"paths": [str(project_dir)]}]))

        with patch("ctx.adapters.ide.zed._RECENT_PROJECTS_PATH", recent):
            result = self.adapter.get_open_projects()
        assert str(project_dir) in result

    def test_get_open_projects_skips_nonexistent(self, tmp_path):
        recent = tmp_path / "recent_projects.json"
        recent.write_text(json.dumps([{"paths": ["/does/not/exist"]}]))

        with patch("ctx.adapters.ide.zed._RECENT_PROJECTS_PATH", recent):
            result = self.adapter.get_open_projects()
        assert result == []

    def test_get_open_projects_returns_empty_when_no_file(self, tmp_path):
        missing = tmp_path / "missing.json"
        with patch("ctx.adapters.ide.zed._RECENT_PROJECTS_PATH", missing):
            assert self.adapter.get_open_projects() == []

    def test_get_open_projects_returns_empty_on_invalid_json(self, tmp_path):
        recent = tmp_path / "recent_projects.json"
        recent.write_text("bad json")
        with patch("ctx.adapters.ide.zed._RECENT_PROJECTS_PATH", recent):
            assert self.adapter.get_open_projects() == []

    def test_open_project_success(self):
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            result = self.adapter.open_project("/path/to/project")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "zed" in args

    def test_open_project_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            assert self.adapter.open_project("/path/to/project") is False


# ---------------------------------------------------------------------------
# IDEAdapterRegistry
# ---------------------------------------------------------------------------

class TestIDEAdapterRegistry:
    def test_available_adapters_filters_by_availability(self):
        registry = IDEAdapterRegistry()
        mock_vscode = MagicMock()
        mock_vscode.is_available.return_value = True
        mock_cursor = MagicMock()
        mock_cursor.is_available.return_value = False
        mock_zed = MagicMock()
        mock_zed.is_available.return_value = False
        registry._adapters = [mock_vscode, mock_cursor, mock_zed]

        assert registry.available_adapters() == [mock_vscode]

    def test_available_adapters_empty_when_none_available(self):
        registry = IDEAdapterRegistry()
        with patch("shutil.which", return_value=None):
            assert registry.available_adapters() == []

    def test_get_adapter_vscode(self):
        registry = IDEAdapterRegistry()
        assert registry.get_adapter("vscode").name == "vscode"

    def test_get_adapter_cursor(self):
        registry = IDEAdapterRegistry()
        assert registry.get_adapter("cursor").name == "cursor"

    def test_get_adapter_zed(self):
        registry = IDEAdapterRegistry()
        assert registry.get_adapter("zed").name == "zed"

    def test_get_adapter_unknown_returns_none(self):
        registry = IDEAdapterRegistry()
        assert registry.get_adapter("vim") is None


# ---------------------------------------------------------------------------
# ProjectSet dataclass
# ---------------------------------------------------------------------------

class TestProjectSet:
    def test_default_paths_empty(self):
        ps = ProjectSet(client="vscode")
        assert ps.paths == []

    def test_with_paths(self):
        ps = ProjectSet(client="zed", paths=["/a", "/b"])
        assert len(ps.paths) == 2
