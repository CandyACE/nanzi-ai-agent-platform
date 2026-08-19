from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class BrowserApprovalMode(str, Enum):
    GUARDED = "guarded"
    AUTOPILOT = "autopilot"


class BrowserSessionStatus(str, Enum):
    ACTIVE = "active"
    WAITING_USER = "waiting_user"
    DETACHED = "detached"
    CLOSED = "closed"
    CRASHED = "crashed"


class BrowserProfileResponse(BaseModel):
    id: str
    display_name: str
    status: str
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrowserSessionOpenRequest(BaseModel):
    url: str = Field(default="https://www.baidu.com/", min_length=1, max_length=2048)
    profile_id: Optional[str] = None
    conversation_id: Optional[str] = Field(default=None, max_length=64)


class BrowserPolicyUpdateRequest(BaseModel):
    approval_mode: BrowserApprovalMode


class BrowserSessionResponse(BaseModel):
    id: str
    profile_id: str
    attached_conversation_id: Optional[str] = None
    current_url: Optional[str] = None
    page_title: Optional[str] = None
    approval_mode: BrowserApprovalMode
    status: BrowserSessionStatus
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrowserViewerTokenResponse(BaseModel):
    session_id: str
    token: str
    expires_at: datetime


class BrowserElement(BaseModel):
    ref: str
    role: Optional[str] = None
    name: Optional[str] = None
    value: Optional[str] = None
    disabled: bool = False
    sensitive: bool = False


class BrowserSnapshot(BaseModel):
    session_id: str
    snapshot_id: str
    tab_id: Optional[str] = None
    url: str
    title: str
    screenshot_ref: Optional[str] = None
    elements: list[BrowserElement] = Field(default_factory=list)
    page_state: str = "ready"
    scroll_x: float = 0
    scroll_y: float = 0
    viewport_width: Optional[int] = None
    viewport_height: Optional[int] = None
    document_width: Optional[int] = None
    document_height: Optional[int] = None
    page_text: str = ""
    visible_text: str = ""


class BrowserTab(BaseModel):
    tab_id: str
    url: str
    title: str
    active: bool = False


class BrowserToolResult(BaseModel):
    session_id: str
    action: str
    url: Optional[str] = None
    title: Optional[str] = None
    snapshot_id: Optional[str] = None
    screenshot_ref: Optional[str] = None
    value: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)
