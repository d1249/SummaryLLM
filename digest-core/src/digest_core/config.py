"""
Configuration management using pydantic-settings.
"""
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import List, Dict, Optional
import os
import yaml
from pathlib import Path


class TimeConfig(BaseModel):
    """Time zone and window configuration."""
    user_timezone: str = Field(default="Europe/Moscow", description="User timezone")
    window: str = Field(default="calendar_day", description="Window mode: calendar_day | rolling_24h")


class EWSConfig(BaseModel):
    """Exchange Web Services configuration."""
    endpoint: str = Field(default="", description="EWS endpoint URL")
    user_upn: str = Field(default="", description="User UPN (user@corp)")
    user_login: Optional[str] = Field(default=None, description="User login for NTLM (e.g., ivanov)")
    user_domain: Optional[str] = Field(default=None, description="Domain for NTLM (e.g., corp-domain.ru)")
    password_env: str = Field(default="EWS_PASSWORD", description="Environment variable for password")
    verify_ca: Optional[str] = Field(default=None, description="Path to CA certificate")
    verify_ssl: bool = Field(default=True, description="Enable SSL certificate verification")
    autodiscover: bool = Field(default=False, description="Enable autodiscover")
    folders: List[str] = Field(default=["Inbox"], description="Folders to process")
    lookback_hours: int = Field(default=24, description="Hours to look back")
    page_size: int = Field(default=100, description="Page size for pagination")
    sync_state_path: str = Field(default=".state/ews.syncstate", description="Sync state file path")
    user_aliases: List[str] = Field(default_factory=list, description="User email aliases for AddressedToMe detection")
    
    def __init__(self, **kwargs):
        # Читаем значения из переменных окружения если они не заданы
        env_values = {
            'endpoint': os.getenv('EWS_ENDPOINT', ''),
            'user_upn': os.getenv('EWS_USER_UPN', ''),
            'user_login': os.getenv('EWS_USER_LOGIN'),
            'user_domain': os.getenv('EWS_USER_DOMAIN'),
        }
        
        # Применяем значения из переменных окружения только если они не заданы явно
        for key, env_value in env_values.items():
            if key not in kwargs and env_value:
                kwargs[key] = env_value
                
        super().__init__(**kwargs)
    
    def get_password(self) -> str:
        """Get EWS password from environment.
        
        This method should be used when you have an EWSConfig instance directly.
        For Config instances, use Config.get_ews_password() instead.
        """
        password = os.getenv(self.password_env)
        if not password:
            raise ValueError(f"Environment variable {self.password_env} not set")
        return password
    
    def get_ntlm_username(self) -> str:
        """Get username for NTLM authentication (login@domain format)."""
        if self.user_login and self.user_domain:
            return f"{self.user_login}@{self.user_domain}"
        
        # Fallback: use user_upn if login/domain not specified
        if self.user_upn and '@' in self.user_upn:
            return self.user_upn
        
        raise ValueError("Cannot determine NTLM username: user_login and user_domain not set, and user_upn is invalid")


class LLMConfig(BaseModel):
    """LLM Gateway configuration."""
    endpoint: str = Field(default="", description="LLM Gateway endpoint")
    model: str = Field(default="Qwen/Qwen3-30B-A3B-Instruct-2507", description="Model identifier")
    timeout_s: int = Field(default=60, description="Request timeout in seconds")
    headers: Dict[str, str] = Field(default_factory=dict, description="Additional headers")
    max_tokens_per_run: int = Field(default=30000, description="Max tokens per run")
    cost_limit_per_run: float = Field(default=5.0, description="Cost limit per run in USD")
    
    def __init__(self, **kwargs):
        # Читаем значения из переменных окружения если они не заданы
        env_values = {
            'endpoint': os.getenv('LLM_ENDPOINT', ''),
        }
        
        # Применяем значения из переменных окружения только если они не заданы явно
        for key, env_value in env_values.items():
            if key not in kwargs and env_value:
                kwargs[key] = env_value
                
        super().__init__(**kwargs)
    
    def get_token(self) -> str:
        """Get LLM token from environment."""
        token = os.getenv("LLM_TOKEN")
        if not token:
            raise ValueError("Environment variable LLM_TOKEN not set")
        return token


class ObservabilityConfig(BaseModel):
    """Observability configuration."""
    prometheus_port: int = Field(default=9108, description="Prometheus metrics port")
    log_level: str = Field(default="INFO", description="Log level")


class SelectionBucketsConfig(BaseModel):
    """Configuration for balanced evidence selection buckets."""
    threads_top: int = Field(default=10, description="Minimum threads to cover (1 chunk each)")
    addressed_to_me: int = Field(default=8, description="Minimum chunks with AddressedToMe=true")
    dates_deadlines: int = Field(default=6, description="Minimum chunks with dates/deadlines")
    critical_senders: int = Field(default=4, description="Minimum chunks from sender_rank>=2")
    per_thread_max: int = Field(default=3, description="Maximum chunks per thread")
    max_total_chunks: int = Field(default=20, description="Maximum total chunks to select")


class SelectionWeightsConfig(BaseModel):
    """Feature weights for evidence chunk scoring."""
    recency: float = Field(default=2.0, description="Weight for message recency (hours)")
    addressed_to_me: float = Field(default=3.0, description="Weight for AddressedToMe flag")
    action_verbs: float = Field(default=1.5, description="Weight per action verb found")
    question_mark: float = Field(default=1.0, description="Weight for questions")
    dates_found: float = Field(default=1.5, description="Weight per date/deadline found")
    importance_high: float = Field(default=2.0, description="Weight for High importance")
    is_flagged: float = Field(default=1.5, description="Weight for flagged messages")
    has_doc_attachments: float = Field(default=1.0, description="Weight for doc/xlsx/pdf attachments")
    sender_rank: float = Field(default=1.0, description="Weight multiplier per sender rank level")
    thread_activity: float = Field(default=0.5, description="Weight for thread activity")
    negative_prior: float = Field(default=-2.0, description="Penalty for noreply/unsubscribe patterns")


class ContextBudgetConfig(BaseModel):
    """Configuration for context token budget."""
    max_total_tokens: int = Field(default=7000, description="Maximum total tokens for LLM input")
    per_thread_max: int = Field(default=3, description="Maximum chunks per thread")


class ChunkingConfig(BaseModel):
    """Configuration for message chunking."""
    long_email_tokens: int = Field(default=1000, description="Threshold for long email")
    max_chunks_if_long: int = Field(default=3, description="Max chunks for long emails")
    max_chunks_default: int = Field(default=12, description="Default max chunks per message")
    adaptive_high_load_emails: int = Field(default=200, description="Email count threshold for high load")
    adaptive_high_load_threads: int = Field(default=60, description="Thread count threshold for high load")
    adaptive_multiplier: float = Field(default=0.75, description="Multiplier for high load")


class ShrinkConfig(BaseModel):
    """Configuration for auto-shrink behavior."""
    enable_auto_shrink: bool = Field(default=True, description="Enable auto-shrink on overflow")
    preserve_min_quotas: bool = Field(default=True, description="Preserve minimum bucket quotas during shrink")


class HierarchicalConfig(BaseModel):
    """Configuration for hierarchical digest mode."""
    enable: bool = Field(default=True, description="Enable hierarchical mode")
    min_threads: int = Field(default=30, description="Min threads to activate")
    min_emails: int = Field(default=150, description="Min emails to activate")
    
    per_thread_max_chunks_in: int = Field(default=8, description="Max chunks per thread for summarization")
    summary_max_tokens: int = Field(default=90, description="Max tokens for thread summary")
    parallel_pool: int = Field(default=8, description="Max parallel thread summarization workers")
    timeout_sec: int = Field(default=20, description="Timeout per thread summarization")
    degrade_on_timeout: str = Field(default="best_2_chunks", description="Degradation strategy on timeout")
    
    final_input_token_cap: int = Field(default=4000, description="Max tokens for final aggregator input")
    max_latency_increase_pct: int = Field(default=50, description="Max acceptable latency increase %")
    target_latency_increase_pct: int = Field(default=30, description="Target latency increase %")
    max_cost_increase_per_email_pct: int = Field(default=40, description="Max acceptable cost increase per email %")


class Config(BaseSettings):
    """Main configuration class."""
    
    # Sub-configurations
    time: TimeConfig = Field(default_factory=TimeConfig)
    ews: EWSConfig = Field(default_factory=EWSConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    selection_buckets: SelectionBucketsConfig = Field(default_factory=SelectionBucketsConfig)
    selection_weights: SelectionWeightsConfig = Field(default_factory=SelectionWeightsConfig)
    context_budget: ContextBudgetConfig = Field(default_factory=ContextBudgetConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    shrink: ShrinkConfig = Field(default_factory=ShrinkConfig)
    hierarchical: HierarchicalConfig = Field(default_factory=HierarchicalConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        # First, load defaults
        super().__init__(**kwargs)
        
        # Then load from YAML files (in order of precedence)
        yaml_configs = self._load_yaml_configs()
        
        # Apply YAML configs (lower precedence first)
        for yaml_config in yaml_configs:
            self._apply_yaml_config(yaml_config)
    
    def _load_yaml_configs(self) -> List[Dict]:
        """Load YAML configuration files in order of precedence."""
        configs = []
        
        # 1. Load config.example.yaml (lowest precedence)
        example_path = Path("configs/config.example.yaml")
        if example_path.exists():
            try:
                with open(example_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config:
                        configs.append(config)
            except Exception as e:
                print(f"Warning: Failed to load {example_path}: {e}")
        
        # 2. Load config.yaml (higher precedence)
        user_path = Path("configs/config.yaml")
        if user_path.exists():
            try:
                with open(user_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config:
                        configs.append(config)
            except Exception as e:
                print(f"Warning: Failed to load {user_path}: {e}")
        
        # 3. Load from DIGEST_CONFIG_PATH (highest precedence)
        custom_path = os.getenv("DIGEST_CONFIG_PATH")
        if custom_path:
            custom_path = Path(custom_path)
            if custom_path.exists():
                try:
                    with open(custom_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        if config:
                            configs.append(config)
                except Exception as e:
                    print(f"Warning: Failed to load {custom_path}: {e}")
        
        return configs
    
    def _apply_yaml_config(self, yaml_config: Dict) -> None:
        """Apply YAML configuration to current config."""
        if 'time' in yaml_config:
            self.time = TimeConfig(**yaml_config['time'])
        if 'ews' in yaml_config:
            # Обновляем существующий объект EWSConfig, а не создаем новый
            for key, value in yaml_config['ews'].items():
                if hasattr(self.ews, key):
                    # Не перезаписываем значения из переменных окружения
                    if key in ['endpoint', 'user_upn', 'user_login', 'user_domain']:
                        # Проверяем, есть ли значение из переменной окружения
                        env_value = self._get_env_value_for_key(key)
                        if not env_value:  # Только если нет переменной окружения
                            setattr(self.ews, key, value)
                    else:
                        setattr(self.ews, key, value)
        if 'llm' in yaml_config:
            # Обновляем существующий объект LLMConfig, а не создаем новый
            for key, value in yaml_config['llm'].items():
                if hasattr(self.llm, key):
                    # Не перезаписываем значения из переменных окружения
                    if key == 'endpoint':
                        env_value = self._get_env_value_for_key('LLM_ENDPOINT')
                        if not env_value:  # Только если нет переменной окружения
                            setattr(self.llm, key, value)
                    else:
                        setattr(self.llm, key, value)
        if 'observability' in yaml_config:
            self.observability = ObservabilityConfig(**yaml_config['observability'])
        if 'selection_buckets' in yaml_config:
            self.selection_buckets = SelectionBucketsConfig(**yaml_config['selection_buckets'])
        if 'selection_weights' in yaml_config:
            self.selection_weights = SelectionWeightsConfig(**yaml_config['selection_weights'])
        if 'context_budget' in yaml_config:
            self.context_budget = ContextBudgetConfig(**yaml_config['context_budget'])
        if 'chunking' in yaml_config:
            self.chunking = ChunkingConfig(**yaml_config['chunking'])
        if 'shrink' in yaml_config:
            self.shrink = ShrinkConfig(**yaml_config['shrink'])
        if 'hierarchical' in yaml_config:
            self.hierarchical = HierarchicalConfig(**yaml_config['hierarchical'])
    
    def _get_env_value_for_key(self, key: str) -> str:
        """Get environment variable value for a given config key."""
        env_mapping = {
            'endpoint': 'EWS_ENDPOINT',
            'user_upn': 'EWS_USER_UPN',
            'user_login': 'EWS_USER_LOGIN',
            'user_domain': 'EWS_USER_DOMAIN',
        }
        env_var = env_mapping.get(key)
        if env_var:
            return os.getenv(env_var, '')
        return ''
    
    def get_ews_password(self) -> str:
        """Get EWS password from environment.
        
        This method delegates to the EWSConfig.get_password() method.
        Use this method when you have a Config instance.
        """
        return self.ews.get_password()
    
    def get_llm_token(self) -> str:
        """Get LLM token from environment."""
        return self.llm.get_token()
