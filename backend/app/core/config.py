from pydantic_settings import BaseSettings, SettingsConfigDict

# 空值，以及历史示例/模板中出现过的密钥，一律视为不可用：
# 这些字符串已随示例文件公开，用它们签名等同于没有签名保护。
_INSECURE_JWT_SECRETS = {
    "",
    "dev-secret-change-me",
    "change-me-to-a-random-long-string",
    "secret",
    "changeme",
}
_MIN_JWT_SECRET_LENGTH = 16


class Settings(BaseSettings):
    # env_ignore_empty：空值一律回退到字段默认值。
    # .env / compose env_file 里常见的 `DATABASE_URL=` 这种「留空」写法，
    # 若被当作真实值传入，create_engine("") 会直接抛 Could not parse SQLAlchemy URL。
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    app_name: str = "CBEC Agent"
    # 本地开发默认 SQLite；生产通过 DATABASE_URL 指向 PostgreSQL
    database_url: str = "sqlite:///./cbec.db"

    # JWT 签名密钥：不给出可用的默认值，必须由部署环境显式注入，
    # 避免带着示例密钥的配置被直接部署上线（启动自检见 validate_security）
    jwt_secret: str = ""
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

    def validate_security(self) -> None:
        """启动自检：拒绝空、示例或过短的 JWT 密钥。

        密钥若保持示例值，任何拿到源码的人都能自行签发 token 冒充管理员，
        因此在服务启动阶段直接失败，而不是留到线上被利用。
        """
        secret = self.jwt_secret.strip()
        if secret in _INSECURE_JWT_SECRETS:
            raise RuntimeError(
                "JWT_SECRET 未配置或仍为示例值：请设置为足够长的随机字符串后重启"
                "（生成方式与说明见 .env.example）"
            )
        if len(secret) < _MIN_JWT_SECRET_LENGTH:
            raise RuntimeError(
                f"JWT_SECRET 过短（当前 {len(secret)} 位，至少需 {_MIN_JWT_SECRET_LENGTH} 位）："
                "请改用随机长字符串后重启"
            )


settings = Settings()
