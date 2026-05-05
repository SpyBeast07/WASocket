# WAHA Gateway

A minimal FastAPI backend acting as a lightweight gateway for [WAHA (WhatsApp HTTP API)](https://waha.dev/).

## Features

- **Send Messages**: Simple `POST /send` endpoint.
- **Webhook Routing**: Receives events from WAHA and forwards them to specific project endpoints based on an in-memory routing map.
- **Secure**: All endpoints protected by API key authentication.
- **Async**: Fire-and-forget webhook forwarding using FastAPI `BackgroundTasks`.
- **Cloudflare Ready**: Optimized for deployment behind Cloudflare Tunnels.

## Project Structure

```text
app/
  main.py           # Application entry point
  config.py         # Configuration and Routing Map
  routes/
    send.py         # Message sending routes
    webhook.py      # Webhook handling and routing
  services/
    waha_client.py  # WAHA API client
    router.py       # Forwarding logic
```

## Getting Started

### 1. Installation

```bash
# Clone the repository (if applicable)
# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
```

**Note on Routing:** Update the `ROUTING_MAP` in `app/config.py` to define where webhook events should be forwarded based on phone numbers or chat IDs.

### 3. Running the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Usage

### Send Message
**POST** `/send`
**Headers:** `x-api-key: your_internal_key`
**Body:**
```json
{
  "phone": "919XXXXXXXXX",
  "message": "Hello from Gateway!"
}
```

### Webhook
**POST** `/webhook`
Expects payloads from WAHA. Will automatically route events if a mapping exists in `config.py`.

## Security

- All incoming requests to `/send` must include the `x-api-key` header matching `INTERNAL_API_KEY`.
- The `/webhook` endpoint can optionally validate a secret token via header or query parameter if `WEBHOOK_SECRET_TOKEN` is set.
