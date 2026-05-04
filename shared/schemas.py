from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class MessageRequest(BaseModel):
    phone: str = Field(..., description="Phone number with country code")
    message: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = None

class ConnectionStatus(BaseModel):
    connected: bool
    session_name: str
    qr_code: Optional[str] = None
