"""Tests for configuration management"""

from pathlib import Path

import pytest
import yaml

from app.core.config import ConfigService


class TestConfigService:
    """Test ConfigService functionality"""

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """Test loading configuration from YAML file"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "server": {"host": "127.0.0.1", "port": 9000},
            "logging": {"level": "DEBUG"},
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        service = ConfigService(str(config_file))
        config = service.load()

        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9000
        assert config.logging.level == "DEBUG"

    def test_load_with_defaults(self, tmp_path: Path) -> None:
        """Test loading configuration with default values"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("{}")

        service = ConfigService(str(config_file))
        config = service.load()

        # Check defaults
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.timeouts.metadata == 10
        assert config.storage.max_file_size == 524288000

    def test_environment_variable_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test environment variable overrides YAML configuration"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000},
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Set environment variable
        monkeypatch.setenv("APP_SERVER_PORT", "9999")

        service = ConfigService(str(config_file))
        config = service.load()

        # Environment variable should override YAML
        assert config.server.port == 9999
        assert config.server.host == "127.0.0.1"

    def test_nested_environment_variable_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test nested configuration override with environment variables"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("{}")

        monkeypatch.setenv("APP_STORAGE_OUTPUT_DIR", "/custom/path")
        monkeypatch.setenv("APP_TIMEOUTS_DOWNLOAD", "600")

        service = ConfigService(str(config_file))
        config = service.load()

        assert config.storage.output_dir == "/custom/path"
        assert config.timeouts.download == 600

    def test_validation_threshold_range(self, tmp_path: Path) -> None:
        """Test cleanup_threshold validation"""
        config_file = tmp_path / "config.yaml"

        # Test invalid threshold > 100
        config_data = {"storage": {"cleanup_threshold": 150}}
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        service = ConfigService(str(config_file))
        with pytest.raises(ValueError, match="cleanup_threshold must be between 0 and 100"):
            service.load()

    def test_validation_log_level(self, tmp_path: Path) -> None:
        """Test log level validation"""
        config_file = tmp_path / "config.yaml"
        config_data = {"logging": {"level": "INVALID"}}

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        service = ConfigService(str(config_file))
        with pytest.raises(ValueError, match="level must be one of"):
            service.load()

    def test_validation_requires_api_keys(self, tmp_path: Path) -> None:
        """Test validation requires at least one API key"""
        config_file = tmp_path / "config.yaml"
        config_data = {"security": {"api_keys": [], "allow_degraded_start": False}}

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        service = ConfigService(str(config_file))
        service.load()

        with pytest.raises(ValueError, match="At least one API key must be configured"):
            service.validate()

    def test_validation_allows_degraded_start(self, tmp_path: Path) -> None:
        """Test validation allows empty API keys in degraded mode"""
        config_file = tmp_path / "config.yaml"
        config_data = {"security": {"api_keys": [], "allow_degraded_start": True}}

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        service = ConfigService(str(config_file))
        service.load()

        # Should not raise in degraded mode
        assert service.validate() is True

    def test_load_nonexistent_file(self) -> None:
        """Test loading when config file doesn't exist uses defaults"""
        service = ConfigService("nonexistent.yaml")
        config = service.load()

        # Should load with defaults
        assert config.server.port == 8000
        assert config.logging.level == "INFO"

    def test_config_property_before_load(self) -> None:
        """Test accessing config property before loading raises error"""
        service = ConfigService()

        with pytest.raises(ValueError, match="Configuration not loaded"):
            _ = service.config

    def test_validate_before_load(self) -> None:
        """Test validating before loading raises error"""
        service = ConfigService()

        with pytest.raises(ValueError, match="Configuration not loaded"):
            service.validate()
