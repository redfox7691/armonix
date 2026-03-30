"""Utility helpers for locating Armonix resources on the filesystem."""

from __future__ import annotations

import os
import sys
from typing import Optional


PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

if sys.platform == "darwin":
    # macOS: segue le convenzioni Apple (Application Support).
    USER_CONFIG_DIR = os.path.join(
        os.path.expanduser("~/Library/Application Support"), "armonix"
    )
    SYSTEM_CONFIG_DIR = "/Library/Application Support/armonix"
else:
    # Linux: segue le specifiche XDG.
    USER_CONFIG_DIR = os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "armonix",
    )
    SYSTEM_CONFIG_DIR = "/etc/armonix"

# Directory that always contains the pristine configuration files installed
# together with the Python modules.  Used as last-resort fallback.
DEFAULT_CONFIG_DIR = PACKAGE_DIR


def _join_if_exists(directory: str, filename: str) -> Optional[str]:
    path = os.path.join(directory, filename)
    return path if os.path.exists(path) else None


def get_config_path(filename: str) -> str:
    """Return the preferred path for a configuration file.

    Lookup order:
    1. ``~/.config/armonix/`` — user-local overrides (highest priority)
    2. ``/etc/armonix/``      — system-wide defaults managed by the package
    3. ``PACKAGE_DIR``        — source tree fallback for development
    """

    user_copy = _join_if_exists(USER_CONFIG_DIR, filename)
    if user_copy:
        return user_copy

    system_copy = _join_if_exists(SYSTEM_CONFIG_DIR, filename)
    if system_copy:
        return system_copy

    default_copy = _join_if_exists(DEFAULT_CONFIG_DIR, filename)
    if default_copy:
        return default_copy

    # Last resort: expected user config location even if not present yet.
    return os.path.join(USER_CONFIG_DIR, filename)


def get_default_config_path(filename: str) -> str:
    """Return the absolute path to the packaged pristine configuration."""

    return os.path.join(DEFAULT_CONFIG_DIR, filename)
