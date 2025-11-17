"""Configuration management with YAML and environment variable support"""

import os
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
            with open(self.config_path, "r") as f:
                yaml_data = yaml.safe_load(f)
                if yaml_data:
                    config_data = yaml_data

        # Create config with environment variable overrides
        # Pydantic Settings will automatically handle env var overrides
        self._config = self._create_config_from_dict(config_data)

        return self._config

    def _create_config_from_dict(self, data: Dict[str, Any]) -> Config:
        """Create Config object from dictionary with nested structure"""
        # For pydantic-settings to properly handle env var overrides,
        # we need to use model_validate which respects the settings behavior
        import os

        # Merge YAML data with environment variables
        # Environment variables take precedence
        def merge_with_env(section_data: Dict[str, Any], prefix: str) -> Dict[str, Any]:
            """Merge section data with environment variables"""
            result = section_data.copy()
            for key in result.keys():
                env_key = f"{prefix}{key.upper()}"
                if env_key in os.environ:
                    # Convert env var to appropriate type
                    env_value = os.environ[env_key]
                    # Try to convert to int if possible
                    try:
                        result[key] = int(env_value)
                    except ValueError:
                        # Try bool
                        if env_value.lower() in ("true", "false"):
                            result[key] = env_value.lower() == "true"
                        else:
                            result[key] = env_value
            return result

        # Create nested config objects with env var merging
        server_data = merge_with_env(data.get("server", {}), "APP_SERVER_")
        server = ServerConfig(**server_data)

        timeouts_data = merge_with_env(data.get("timeouts", {}), "APP_TIMEOUTS_")
        timeouts = TimeoutsConfig(**timeouts_data)

        storage_data = merge_with_env(data.get("storage", {}), "APP_STORAGE_")
        storage = StorageConfig(**storage_data)

        downloads_data = merge_with_env(data.get("downloads", {}), "APP_DOWNLOADS_")
        downloads = DownloadsConfig(**downloads_data)

        rate_limiting_data = merge_with_env(data.get("rate_limiting", {}), "APP_RATE_LIMITING_")
        rate_limiting = RateLimitingConfig(**rate_limiting_data)

        templates_data = merge_with_env(data.get("templates", {}), "APP_TEMPLATES_")
        templates = TemplatesConfig(**templates_data)

        logging_data = merge_with_env(data.get("logging", {}), "APP_LOGGING_")
        logging_config = LoggingConfig(**logging_data)

        security_data = merge_with_env(data.get("security", {}), "APP_SECURITY_")
        security = SecurityConfig(**security_data)

        monitoring_data = merge_with_env(data.get("monitoring", {}), "APP_MONITORING_")
        monitoring = MonitoringConfig(**monitoring_data)

        # Handle providers
        providers_data = data.get("providers", {})
        youtube_data = merge_with_env(providers_data.get("youtube", {}), "APP_YOUTUBE_")
        youtube_config = YouTubeProviderConfig(**youtube_data)
        providers = ProvidersConfig(youtube=youtube_config)

        # Create main config
        config = Config(
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

        return config

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
