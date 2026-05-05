import logging
from fastapi import FastAPI
from app.routes import send, webhook

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="WAHA Gateway")

# Include routes
app.include_router(send.router, tags=["Sending"])
app.include_router(webhook.router, tags=["Webhooks"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
