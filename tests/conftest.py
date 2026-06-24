"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A throwaway workspace directory for a test."""
    return tmp_path
