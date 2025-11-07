from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "HEX-LoadBench"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite:///./hex_loadbench.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Authentication
    JWT_SECRET: str = "your-super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    API_KEY_HEADER: str = "X-API-Key"
    
    # Load Testing
    K6_BINARY: str = "/usr/bin/k6"
    DEFAULT_TEST_TIMEOUT: int = 300
    MAX_RPS_PER_TEST: int = 10000
    MAX_CONCURRENT_USERS_PER_TEST: int = 1000
    DEFAULT_REGION: str = "us-east-1"
    ALLOWED_REGIONS: List[str] = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
    
    # Safety Limits
    GLOBAL_DAILY_RPS_CAP: int = 10000000
    EMERGENCY_KILL_SWITCH: bool = False
    RATE_LIMIT_PER_IP: int = 1000
    ALLOWED_TARGET_DOMAINS: List[str] = []  # Empty = allow all
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # File Upload
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "uploads"
    ALLOWED_FILE_TYPES: List[str] = ["application/pdf", "text/plain", "application/json"]
    
    # Email
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@hexloadbench.com"
    
    # Notifications
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_DEFAULT_CHAT_ID: str = ""
    SLACK_WEBHOOK_URL: str = ""
    SLACK_DEFAULT_CHANNEL: str = "#load-testing"
    
    # Security
    REQUIRE_AUTH_DOCUMENT: bool = True
    PASSWORD_MIN_LENGTH: int = 8
    SESSION_TIMEOUT_MINUTES: int = 30
    
    # Audit & Compliance
    AUDIT_LOG_RETENTION_DAYS: int = 365
    IMMUTABLE_AUDIT_LOGS: bool = True
    GDPR_COMPLIANCE: bool = True
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    RATE_LIMIT_REQUESTS_PER_DAY: int = 10000
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"
    HEALTH_CHECK_PATH: str = "/health"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    LOG_FILE: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Load configuration from YAML file if available
def load_config_from_yaml(config_path: str = "config/config.yaml"):
    """Load configuration from YAML file."""
    try:
        import yaml
        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
                
                # Update settings with YAML config
                if 'database' in config:
                    settings.DATABASE_URL = config['database'].get('connection', settings.DATABASE_URL)
                
                if 'api_server' in config:
                    api_config = config['api_server']
                    settings.API_HOST = api_config.get('host', settings.API_HOST)
                    settings.API_PORT = api_config.get('port', settings.API_PORT)
                    settings.CORS_ORIGINS = api_config.get('cors_origins', settings.CORS_ORIGINS)
                
                if 'load_testing' in config:
                    lt_config = config['load_testing']
                    settings.MAX_RPS_PER_TEST = lt_config.get('max_rps_per_test', settings.MAX_RPS_PER_TEST)
                    settings.MAX_CONCURRENT_USERS_PER_TEST = lt_config.get('max_concurrent_users_per_test', settings.MAX_CONCURRENT_USERS_PER_TEST)
                    settings.ALLOWED_REGIONS = lt_config.get('regions', settings.ALLOWED_REGIONS)
                
                if 'safety' in config:
                    safety_config = config['safety']
                    settings.GLOBAL_DAILY_RPS_CAP = safety_config.get('global_daily_rps_cap', settings.GLOBAL_DAILY_RPS_CAP)
                    settings.EMERGENCY_KILL_SWITCH = safety_config.get('emergency_kill_switch', settings.EMERGENCY_KILL_SWITCH)
                
                if 'notifications' in config:
                    notif_config = config['notifications']
                    if 'telegram' in notif_config:
                        settings.TELEGRAM_BOT_TOKEN = notif_config['telegram'].get('bot_token', settings.TELEGRAM_BOT_TOKEN)
                        settings.TELEGRAM_DEFAULT_CHAT_ID = notif_config['telegram'].get('default_chat_id', settings.TELEGRAM_DEFAULT_CHAT_ID)
                    if 'slack' in notif_config:
                        settings.SLACK_WEBHOOK_URL = notif_config['slack'].get('webhook_url', settings.SLACK_WEBHOOK_URL)
                        settings.SLACK_DEFAULT_CHANNEL = notif_config['slack'].get('default_channel', settings.SLACK_DEFAULT_CHANNEL)
                    if 'email' in notif_config:
                        email_config = notif_config['email']
                        settings.SMTP_SERVER = email_config.get('smtp_server', settings.SMTP_SERVER)
                        settings.SMTP_PORT = email_config.get('smtp_port', settings.SMTP_PORT)
                        settings.SMTP_USERNAME = email_config.get('username', settings.SMTP_USERNAME)
                        settings.SMTP_PASSWORD = email_config.get('password', settings.SMTP_PASSWORD)
                        
                return True
    except Exception as e:
        print(f"Error loading YAML config: {e}")
        return False
    
    return False

# Load configuration on import
load_config_from_yaml()