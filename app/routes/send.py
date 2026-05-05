from fastapi import APIRouter, Header, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from app.config import settings
from app.services.waha_client import waha_client

router = APIRouter()

api_key_header = APIKeyHeader(name="x-api-key", auto_error=True)

async def validate_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

class SendRequest(BaseModel):
    phone: str
    message: str

@router.post("/send")
async def send_message(request: SendRequest, _ = Depends(validate_api_key)):
    try:
        response = await waha_client.send_text(request.phone, request.message)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
