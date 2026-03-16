"""Sanitizer — strips sensitive and machine-specific data before sharing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_HOME = str(Path.home())

# Private IP ranges: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
_PRIVATE_IP_RE = re.compile(
    r"(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})"
)

# Key names that suggest the value is a secret
_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|passwd|pwd|auth|credential|api[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)

# Fields that carry path values
_PATH_FIELDS = {"path", "directory", "cwd", "workspace_path", "compose_file", "project_path"}


def sanitize_path(value: str, project_root: str | None = None) -> str:
    """Replace home dir and project root prefixes with tokens."""
    # Expand ~ first
    if value.startswith("~"):
        value = str(Path(value).expanduser())

    if project_root:
        # Normalise so trailing slash doesn't matter
        pr = project_root.rstrip("/")
        if value == pr:
            return "{{PROJECT_ROOT}}"
        if value.startswith(pr + "/"):
            return "{{PROJECT_ROOT}}" + value[len(pr):]

    home = _HOME.rstrip("/")
    if value == home:
        return "{{HOME}}"
    if value.startswith(home + "/"):
        return "{{HOME}}" + value[len(home):]

    return value


def _contains_private_ip(value: str) -> bool:
    return bool(_PRIVATE_IP_RE.search(value))


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key))


def _is_path_value(key: str, value: str) -> bool:
    return key.lower() in _PATH_FIELDS or (
        isinstance(value, str) and (value.startswith("/") or value.startswith("~"))
    )


def sanitize_action(action: dict[str, Any], project_root: str | None = None) -> dict[str, Any]:
    """Return a sanitized copy of an action dict.

    Removed keys are noted under ``_removed`` so the caller can add a comment.
    """
    result: dict[str, Any] = {}
    removed: list[str] = []

    for key, value in action.items():
        # Always keep the type field
        if key == "type":
            result[key] = value
            continue

        # Strip secret-looking keys
        if _is_secret_key(key):
            removed.append(key)
            continue

        if isinstance(value, str):
            # Strip values containing private IPs
            if _contains_private_ip(value):
                removed.append(key)
                continue

            # Sanitize path-like values
            if _is_path_value(key, value):
                value = sanitize_path(value, project_root)

        result[key] = value

    if removed:
        result["_removed"] = removed

    return result
