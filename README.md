# WASocket

A high-performance, containerized WhatsApp API gateway built with FastAPI, Node.js (WPPConnect), and Redis.

## 🧠 Architecture

```text
Public Traffic (HTTPS/8083)
    ↓
Caddy (Reverse Proxy)
    ↓
FastAPI (Security + Logic)
    ↓
Redis (Reliable Queue)
    ↓
Python Worker (Smart Retry + Rate Limiting)
    ↓
Node Engine (WPPConnect / Chromium)
    ↓
WhatsApp WebSocket
```

## ✨ Key Features

- **Docker-First**: One-command deployment with `docker-compose`.
- **High Reliability**: Automatic session recovery and smart worker retries.
- **Secure**: Protected by API Key (`x-api-key` header).
- **Observable**: Centralized health monitoring and structured logging.
- **Persistent**: WhatsApp sessions are preserved across restarts.

## 🚀 Quick Start

### 1. Configure
Copy the environment template and set your secret API key:
```bash
cp .env.example .env
# Edit .env and set your API_KEY
```

### 2. Deploy
Start the entire stack using Docker Compose:
```bash
docker-compose up -d --build
```

### 3. Authenticate
View the logs to scan the WhatsApp QR code:
```bash
docker-compose logs -f engine
```
*Scan the generated QR code with your phone.*

## 🔒 Security
All API requests must include the following header:
`x-api-key: your-secret-key`

## 📡 API Endpoints

### Send Message
`POST /send`
```json
{
  "phone": "919999999999",
  "message": "Hello from WASocket!",
  "priority": "high"
}
```

### System Health
`GET /health`
Returns the status of the API, Worker, Engine, and Queue lengths.

## 🛠️ Components

- `api/`: FastAPI gateway.
- `worker/`: Background job processor with rate limiting.
- `engine/`: Node.js WhatsApp engine (WPPConnect).
- `infra/`: Caddy reverse proxy configuration.
- `shared/`: Common schemas and models.

## ⚙️ Configuration (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Secret key for API access | `wasocket-secret-key` |
| `SESSION_NAME` | WhatsApp session identifier | `wasocket_session` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` |
| `ENGINE_URL` | Engine connection string | `http://engine:3000` |

## ⚠️ Important Notes
- **Rate Limiting**: Default is set to 60 messages per minute to prevent account flagging.
- **Session Persistence**: Sessions are stored in the `engine-tokens` Docker volume.
- **Headless Mode**: The engine runs Chromium in headless mode within the container.
