"""Tests for package metadata helpers."""

from importlib.metadata import version

import moneywiz_mcp_server


def test_package_version_matches_installed_metadata() -> None:
    """Package __version__ should reflect installed distribution metadata."""
    assert moneywiz_mcp_server.__version__ == version("moneywiz-mcp-server")
