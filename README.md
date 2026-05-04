# WASocket

A thin REST API wrapper over a single WhatsApp Web session.

## 🧠 Architecture

```text
FastAPI (API layer)
    ↓
Redis (queue + state)
    ↓
Worker (Python async)
    ↓
Node Engine (WPPConnect)
    ↓
WhatsApp WebSocket
```

## 🧱 Folders

- `api/`: FastAPI application.
- `worker/`: Python async worker for queue processing.
- `engine/`: Node.js WPPConnect engine (Isolated service).
- `infra/`: Redis configurations and infrastructure settings.
- `shared/`: Shared Pydantic schemas and models.

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- Node.js v18+
- Redis (running locally or via Docker)
- pnpm (recommended for Node)

### 2. Setup
1. **Infrastructure**:
   ```bash
   cd infra
   docker-compose up -d
   ```
2. **Node Engine**:
   ```bash
   cd engine
   pnpm install
   cp .env.example .env # Update if necessary
   pnpm start
   ```
   *Scan the QR code printed in the terminal.*

3. **Python API & Worker**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   # Start API
   uvicorn api.main:app --reload
   # Start Worker (in another terminal)
   python worker/main.py
   ```

## 🛠️ Internal API (Engine)
- `GET /status`: Connection and QR code status.
- `GET /session`: Logged-in device info.
- `POST /send-message`: Send a text message.

## ⚠️ Important Notes
- The engine uses a protocol-based communication (headless).
- All communications from the API to WhatsApp are queued via Redis.
- Session is persisted in `engine/tokens/`.
