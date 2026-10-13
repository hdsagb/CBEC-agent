from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CBEC Agent"
    # 本地开发默认 SQLite；生产通过 DATABASE_URL 指向 PostgreSQL
    database_url: str = "sqlite:///./cbec.db"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # LLM 适配层
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 多模态（图片报价单识别）：llm_vision_model 留空表示不启用，
    # 图片解析回退到本地 OCR。base_url / api_key 留空时复用 DeepSeek 配置。
    llm_vision_model: str = ""
    llm_vision_base_url: str = ""
    llm_vision_api_key: str = ""

    # 本地 OCR 兜底（RapidOCR）：依赖缺失时自动跳过
    ocr_enabled: bool = True

    # 上传文件存储目录
    upload_dir: str = "./uploads"


settings = Settings()
