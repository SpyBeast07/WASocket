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
let isReconnecting = false;
let lastConnectionTimestamp = 0;
const STALE_THRESHOLD_MS = 60000;

function logEvent(event, details = {}) {
  const timestamp = new Date().toISOString();
  console.log(JSON.stringify({ timestamp, event, ...details }));
}

async function start() {
  try {
    client = await wppconnect.create({
      session: sessionName,
      autoClose: false, // Disable auto-close entirely
      disableWelcome: true,
      waitForLogin: true,
      catchQR: (base64Qrimg, asciiQR, attempts, urlCode) => {
        qrCode = urlCode;
        console.log(`\n--- SCAN THIS QR CODE (Attempt ${attempts}) ---\n`);
        console.log(asciiQR);
        console.log(`\n--------------------------------------------\n`);
      },
      statusFind: (statusSession, session) => {
        logEvent('STATUS_FIND', { status: statusSession });
        connectionStatus = statusSession;
        
        // Trigger recovery if browser closes or session is lost
        if (['browserClose', 'autocloseCalled', 'serverClose'].includes(statusSession)) {
          connectionStatus = 'DISCONNECTED';
          if (!isReconnecting) triggerSoftRecovery();
        }
      },
      folderNameToken: 'tokens',
      headless: true,
      useChrome: false,
      debug: false,
      logQR: true,
      browserArgs: [
        '--no-sandbox', 
        '--disable-setuid-sandbox', 
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu'
      ],
      puppeteerOptions: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
      }
    });

    console.log('WhatsApp Client Initialized');
    lastConnectionTimestamp = Date.now();
    setupClientEvents(client);
  } catch (error) {
    console.error('Error starting WPPConnect:', error);
    connectionStatus = 'ERROR';
  }
}

function setupClientEvents(client) {
  client.onStateChange((state) => {
    logEvent('CONNECTION_STATE_CHANGE', { state });
    
    // Map states
    if (['CONNECTED', 'PAIRING', 'OPENING'].includes(state)) {
      connectionStatus = 'CONNECTED';
    } else if (['CONFLICT', 'UNPAIRED', 'UNLAUNCHED', 'UNINITIALIZED'].includes(state)) {
      connectionStatus = 'AUTH_REQUIRED';
      
      // If we are explicitly UNPAIRED, we should restart to ensure a fresh QR is generated
      if (state === 'UNPAIRED' && !isReconnecting) {
        logEvent('RECOVERY_TRIGGERED', { reason: 'State changed to UNPAIRED (Logout detected)' });
        triggerSoftRecovery();
      }
    } else {
      connectionStatus = 'DISCONNECTED';
    }

    // Auto-recovery for fatal disconnections
    if (connectionStatus === 'DISCONNECTED' && !isReconnecting) {
      logEvent('RECOVERY_TRIGGERED', { reason: `State changed to ${state}` });
      triggerSoftRecovery();
    }
  });

  client.onInterfaceChange((info) => {
    logEvent('INTERFACE_CHANGE', { ...info });
    if (info.mode === 'QR' || info.info === 'QR') {
      connectionStatus = 'AUTH_REQUIRED';
    }
  });

  client.onStreamChange((state) => {
    logEvent('STREAM_STATE_CHANGE', { state });
    // WPPConnect handles stream reconnection internally. 
    // We only update status if it's connected.
    if (state === 'CONNECTED') {
      connectionStatus = 'CONNECTED';
    }
  });

  client.onAck((ack) => {
    // Separation of concerns: ACKs handled asynchronously
  });
}

async function triggerSoftRecovery() {
    if (isReconnecting) return;
    isReconnecting = true;
    
    logEvent('RECOVERY_START', { session: sessionName });
    
    try {
        if (client) {
          await client.close().catch(() => {});
          client = null;
        }
        connectionStatus = 'RECONNECTING';
        
        // Wait 5 seconds before retrying to avoid tight loops
        await new Promise(resolve => setTimeout(resolve, 5000));
        await start();
    } catch (e) {
        logEvent('RECOVERY_FAILED', { error: e.message });
    } finally {
        isReconnecting = false;
        logEvent('RECOVERY_END');
    }
}

// API Endpoints

app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    service: 'engine', 
    engine_status: connectionStatus,
    failures: consecutiveFailureCount 
  });
});

app.get('/status', async (req, res) => {
  res.json({ 
    status: connectionStatus, 
    connected: connectionStatus === 'CONNECTED',
    qr_code: connectionStatus === 'AUTH_REQUIRED' ? qrCode : null
  });
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

  if (fireAndForget) {
    client.sendText(formattedPhone, message)
      .then(() => { lastSuccessfulSendTimestamp = Date.now(); })
      .catch((err) => { console.error('[Async Error] Send attempt:', err.message); });

    return res.status(202).json({ success: true, mode: 'fire-and-forget' });
  }

  // Standard Path
  try {
    client.sendText(formattedPhone, message).catch(e => console.error('Send error:', e.message));
    lastSuccessfulSendTimestamp = Date.now();
    res.json({ success: true, note: 'Message dispatched' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

setInterval(async () => {
  if (client && connectionStatus === 'CONNECTED') {
    const isActuallyConnected = await client.isConnected().catch(() => false);
    if (!isActuallyConnected) {
      logEvent('HEALTH_CHECK_FAILED', { reason: 'client.isConnected() returned false' });
      connectionStatus = 'DISCONNECTED';
      triggerSoftRecovery();
    }
  }
}, 30000);

app.listen(port, '0.0.0.0', () => {
  console.log(`Engine listening at http://0.0.0.0:${port}`);
  start();
});
