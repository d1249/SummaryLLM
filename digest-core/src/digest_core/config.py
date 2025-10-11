"""
Configuration management using pydantic-settings.
"""
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import List, Dict, Optional
import os


class TimeConfig(BaseModel):
    """Time zone and window configuration."""
    user_timezone: str = Field(default="Europe/Moscow", description="User timezone")
    window: str = Field(default="calendar_day", description="Window mode: calendar_day | rolling_24h")


class EWSConfig(BaseModel):
    """Exchange Web Services configuration."""
    endpoint: str = Field(description="EWS endpoint URL")
    user_upn: str = Field(description="User UPN (user@corp)")
    password_env: str = Field(default="EWS_PASSWORD", description="Environment variable for password")
    verify_ca: Optional[str] = Field(default=None, description="Path to CA certificate")
    autodiscover: bool = Field(default=False, description="Enable autodiscover")
    folders: List[str] = Field(default=["Inbox"], description="Folders to process")
    lookback_hours: int = Field(default=24, description="Hours to look back")
    page_size: int = Field(default=100, description="Page size for pagination")
    sync_state_path: str = Field(default=".state/ews.syncstate", description="Sync state file path")


class LLMConfig(BaseModel):
    """LLM Gateway configuration."""
    endpoint: str = Field(description="LLM Gateway endpoint")
    model: str = Field(default="corp/gpt-4o-mini", description="Model identifier")
    timeout_s: int = Field(default=45, description="Request timeout in seconds")
    headers: Dict[str, str] = Field(default_factory=dict, description="Additional headers")
    max_tokens_per_run: int = Field(default=30000, description="Max tokens per run")
    cost_limit_per_run: float = Field(default=5.0, description="Cost limit per run in USD")


class ObservabilityConfig(BaseModel):
    """Observability configuration."""
    prometheus_port: int = Field(default=9108, description="Prometheus metrics port")
    log_level: str = Field(default="INFO", description="Log level")


class Config(BaseSettings):
    """Main configuration class."""
    
    # Sub-configurations
    time: TimeConfig = Field(default_factory=TimeConfig)
    ews: EWSConfig = Field(default_factory=EWSConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    
    class Config:
        env_file = "configs/config.example.yaml"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Load from YAML file if it exists
        yaml_path = "configs/config.example.yaml"
        if os.path.exists(yaml_path):
            import yaml
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                
            # Override with YAML values
            if 'time' in yaml_config:
                self.time = TimeConfig(**yaml_config['time'])
            if 'ews' in yaml_config:
                self.ews = EWSConfig(**yaml_config['ews'])
            if 'llm' in yaml_config:
                self.llm = LLMConfig(**yaml_config['llm'])
            if 'observability' in yaml_config:
                self.observability = ObservabilityConfig(**yaml_config['observability'])
    
    def get_ews_password(self) -> str:
        """Get EWS password from environment."""
        password = os.getenv(self.ews.password_env)
        if not password:
            raise ValueError(f"Environment variable {self.ews.password_env} not set")
        return password
    
    def get_llm_token(self) -> str:
        """Get LLM token from environment."""
        token = os.getenv("LLM_TOKEN")
        if not token:
            raise ValueError("Environment variable LLM_TOKEN not set")
        return token
