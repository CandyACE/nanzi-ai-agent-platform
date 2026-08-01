from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional
from datetime import datetime
from pydantic import field_validator

ModelProvider = Literal[
    "openai",
    "azure",
    "deepseek",
    "kimi",
    "zhipu",
    "siliconflow",
    "dashscope",
    "ollama",
    "other",
]
ModelType = Literal["llm", "embedding", "multimodal"]


def _strip_required_text(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be blank")
    return normalized

class AIModelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Display Name")
    model_id: str = Field(..., min_length=1, max_length=255, description="Actual Model ID for API")
    provider: ModelProvider = Field(..., description="OpenAI-compatible provider")
    type: ModelType = Field(..., description="Type: llm, embedding, multimodal")
    api_base_url: Optional[str] = None
    context_size: Optional[int] = Field(
        default=None,
        gt=0,
        le=10_000_000,
        description="Model context window in tokens",
    )
    max_output_tokens: Optional[int] = Field(
        default=None,
        gt=0,
        le=10_000_000,
        description="Maximum output tokens per request",
    )
    is_active: bool = True

    @field_validator("name", "model_id")
    @classmethod
    def normalize_text(cls, value: str, info):
        return _strip_required_text(value, info.field_name)

class AIModelCreate(AIModelBase):
    api_key: Optional[str] = None

class AIModelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    model_id: Optional[str] = Field(default=None, min_length=1, max_length=255)
    provider: Optional[ModelProvider] = None
    type: Optional[ModelType] = None
    api_base_url: Optional[str] = None
    context_size: Optional[int] = Field(default=None, gt=0, le=10_000_000)
    max_output_tokens: Optional[int] = Field(default=None, gt=0, le=10_000_000)
    api_key: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name", "model_id")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str], info):
        if value is None:
            return value
        return _strip_required_text(value, info.field_name)


class AIModelDiscoverRequest(BaseModel):
    provider: ModelProvider
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_config_id: Optional[str] = None


class AIModelTestRequest(BaseModel):
    provider: ModelProvider
    type: ModelType
    model_id: str = Field(..., min_length=1, max_length=255)
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    context_size: Optional[int] = Field(default=None, gt=0, le=10_000_000)
    max_output_tokens: Optional[int] = Field(default=None, gt=0, le=10_000_000)
    model_config_id: Optional[str] = None

    @field_validator("model_id")
    @classmethod
    def normalize_model_id(cls, value: str):
        return _strip_required_text(value, "model_id")


class AIModelOption(BaseModel):
    model_id: str
    name: str

class AIModelResponse(AIModelBase):
    id: str
    created_at: datetime
    updated_at: datetime
    # Existing deployments may contain legacy provider/type values that are
    # still readable. Create/update requests remain strictly validated above.
    provider: str
    type: str
    # We do NOT return the full api_key for security
    has_api_key: bool = False

    model_config = ConfigDict(from_attributes=True)

    @staticmethod
    def from_orm_custom(obj):
        """Custom converter to handle masked API key logic"""
        data = AIModelResponse.model_validate(obj)
        data.has_api_key = bool(obj.api_key)
        # Ensure API key is never leaked in the default response if Pydantic included it
        # (Though it is not in AIModelBase, better safe)
        return data
