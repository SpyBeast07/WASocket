import logging
from fastapi import FastAPI
from app.routes import send, webhook

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WAHA Gateway",
    description="Minimal FastAPI gateway for WhatsApp HTTP API (WAHA)",
    version="1.0.0"
)

# Include routers
app.include_router(send.router, tags=["Sending"])
app.include_router(webhook.router, tags=["Webhooks"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # Run on 0.0.0.0:8000 for Cloudflare Tunnel compatibility
    uvicorn.run(app, host="0.0.0.0", port=8000)
