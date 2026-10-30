from datetime import datetime

from pydantic import BaseModel


class LLMConfigOut(BaseModel):
    """全局模型配置的对外视图：只返回掩码，绝不返回明文 Key。"""

    provider: str
    base_url: str
    model: str

    api_key_masked: str
    api_key_configured: bool

    vision_model: str
    vision_base_url: str
    vision_api_key_masked: str
    vision_api_key_configured: bool

    # db=数据库中的配置；env=环境变量兜底（页面尚未保存过）
    source: str
    status: str
    status_message: str
    checked_at: datetime | None = None

    updated_at: datetime | None = None
    updated_by: int = 0
    can_edit: bool = False


class LLMConfigUpdate(BaseModel):
    """保存配置的入参。

    api_key / vision_api_key 不传（或传 null）表示保持原值，传空字符串表示清除。
    """

    provider: str = "openai"
    base_url: str
    model: str
    api_key: str | None = None

    vision_model: str | None = None
    vision_base_url: str | None = None
    vision_api_key: str | None = None


class LLMProbeOut(BaseModel):
    status: str
    message: str
    latency_ms: int
    checked_at: datetime
    config: LLMConfigOut
