import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List, Optional
from sqlalchemy.engine.url import URL

class Settings(BaseSettings):
    API_SERVICE_ENV: str = "dev"
    API_SERVICE_PORT: int = 8001
    LOG_LEVEL: str = "INFO"  # Aligned with .env
    ALLOWED_ORIGINS: List[str] = ["*"]
    APP_PUBLIC_URL: Optional[str] = None

    # MySQL
    MYSQL_HOST: str
    MYSQL_PORT: int = 3306
    MYSQL_DB: str
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_POOL_SIZE: int = 20
    MYSQL_MAX_OVERFLOW: int = 50
    MYSQL_POOL_RECYCLE: int = 3600

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None  # 改为 Optional 且默认为 None
    REDIS_ENABLE: bool = True

    # Security - API Key Encryption
    # Fernet Key (32 url-safe base64-encoded bytes)
    ENCRYPTION_KEY: str

    # LLM Gateway
    LLM_BASE_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: Optional[str] = None
    LLM_TEMPERATURE: Optional[float] = None

    # External SQL API
    EXTERNAL_SQL_API_URL: Optional[str] = None
    EXTERNAL_SQL_API_KEY: Optional[str] = None

    # Metadata & RAG
    METADATA_PROVIDER: str = "local" # local / ragflow
    RAGFLOW_API_URL: Optional[str] = None
    RAGFLOW_API_KEY: Optional[str] = None

    # Ebbinghaus Memory Configs
    MEMORY_BASE_HALF_LIFE: float = 7.0
    MEMORY_CONSOLIDATION_THRESHOLD: float = 0.82

    # SSO Configuration
    SSO_API_URL: str = "https://yovole.net/api/v1/user/check/login"
    SSO_ACCESS_TOKEN: str = "laplace"
    SSO_REQUEST_SYSTEM: str = "NANZI_AI_AGENT_PLATFORM"
    SSO_REQUEST_BUSINESS: str = "USER-LOGIN"
    SSO_TIMEOUT: int = 30

    @property
    def SKILLS_DIR(self) -> str:
        container_path = "/app/data/skills"
        if os.path.exists(container_path):
            return container_path
        host_path = os.path.expanduser("~/.agents/skills")
        os.makedirs(host_path, exist_ok=True)
        return host_path

    def build_mysql_url(self, driver: str = "mysql+aiomysql") -> URL:
        """构建 SQLAlchemy MySQL URL（自动对 user/password 中的 @:#/ 等特殊字符做编码）。"""
        return URL.create(
            drivername=driver,
            username=self.MYSQL_USER,
            password=self.MYSQL_PASSWORD,
            host=self.MYSQL_HOST,
            port=self.MYSQL_PORT,
            database=self.MYSQL_DB,
        )

    @property
    def MYSQL_ASYNC_URL(self) -> URL:
        return self.build_mysql_url("mysql+aiomysql")

    @property
    def MYSQL_SYNC_URL(self) -> str:
        # APScheduler 等同步组件需要字符串 URL；render 时保留已编码的密码
        return self.build_mysql_url("mysql+pymysql").render_as_string(hide_password=False)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
