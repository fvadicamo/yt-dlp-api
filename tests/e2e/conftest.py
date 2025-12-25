"""E2E test configuration and fixtures.

These fixtures set up a test environment with:
- Test mode enabled (APP_TESTING_TEST_MODE=true)
- API key authentication configured
- Degraded start allowed (no real cookies needed)
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Set test mode environment variable at module import time
# This ensures it's set before any app modules are imported
os.environ["APP_TESTING_TEST_MODE"] = "true"
os.environ["APP_TESTING_MOCK_YTDLP"] = "true"
os.environ["APP_SECURITY_ALLOW_DEGRADED_START"] = "true"


@pytest.fixture(scope="module")
def temp_downloads_dir() -> Generator[str, None, None]:
    """Create a temporary directory for downloads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(scope="module")
def dummy_cookie_file(temp_downloads_dir: str) -> str:
    """Create a dummy cookie file for testing."""
    cookie_dir = Path(temp_downloads_dir) / "cookies"
    cookie_dir.mkdir(exist_ok=True)
    cookie_file = cookie_dir / "youtube.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n" ".youtube.com\tTRUE\t/\tTRUE\t1999999999\tCONSENT\tYES+\n"
    )
    return str(cookie_file)


@pytest.fixture(scope="module")
def e2e_env(temp_downloads_dir: str, dummy_cookie_file: str) -> Generator[None, None, None]:
    """Set up environment variables for E2E testing."""
    # Set remaining environment variables (core test mode vars are set at module level)
    original_env: dict[str, str | None] = {}
    env_vars = {
        "APP_SECURITY_API_KEYS": '["e2e-test-api-key"]',
        "APP_LOGGING_LEVEL": "WARNING",
        "APP_STORAGE_OUTPUT_DIR": temp_downloads_dir,
        "APP_YOUTUBE_COOKIE_PATH": dummy_cookie_file,
        "APP_STORAGE_COOKIE_DIR": str(Path(dummy_cookie_file).parent),
    }

    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original values
    for key in original_env:
        original_value = original_env[key]
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture(scope="module")
def e2e_client(e2e_env: None) -> Generator[TestClient, None, None]:
    """Create a test client with test mode enabled.

    This fixture:
    - Enables test mode for mocked yt-dlp operations
    - Configures API key authentication
    - Uses a temporary directory for downloads

    Note: Core test mode vars are set at module level, other vars in e2e_env.
    """
    # Import after environment is set
    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth_headers() -> dict:
    """Authentication headers for API requests."""
    return {"X-API-Key": "e2e-test-api-key"}


@pytest.fixture
def demo_video_url() -> str:
    """URL for demo video (Rick Astley)."""
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def short_video_url() -> str:
    """URL for short demo video (Me at the zoo)."""
    return "https://www.youtube.com/watch?v=jNQXAC9IVRw"
