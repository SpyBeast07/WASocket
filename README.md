# 🚀 WAHA Gateway

A minimal, secure, and production-ready FastAPI gateway for **WAHA (WhatsApp HTTP API)**. Designed to act as a lightweight bridge between your projects and WhatsApp.

---

## ✨ Features

- **🔒 Secure API**: Protects your WhatsApp pipeline with `x-api-key` validation.
- **🛣️ Intelligent Routing**: Routes incoming webhooks to specific project endpoints based on Chat ID.
- **⚡ Async Performance**: Fire-and-forget webhook forwarding with sub-10ms overhead.
- **☁️ Cloudflare Ready**: Configured for 0.0.0.0:8000, perfect for Cloudflare Tunnels.
- **🛡️ Loop Prevention**: Automatically filters out messages sent from your own session.

---

## 🛠️ Tech Stack

- **FastAPI**: Modern, high-performance Python framework.
- **HTTPX**: Fully async HTTP client for fast forwarding.
- **Pydantic Settings**: Robust environment variable management.

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone <your-repo-url>
cd WASocket

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
Copy the example environment file and fill in your details:
```bash
cp .env.example .env
```

### 3. Define Routes
Edit `app/services/router.py` to add your project webhooks:
```python
ROUTING_MAP = {
    "919XXXXXXXXX": "https://project-a.com/webhook",
    "group-id": "https://project-b.com/webhook"
}
```

### 4. Run the Gateway
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📖 API Usage

### Send Message
**Endpoint:** `POST /send`  
**Header:** `x-api-key: your_secure_key`

```json
{
  "phone": "919XXXXXXXXX",
  "message": "Hello from WAHA Gateway!"
}
```

### Webhook Reception
**Endpoint:** `POST /webhook`  
Configure this URL in your WAHA dashboard. You can also set a secret token in `.env` for added security.

---

## 📂 Project Structure

```text
app/
├── main.py           # Application entry point
├── config.py         # Configuration management
├── routes/
│   ├── send.py       # Message sending endpoint
│   └── webhook.py    # Incoming webhook handler
└── services/
    ├── waha_client.py # WAHA API client
    └── router.py      # Webhook routing logic
```

---

## ⚖️ License
MIT License. Free to use and modify.
