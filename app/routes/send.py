from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from app.config import settings
from app.services.waha_client import waha_client

router = APIRouter()

class SendRequest(BaseModel):
    phone: str
    message: str

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_api_key

@router.post("/send", dependencies=[Depends(verify_api_key)])
async def send_message(request: SendRequest):
    try:
        result = await waha_client.send_text(request.phone, request.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
