"""Pytest configuration and shared fixtures"""

import os

import pytest


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset environment variables before each test"""
    # Clear any APP_ prefixed environment variables
    for key in list(os.environ.keys()):
        if key.startswith("APP_"):
            monkeypatch.delenv(key, raising=False)
