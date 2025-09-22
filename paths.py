"""Utility helpers for locating Armonix resources on the filesystem."""

from __future__ import annotations

import os
from typing import Optional


PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# System-wide configuration directory used by the Debian package.
SYSTEM_CONFIG_DIR = "/etc/armonix"

# Directory that always contains the pristine configuration files installed
# together with the Python modules.  The Debian package also ships copies of
# these files under ``/usr/share/armonix/examples`` so that administrators can
# easily restore the defaults.
DEFAULT_CONFIG_DIR = PACKAGE_DIR


def _join_if_exists(directory: str, filename: str) -> Optional[str]:
    path = os.path.join(directory, filename)
    return path if os.path.exists(path) else None


def get_config_path(filename: str) -> str:
    """Return the preferred path for a configuration file.

    The lookup order mirrors the filesystem layout of the Debian package: the
    administrator-managed copy in ``/etc/armonix`` has precedence while the
    pristine copy that ships with the Python modules is used as a fallback so
    that Armonix always has sensible defaults to load.
    """

    system_copy = _join_if_exists(SYSTEM_CONFIG_DIR, filename)
    if system_copy:
        return system_copy

    default_copy = _join_if_exists(DEFAULT_CONFIG_DIR, filename)
    if default_copy:
        return default_copy

    # As a last resort return the expected location inside /etc even if the
    # file does not currently exist.  This mirrors the behaviour of many system
    # daemons that expect administrators to provide their own configuration.
    return os.path.join(SYSTEM_CONFIG_DIR, filename)


def get_default_config_path(filename: str) -> str:
    """Return the absolute path to the packaged pristine configuration."""

    return os.path.join(DEFAULT_CONFIG_DIR, filename)
