"""Configuration management with YAML and environment variable support"""

import os
from typing import Any, Dict, List, Optional, Tuple, Type

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class BaseConfigSection(BaseSettings):
    """Base class for all config sections with correct environment variable precedence.

    This class customizes the settings source priority to ensure that:
    1. Environment variables have highest priority
    2. Init kwargs (YAML data) have second priority
    3. Default values have lowest priority

    This allows environment variables to override YAML configuration as expected.
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings source priority: env vars > init kwargs > defaults."""
        return (env_settings, init_settings, dotenv_settings, file_secret_settings)


class ServerConfig(BaseConfigSection):
    """Server configuration"""

    host: str = (
        "0.0.0.0"  # nosec B104 - Intentional binding to all interfaces for containerized deployment
    )
    port: int = 8000
    workers: int = 4

    model_config = SettingsConfigDict(env_prefix="APP_SERVER_")


class TimeoutsConfig(BaseConfigSection):
    """Operation timeout configuration"""

    metadata: int = 10  # seconds
    download: int = 300
    audio_conversion: int = 60

    model_config = SettingsConfigDict(env_prefix="APP_TIMEOUTS_")


class StorageConfig(BaseConfigSection):
    """Storage and file management configuration"""

    output_dir: str = "/app/downloads"
    cookie_dir: str = "/app/cookies"
    cleanup_age: int = 24  # hours
    cleanup_threshold: int = 80  # disk usage percentage
    max_file_size: int = 524288000  # 500MB in bytes

    model_config = SettingsConfigDict(env_prefix="APP_STORAGE_")

    @field_validator("cleanup_threshold")
    @classmethod
    def validate_threshold(cls, v: int) -> int:
        if not 0 < v <= 100:
            raise ValueError("cleanup_threshold must be between 1 and 100")
        return v


class DownloadsConfig(BaseConfigSection):
    """Download queue configuration"""

    max_concurrent: int = 5
    queue_size: int = 100
    job_ttl: int = 24  # hours - time to keep completed/failed jobs

    model_config = SettingsConfigDict(env_prefix="APP_DOWNLOADS_")


class RateLimitingConfig(BaseConfigSection):
    """Rate limiting configuration"""

    metadata_rpm: int = 100  # requests per minute
    download_rpm: int = 10
    burst_capacity: int = 20  # maximum tokens

    model_config = SettingsConfigDict(env_prefix="APP_RATE_LIMITING_")


class TemplatesConfig(BaseConfigSection):
    """Output template configuration"""

    default_output: str = "%(title)s-%(id)s.%(ext)s"

    model_config = SettingsConfigDict(env_prefix="APP_TEMPLATES_")


class YouTubeProviderConfig(BaseConfigSection):
    """YouTube provider configuration"""

    enabled: bool = True
    cookie_path: Optional[str] = None
    retry_attempts: int = 3
    retry_backoff: List[int] = Field(default_factory=lambda: [2, 4, 8])

    model_config = SettingsConfigDict(env_prefix="APP_YOUTUBE_")


class ProvidersConfig(BaseConfigSection):
    """Providers configuration"""

    youtube: YouTubeProviderConfig = Field(default_factory=YouTubeProviderConfig)


class LoggingConfig(BaseConfigSection):
    """Logging configuration"""

    level: str = "INFO"
    format: str = "json"

    model_config = SettingsConfigDict(env_prefix="APP_LOGGING_")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"level must be one of {valid_levels}")
        return v_upper


class SecurityConfig(BaseConfigSection):
    """Security configuration"""

    api_keys: List[str] = Field(default_factory=list)
    allow_degraded_start: bool = False

    model_config = SettingsConfigDict(env_prefix="APP_SECURITY_")


class MonitoringConfig(BaseConfigSection):
    """Monitoring configuration"""

    metrics_enabled: bool = True
    metrics_port: int = 9090

    model_config = SettingsConfigDict(env_prefix="APP_MONITORING_")


class Config(BaseSettings):
    """Main application configuration"""

    server: ServerConfig = Field(default_factory=ServerConfig)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    downloads: DownloadsConfig = Field(default_factory=DownloadsConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    templates: TemplatesConfig = Field(default_factory=TemplatesConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    model_config = SettingsConfigDict(env_prefix="APP_")


class ConfigService:
    """Service for loading and managing configuration"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self._config: Optional[Config] = None

    def load(self) -> Config:
        """Load configuration from YAML file with environment variable overrides.

        Thanks to BaseConfigSection.settings_customise_sources(), environment variables
        automatically take precedence over YAML values, which in turn take precedence
        over defaults. No manual checking required.
        """
        config_data: Dict[str, Any] = {}

        # Load from YAML file if it exists
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
                if yaml_data:
                    config_data = yaml_data

        # Create nested config objects - BaseConfigSection handles env var precedence
        server = ServerConfig(**config_data.get("server", {}))
        timeouts = TimeoutsConfig(**config_data.get("timeouts", {}))
        storage = StorageConfig(**config_data.get("storage", {}))
        downloads = DownloadsConfig(**config_data.get("downloads", {}))
        rate_limiting = RateLimitingConfig(**config_data.get("rate_limiting", {}))
        templates = TemplatesConfig(**config_data.get("templates", {}))
        logging_config = LoggingConfig(**config_data.get("logging", {}))
        security = SecurityConfig(**config_data.get("security", {}))
        monitoring = MonitoringConfig(**config_data.get("monitoring", {}))

        # Handle providers
        providers_data = config_data.get("providers", {})
        youtube_config = YouTubeProviderConfig(**providers_data.get("youtube", {}))
        providers = ProvidersConfig(youtube=youtube_config)

        # Create main config
        self._config = Config(
            server=server,
            timeouts=timeouts,
            storage=storage,
            downloads=downloads,
            rate_limiting=rate_limiting,
            templates=templates,
            providers=providers,
            logging=logging_config,
            security=security,
            monitoring=monitoring,
        )

        return self._config

    def validate(self) -> bool:
        """Validate the loaded configuration"""
        if self._config is None:
            raise ValueError("Configuration not loaded. Call load() first.")

        # Additional validation logic
        if not self._config.security.api_keys and not self._config.security.allow_degraded_start:
            raise ValueError("At least one API key must be configured")

        return True

    @property
    def config(self) -> Config:
        """Get the loaded configuration"""
        if self._config is None:
            raise ValueError("Configuration not loaded. Call load() first.")
        return self._config
