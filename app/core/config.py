"""Configuration management with YAML and environment variable support"""

import os
from typing import Any, Dict, List, Optional, TypeVar

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

T = TypeVar("T", bound=BaseSettings)


class ServerConfig(BaseSettings):
    """Server configuration"""

    host: str = (
        "0.0.0.0"  # nosec B104 - Intentional binding to all interfaces for containerized deployment
    )
    port: int = 8000
    workers: int = 4

    model_config = SettingsConfigDict(env_prefix="APP_SERVER_")


class TimeoutsConfig(BaseSettings):
    """Operation timeout configuration"""

    metadata: int = 10  # seconds
    download: int = 300
    audio_conversion: int = 60

    model_config = SettingsConfigDict(env_prefix="APP_TIMEOUTS_")


class StorageConfig(BaseSettings):
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
        if not 0 <= v <= 100:
            raise ValueError("cleanup_threshold must be between 0 and 100")
        return v


class DownloadsConfig(BaseSettings):
    """Download queue configuration"""

    max_concurrent: int = 5
    queue_size: int = 100

    model_config = SettingsConfigDict(env_prefix="APP_DOWNLOADS_")


class RateLimitingConfig(BaseSettings):
    """Rate limiting configuration"""

    metadata_rpm: int = 100  # requests per minute
    download_rpm: int = 10
    burst_capacity: int = 20  # maximum tokens

    model_config = SettingsConfigDict(env_prefix="APP_RATE_LIMITING_")


class TemplatesConfig(BaseSettings):
    """Output template configuration"""

    default_output: str = "%(title)s-%(id)s.%(ext)s"

    model_config = SettingsConfigDict(env_prefix="APP_TEMPLATES_")


class YouTubeProviderConfig(BaseSettings):
    """YouTube provider configuration"""

    enabled: bool = True
    cookie_path: Optional[str] = None
    retry_attempts: int = 3
    retry_backoff: List[int] = Field(default_factory=lambda: [2, 4, 8])

    model_config = SettingsConfigDict(env_prefix="APP_YOUTUBE_")


class ProvidersConfig(BaseSettings):
    """Providers configuration"""

    youtube: YouTubeProviderConfig = Field(default_factory=YouTubeProviderConfig)


class LoggingConfig(BaseSettings):
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


class SecurityConfig(BaseSettings):
    """Security configuration"""

    api_keys: List[str] = Field(default_factory=list)
    allow_degraded_start: bool = False

    model_config = SettingsConfigDict(env_prefix="APP_SECURITY_")


class MonitoringConfig(BaseSettings):
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
        """Load configuration from YAML file with environment variable overrides"""
        config_data: Dict[str, Any] = {}

        # Load from YAML file if it exists
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
                if yaml_data:
                    config_data = yaml_data

        # Create nested config objects by calling parse_obj which respects env vars
        # For BaseSettings, we need to let it initialize without kwargs to read env vars
        # Then we can override with YAML values that aren't overridden by env
        def create_config_section(
            config_class: type[T], yaml_data: Dict[str, Any], env_prefix: str
        ) -> T:
            """Create a config section with proper env var precedence"""
            # Check which fields have env var overrides
            init_data = {}
            for field_name in yaml_data.keys():
                env_var = f"{env_prefix}{field_name.upper()}"
                if env_var not in os.environ:
                    # Only use YAML value if no env var exists
                    init_data[field_name] = yaml_data[field_name]

            # Create instance - it will read env vars automatically
            return config_class(**init_data)

        server = create_config_section(ServerConfig, config_data.get("server", {}), "APP_SERVER_")
        timeouts = create_config_section(
            TimeoutsConfig, config_data.get("timeouts", {}), "APP_TIMEOUTS_"
        )
        storage = create_config_section(
            StorageConfig, config_data.get("storage", {}), "APP_STORAGE_"
        )
        downloads = create_config_section(
            DownloadsConfig, config_data.get("downloads", {}), "APP_DOWNLOADS_"
        )
        rate_limiting = create_config_section(
            RateLimitingConfig, config_data.get("rate_limiting", {}), "APP_RATE_LIMITING_"
        )
        templates = create_config_section(
            TemplatesConfig, config_data.get("templates", {}), "APP_TEMPLATES_"
        )
        logging_config = create_config_section(
            LoggingConfig, config_data.get("logging", {}), "APP_LOGGING_"
        )
        security = create_config_section(
            SecurityConfig, config_data.get("security", {}), "APP_SECURITY_"
        )
        monitoring = create_config_section(
            MonitoringConfig, config_data.get("monitoring", {}), "APP_MONITORING_"
        )

        # Handle providers
        providers_data = config_data.get("providers", {})
        youtube_config = create_config_section(
            YouTubeProviderConfig, providers_data.get("youtube", {}), "APP_YOUTUBE_"
        )
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
