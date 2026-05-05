import time
import logging
import httpx
import asyncio
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from shared.schemas import MessageRequest
from api.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="WASocket API")

# Security
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return api_key

http_client = None

@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info(f"API Started | Engine URL: {settings.engine_url}")

@app.on_event("shutdown")
async def shutdown():
    if http_client:
        await http_client.aclose()

# Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"Method: {request.method} Path: {request.url.path} "
        f"Status: {response.status_code} Duration: {duration:.4f}s"
    )
    return response

@app.get("/health")
async def health_check():
    health = {
        "status": "ok",
        "timestamp": time.time(),
        "services": {
            "api": "CONNECTED",
            "engine": "UNKNOWN"
        }
    }

    # Check Engine
    try:
        resp = await http_client.get(f"{settings.engine_url}/health")
        if resp.status_code == 200:
            engine_data = resp.json()
            health["services"]["engine"] = "CONNECTED" if engine_data.get("ready") else "INITIALIZING"
        else:
            health["services"]["engine"] = "ERROR"
    except Exception:
        health["services"]["engine"] = "DISCONNECTED"

    # Overall Status
    if health["services"]["engine"] in ["DISCONNECTED", "ERROR"]:
        health["status"] = "degraded"
    
    return health

@app.post("/send", dependencies=[Depends(get_api_key)])
async def send_message(payload: MessageRequest):
    start_time = time.time()
    
    # 1. Basic Rate Delay (Optional light pacing)
    await asyncio.sleep(0.3) 

    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            # Check engine status before sending
            # Note: Engine's /send-message already checks readiness, but we can be proactive if needed.
            # However, the user said "Do NOT add heavy checks per request".
            
            resp = await http_client.post(
                f"{settings.engine_url}/send-message",
                json={"phone": payload.phone, "message": payload.message},
                timeout=25.0
            )
            
            if resp.status_code == 200:
                result = resp.json()
                dispatch_duration = time.time() - start_time
                return {
                    "success": True,
                    "message_id": result.get("messageId"),
                    "latency_ms": round(dispatch_duration * 1000, 2),
                    "attempts": attempt + 1
                }
            
            # If 503 (initializing), we might want to wait longer or retry
            if resp.status_code == 503:
                last_error = "Engine initializing"
                logger.warning(f"Attempt {attempt + 1}: Engine initializing. Retrying...")
            else:
                last_error = f"Engine error: {resp.text}"
                logger.error(f"Attempt {attempt + 1}: Engine error {resp.status_code}: {resp.text}")

        except (httpx.RequestError, asyncio.TimeoutError) as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt + 1}: Transport error: {e}")

        if attempt < max_retries:
            await asyncio.sleep(1.0) # Simple backoff

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to send message after {max_retries + 1} attempts. Last error: {last_error}"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
