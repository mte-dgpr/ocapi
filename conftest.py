"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Path to the repository root for tests."""
    return Path(__file__).resolve().parent
