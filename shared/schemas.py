import re
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any

class MessagePriority(str, Enum):
    HIGH = "high"
    DEFAULT = "default"

class MessageRequest(BaseModel):
    phone: str = Field(..., description="Phone number with country code")
    message: str = Field(..., description="Message content", min_length=1)
    priority: MessagePriority = Field(default=MessagePriority.DEFAULT)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean_number = re.sub(r"\D", "", v)
        if not (10 <= len(clean_number) <= 15):
            raise ValueError("Phone number must be between 10 and 15 digits including country code")
        return clean_number

class ConnectionStatus(BaseModel):
    connected: bool
    session_name: str
    qr_code: Optional[str] = None
