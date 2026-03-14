"""Unit tests for terminal adapters (mocked subprocess calls)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ctx.adapters.terminal.base import TerminalAdapter, TerminalSession
from ctx.adapters.terminal.iterm2 import ITerm2Adapter
from ctx.adapters.terminal.terminal_app import TerminalAppAdapter
from ctx.adapters.terminal.warp import WarpAdapter
from ctx.adapters.terminal.kitty import KittyAdapter
from ctx.adapters.terminal.registry import TerminalAdapterRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_process(stdout="", returncode=0):
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


# ---------------------------------------------------------------------------
# ITerm2Adapter
# ---------------------------------------------------------------------------

class TestITerm2Adapter:
    def setup_method(self):
        self.adapter = ITerm2Adapter()

    def test_name(self):
        assert self.adapter.name == "iterm2"

    def test_is_available_when_running(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)):
            assert self.adapter.is_available() is True

    def test_is_available_when_not_running(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.is_available() is False

    def test_get_open_dirs_returns_dirs(self):
        output = "/home/user/project1\n/home/user/project2\n"
        with patch("subprocess.run", return_value=_make_completed_process(stdout=output, returncode=0)):
            dirs = self.adapter.get_open_dirs()
        assert dirs == ["/home/user/project1", "/home/user/project2"]

    def test_get_open_dirs_returns_empty_on_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.get_open_dirs() == []

    def test_get_open_dirs_returns_empty_on_blank_output(self):
        with patch("subprocess.run", return_value=_make_completed_process(stdout="", returncode=0)):
            assert self.adapter.get_open_dirs() == []

    def test_get_open_dirs_filters_empty_strings(self):
        output = "/home/user/project1\n\n/home/user/project2\n"
        with patch("subprocess.run", return_value=_make_completed_process(stdout=output, returncode=0)):
            dirs = self.adapter.get_open_dirs()
        assert "" not in dirs
        assert len(dirs) == 2

    def test_open_in_dir_success(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)) as mock_run:
            result = self.adapter.open_in_dir("/home/user/myproject")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "osascript" in args

    def test_open_in_dir_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.open_in_dir("/home/user/myproject") is False

    def test_open_in_dir_script_contains_path(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)) as mock_run:
            self.adapter.open_in_dir("/my/special/dir")
        call_args = mock_run.call_args
        # The script is passed as a string argument
        script_arg = call_args[0][0][-1]
        assert "/my/special/dir" in script_arg


# ---------------------------------------------------------------------------
# TerminalAppAdapter
# ---------------------------------------------------------------------------

class TestTerminalAppAdapter:
    def setup_method(self):
        self.adapter = TerminalAppAdapter()

    def test_name(self):
        assert self.adapter.name == "terminal"

    def test_is_available_when_running(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)):
            assert self.adapter.is_available() is True

    def test_is_available_when_not_running(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.is_available() is False

    def test_get_open_dirs_returns_dirs(self):
        # First call: osascript returns tty list
        # Subsequent calls: lsof for PID, then lsof for cwd
        tty_result = _make_completed_process(stdout="/dev/ttys001\n", returncode=0)
        pid_result = _make_completed_process(stdout="1234\n", returncode=0)
        cwd_result = _make_completed_process(stdout="p1234\ncwd\nn/home/user/project\n", returncode=0)

        with patch("subprocess.run", side_effect=[tty_result, pid_result, cwd_result]):
            dirs = self.adapter.get_open_dirs()
        assert "/home/user/project" in dirs

    def test_get_open_dirs_returns_empty_on_osascript_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.get_open_dirs() == []

    def test_get_open_dirs_returns_empty_on_blank_output(self):
        with patch("subprocess.run", return_value=_make_completed_process(stdout="", returncode=0)):
            assert self.adapter.get_open_dirs() == []

    def test_open_in_dir_success(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)) as mock_run:
            result = self.adapter.open_in_dir("/home/user/myproject")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "osascript" in args

    def test_open_in_dir_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.open_in_dir("/home/user/myproject") is False

    def test_open_in_dir_script_contains_path(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)) as mock_run:
            self.adapter.open_in_dir("/my/special/dir")
        call_args = mock_run.call_args
        script_arg = call_args[0][0][-1]
        assert "/my/special/dir" in script_arg


# ---------------------------------------------------------------------------
# WarpAdapter
# ---------------------------------------------------------------------------

class TestWarpAdapter:
    def setup_method(self):
        self.adapter = WarpAdapter()

    def test_name(self):
        assert self.adapter.name == "warp"

    def test_is_available_when_running(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)):
            assert self.adapter.is_available() is True

    def test_is_available_when_not_running(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.is_available() is False

    def test_get_open_dirs_returns_empty(self):
        assert self.adapter.get_open_dirs() == []

    def test_open_in_dir_success(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)) as mock_run:
            result = self.adapter.open_in_dir("/home/user/myproject")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "open" in args
        assert "-a" in args
        assert "Warp" in args
        assert "/home/user/myproject" in args

    def test_open_in_dir_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.open_in_dir("/home/user/myproject") is False


# ---------------------------------------------------------------------------
# KittyAdapter
# ---------------------------------------------------------------------------

class TestKittyAdapter:
    def setup_method(self):
        self.adapter = KittyAdapter()

    def test_name(self):
        assert self.adapter.name == "kitty"

    def test_is_available_when_both_which_and_pgrep_succeed(self):
        with patch("shutil.which", return_value="/usr/local/bin/kitty"):
            with patch("subprocess.run", return_value=_make_completed_process(returncode=0)):
                assert self.adapter.is_available() is True

    def test_is_available_when_which_fails(self):
        with patch("shutil.which", return_value=None):
            assert self.adapter.is_available() is False

    def test_is_available_when_pgrep_fails(self):
        with patch("shutil.which", return_value="/usr/local/bin/kitty"):
            with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
                assert self.adapter.is_available() is False

    def test_get_open_dirs_parses_kitty_ls_output(self):
        kitty_ls_output = json.dumps([
            {
                "tabs": [
                    {
                        "windows": [
                            {"cwd": "/home/user/project1"},
                            {"cwd": "/home/user/project2"},
                        ]
                    }
                ]
            }
        ])
        with patch("subprocess.run", return_value=_make_completed_process(stdout=kitty_ls_output, returncode=0)):
            dirs = self.adapter.get_open_dirs()
        assert "/home/user/project1" in dirs
        assert "/home/user/project2" in dirs

    def test_get_open_dirs_returns_empty_on_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.get_open_dirs() == []

    def test_get_open_dirs_returns_empty_on_invalid_json(self):
        with patch("subprocess.run", return_value=_make_completed_process(stdout="not json", returncode=0)):
            assert self.adapter.get_open_dirs() == []

    def test_open_in_dir_success(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=0)) as mock_run:
            result = self.adapter.open_in_dir("/home/user/myproject")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "kitty" in args
        assert "--directory" in args
        assert "/home/user/myproject" in args

    def test_open_in_dir_failure(self):
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            assert self.adapter.open_in_dir("/home/user/myproject") is False


# ---------------------------------------------------------------------------
# TerminalAdapterRegistry
# ---------------------------------------------------------------------------

class TestTerminalAdapterRegistry:
    def test_available_adapters_filters_by_availability(self):
        registry = TerminalAdapterRegistry()
        mock_iterm2 = MagicMock()
        mock_iterm2.is_available.return_value = True
        mock_term = MagicMock()
        mock_term.is_available.return_value = False
        mock_warp = MagicMock()
        mock_warp.is_available.return_value = False
        mock_kitty = MagicMock()
        mock_kitty.is_available.return_value = False
        registry._adapters = [mock_iterm2, mock_term, mock_warp, mock_kitty]

        assert registry.available_adapters() == [mock_iterm2]

    def test_available_adapters_empty_when_none_available(self):
        registry = TerminalAdapterRegistry()
        with patch("subprocess.run", return_value=_make_completed_process(returncode=1)):
            with patch("shutil.which", return_value=None):
                assert registry.available_adapters() == []

    def test_get_adapter_iterm2(self):
        registry = TerminalAdapterRegistry()
        assert registry.get_adapter("iterm2").name == "iterm2"

    def test_get_adapter_terminal(self):
        registry = TerminalAdapterRegistry()
        assert registry.get_adapter("terminal").name == "terminal"

    def test_get_adapter_warp(self):
        registry = TerminalAdapterRegistry()
        assert registry.get_adapter("warp").name == "warp"

    def test_get_adapter_kitty(self):
        registry = TerminalAdapterRegistry()
        assert registry.get_adapter("kitty").name == "kitty"

    def test_get_adapter_unknown_returns_none(self):
        registry = TerminalAdapterRegistry()
        assert registry.get_adapter("ghostty") is None


# ---------------------------------------------------------------------------
# TerminalSession dataclass
# ---------------------------------------------------------------------------

class TestTerminalSession:
    def test_fields(self):
        session = TerminalSession(app="iterm2", directory="/home/user")
        assert session.app == "iterm2"
        assert session.directory == "/home/user"

    def test_equality(self):
        s1 = TerminalSession(app="iterm2", directory="/home/user")
        s2 = TerminalSession(app="iterm2", directory="/home/user")
        assert s1 == s2

    def test_inequality(self):
        s1 = TerminalSession(app="iterm2", directory="/home/user/a")
        s2 = TerminalSession(app="iterm2", directory="/home/user/b")
        assert s1 != s2
