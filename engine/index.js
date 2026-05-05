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
const STALE_THRESHOLD_MS = 300000; // 5 minutes instead of 1

function logEvent(event, details = {}) {
  const timestamp = new Date().toISOString();
  console.log(JSON.stringify({ timestamp, event, ...details }));
}

async function start() {
  try {
    client = await wppconnect.create({
      session: sessionName,
      whatsappVersion: undefined, // Let latest wppconnect handle it
      autoClose: 3600000,
      waitForLogin: false,
      tokenStore: 'file',
      disableWelcome: true,
      catchQR: (base64Qrimg, asciiQR, attempts, urlCode) => {
        qrCode = urlCode;
        logEvent('QR_RECEIVED', { attempt: attempts });
        console.log(`\n--- SCAN THIS QR CODE (Attempt ${attempts}) ---\n`);
        console.log(asciiQR);
        console.log(`\n--------------------------------------------\n`);
      },
      statusFind: (statusSession, session) => {
        logEvent('STATUS_FIND', { status: statusSession });
        if (['browserClose', 'autocloseCalled', 'desconnectedMobile'].includes(statusSession)) {
            connectionStatus = 'DISCONNECTED';
        } else if (statusSession === 'isLogged' || statusSession === 'qrReadSuccess') {
            connectionStatus = 'CONNECTED';
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
        '--disable-gpu',
        '--hide-scrollbars',
        '--disable-notifications',
        '--disable-extensions',
        '--disable-infobars',
        '--disable-renderer-backgrounding',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-ipc-flooding-protection',
        '--disable-breakpad',
        '--disable-ipv6',
        '--dns-prefetch-disable',
        '--remote-debugging-port=9222',
        '--window-size=1280,720',
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
      ],
      puppeteerOptions: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
        protocolTimeout: 60000, // Increase to 60s for VPS stability
        args: [
          '--no-sandbox', 
          '--disable-setuid-sandbox', 
          '--disable-dev-shm-usage', 
          '--remote-debugging-port=9222',
          '--disable-setuid-sandbox',
          '--disable-web-security',
          '--disable-features=IsolateOrigins,site-per-process'
        ],
      }
    });

    console.log('WhatsApp Client Initialized');
    
    // Explicitly disable autoclose again after initialization
    if (client && typeof client.setAutoClose === 'function') {
        try {
            await client.setAutoClose(false); 
            console.log('Successfully setAutoClose(false)');
        } catch (e) {
            console.log('Could not setAutoClose(false) via method:', e.message);
        }
    }

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
    
    // Update status based on state
    if (['CONNECTED', 'PAIRING', 'OPENING', 'SYNCING'].includes(state)) {
      connectionStatus = 'CONNECTED';
    } else if (['CONFLICT', 'UNPAIRED', 'UNLAUNCHED', 'UNINITIALIZED'].includes(state)) {
      connectionStatus = 'AUTH_REQUIRED';
    } else if (state === 'DISCONNECTED') {
      // Don't trigger recovery immediately from events, let the interval handle it
      // as events can be noisy during transitions.
      connectionStatus = 'DISCONNECTED';
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
          logEvent('CLOSING_OLD_CLIENT');
          // Add a timeout to close() so it doesn't hang the recovery process
          await Promise.race([
            client.close(),
            new Promise((_, reject) => setTimeout(() => reject(new Error('Close timeout')), 10000))
          ]).catch(e => logEvent('CLOSE_ERROR', { error: e.message }));
          client = null;
        }
        connectionStatus = 'RECONNECTING';
        
        // Wait 5 seconds before retrying
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
app.get('/screenshot', async (req, res) => {
    if (!client || !client.page) return res.status(404).json({ error: 'Browser not active' });
    try {
        const screenshot = await client.page.screenshot({ type: 'png', fullPage: true });
        res.set('Content-Type', 'image/png');
        res.send(screenshot);
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

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
    // Add a timeout to isConnected to avoid hanging the entire request
    const isActuallyConnected = client ? await Promise.race([
        client.isConnected(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('isConnected timeout')), 5000))
    ]).catch(() => false) : false;
    
    if (!isActuallyConnected) {
      connectionStatus = 'DISCONNECTED';
      return res.status(401).json({ error: 'Client not connected' });
    }
    connectionStatus = 'CONNECTED';
  }

  const formattedPhone = phone.includes('@c.us') ? phone : `${phone}@c.us`;

  if (fireAndForget) {
    client.sendText(formattedPhone, message, { waitForAck: false })
      .then(() => { lastSuccessfulSendTimestamp = Date.now(); })
      .catch((err) => { 
        if (err.message.includes('msgChunks')) return; // Ignore known WPPConnect bug
        console.error('[Async Error] Send attempt:', err.message); 
      });

    return res.status(202).json({ success: true, mode: 'fire-and-forget' });
  }

  // Standard Path
  try {
    client.sendText(formattedPhone, message, { waitForAck: false })
      .catch(e => {
        if (e.message.includes('msgChunks')) return;
        console.error('Send error:', e.message);
      });
    lastSuccessfulSendTimestamp = Date.now();
    res.json({ success: true, note: 'Message dispatched' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/logout', async (req, res) => {
  try {
    if (client) {
      await client.logout().catch(() => {});
      await client.close().catch(() => {});
      client = null;
    }
    connectionStatus = 'DISCONNECTED';
    qrCode = null;
    res.json({ success: true, message: 'Logged out. Engine will restart.' });
    // Restart after a short delay
    setTimeout(() => start(), 2000);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Health check interval - made less aggressive
setInterval(async () => {
  if (client && connectionStatus === 'CONNECTED') {
    try {
      const isActuallyConnected = await client.isConnected();
      if (!isActuallyConnected) {
        logEvent('HEALTH_CHECK_FAILED', { reason: 'client.isConnected() returned false' });
        connectionStatus = 'DISCONNECTED';
        // Only trigger recovery if we've been disconnected for a while
        // triggerSoftRecovery(); 
      }
    } catch (e) {
      logEvent('HEALTH_CHECK_ERROR', { error: e.message });
    }
  }
}, 60000); // Check every minute instead of 30s

app.listen(port, '0.0.0.0', () => {
  console.log(`Engine listening at http://0.0.0.0:${port}`);
  start();
});
