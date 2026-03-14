"""iTerm2 terminal adapter for ctx."""

from __future__ import annotations

import subprocess

from ctx.adapters.terminal.base import TerminalAdapter

_GET_DIRS_SCRIPT = """\
tell application "iTerm2"
    set dirList to {}
    repeat with aWindow in windows
        repeat with aTab in tabs of aWindow
            set aSession to current session of aTab
            set sessionPath to path of aSession
            if sessionPath is not missing value then
                set end of dirList to sessionPath
            end if
        end repeat
    end repeat
    set AppleScript's text item delimiters to "\\n"
    return dirList as text
end tell
"""


class ITerm2Adapter(TerminalAdapter):
    """Adapter for iTerm2 on macOS."""

    @property
    def name(self) -> str:
        return "iterm2"

    def is_available(self) -> bool:
        result = subprocess.run(
            ["pgrep", "-x", "iTerm2"],
            capture_output=True,
        )
        return result.returncode == 0

    def get_open_dirs(self) -> list[str]:
        try:
            result = subprocess.run(
                ["osascript", "-e", _GET_DIRS_SCRIPT],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return []
            output = result.stdout.strip()
            if not output:
                return []
            return [d for d in output.split("\n") if d]
        except Exception:
            return []

    def open_in_dir(self, directory: str) -> bool:
        script = (
            'tell application "iTerm2"\n'
            '    create window with default profile\n'
            '    tell current session of current window\n'
            f"        write text \"cd '{directory}'\"\n"
            '    end tell\n'
            'end tell'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
        )
        return result.returncode == 0
