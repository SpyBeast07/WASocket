const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const dotenv = require('dotenv');
const cors = require('cors');

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;
const sessionName = process.env.SESSION_NAME || 'wasocket_session';

app.use(cors());
app.use(express.json());

let client = null;
let connectionStatus = 'DISCONNECTED';
let qrCode = null;

// RELIABILITY & PERFORMANCE TRACKING
let lastSuccessfulSendTimestamp = 0;
let consecutiveFailureCount = 0;
const STALE_THRESHOLD_MS = 60000;

async function start() {
  try {
    client = await wppconnect.create({
      session: sessionName,
      autoClose: 0,
      whatsappVersion: '2.3000.1015901307',
      catchQR: (base64Qrimg, asciiQR, attempts, urlCode) => {
        qrCode = urlCode;
      },
      statusFind: (statusSession, session) => {
        connectionStatus = statusSession;
      },
      folderNameToken: 'tokens',
      headless: true,
      useChrome: true,
      debug: false,
      browserArgs: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });

    console.log('WhatsApp Client Initialized');
    setupClientEvents(client);
  } catch (error) {
    console.error('Error starting WPPConnect:', error);
    connectionStatus = 'ERROR';
  }
}

function setupClientEvents(client) {
  client.onStateChange((state) => {
    console.log('[Event] State changed: ', state);
    connectionStatus = state;
  });

  client.onStreamChange((state) => {
    if (state === 'DISCONNECTED' || state === 'SYNCING') {
        connectionStatus = state;
    }
  });

  // ASYNC ACK HANDLING (Non-blocking)
  client.onAck((ack) => {
    // Optionally log or store ACKs in Redis/DB for status tracking
    // This is separated from the send path to keep latency low
  });
}

async function triggerSoftRecovery() {
    if (client) {
        try {
            await client.close();
            client = null;
            connectionStatus = 'RECONNECTING';
            start();
        } catch (e) {}
    }
}

// API Endpoints

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'engine', failures: consecutiveFailureCount });
});

app.get('/status', async (req, res) => {
  let isConnected = connectionStatus === 'CONNECTED';
  res.json({ status: connectionStatus, connected: isConnected });
});

app.post('/send-message', async (req, res) => {
  const { phone, message, fireAndForget = true } = req.body;
  const now = Date.now();

  if (!phone || !message) return res.status(400).json({ error: 'Missing data' });

  // 1. WARM-UP & STALE CHECK
  let isConnectionStale = (now - lastSuccessfulSendTimestamp) > STALE_THRESHOLD_MS;
  if (isConnectionStale || connectionStatus !== 'CONNECTED') {
    const isActuallyConnected = client ? await client.isConnected().catch(() => false) : false;
    if (!isActuallyConnected) {
      connectionStatus = 'DISCONNECTED';
      return res.status(401).json({ error: 'Client not connected' });
    }
    connectionStatus = 'CONNECTED';
  }

  const formattedPhone = phone.includes('@c.us') ? phone : `${phone}@c.us`;

  // 2. FIRE-AND-FORGET EXECUTION (ULTRA-LOW LATENCY)
  if (fireAndForget) {
    // We initiate the send and return 202 ACCEPTED immediately
    client.sendText(formattedPhone, message)
      .then(() => {
        lastSuccessfulSendTimestamp = Date.now();
        consecutiveFailureCount = 0;
      })
      .catch((err) => {
        consecutiveFailureCount++;
        console.error('[Async Error] Send failed:', err.message);
        if (consecutiveFailureCount >= 3) triggerSoftRecovery();
      });

    return res.status(202).json({ success: true, mode: 'fire-and-forget' });
  }

  // Standard Blocking Path (for when user NEEDS result object)
  try {
    const result = await client.sendText(formattedPhone, message);
    lastSuccessfulSendTimestamp = Date.now();
    consecutiveFailureCount = 0;
    res.json({ success: true, result });
  } catch (error) {
    consecutiveFailureCount++;
    if (consecutiveFailureCount >= 3) triggerSoftRecovery();
    res.status(500).json({ error: error.message });
  }
});

setInterval(async () => {
  if (client && connectionStatus === 'CONNECTED') {
    const isActuallyConnected = await client.isConnected().catch(() => false);
    if (!isActuallyConnected) connectionStatus = 'DISCONNECTED';
  }
}, 30000);

app.listen(port, () => {
  console.log(`Engine listening at http://localhost:${port}`);
  start();
});
