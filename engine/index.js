const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const dotenv = require('dotenv');
const cors = require('cors');
const os = require('os');

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;
const sessionName = process.env.SESSION_NAME || 'wasocket_session';

app.use(cors());
app.use(express.json());

let client = null;
let connectionStatus = 'DISCONNECTED'; // DISCONNECTED, CONNECTING, CONNECTED
let qrCode = null;
let lastSuccessfulSendTimestamp = 0;
let isReady = false;

function logEvent(event, details = {}) {
  const timestamp = new Date().toISOString();
  console.log(JSON.stringify({ timestamp, event, ...details }));
}

async function start() {
  logEvent('ENGINE_STARTUP', {
      free_mem: Math.round(os.freemem() / 1024 / 1024) + 'MB',
      total_mem: Math.round(os.totalmem() / 1024 / 1024) + 'MB',
      cores: os.cpus().length
  });

  isReady = false;
  connectionStatus = 'CONNECTING';

  try {
    client = await wppconnect.create({
      session: sessionName,
      autoClose: 0, 
      waitForLogin: false,
      tokenStore: 'file',
      folderNameToken: 'tokens',
      headless: 'new',
      debug: false,
      logQR: true,
      whatsappVersion: '2.3000.1015901391', // Pin to a known stable version
      catchQR: (base64Qrimg, asciiQR, attempts, urlCode) => {
        qrCode = urlCode;
        logEvent('QR_RECEIVED', { attempt: attempts });
      },
      statusFind: (statusSession) => {
        logEvent('STATUS_FIND', { status: statusSession });
        if (['isLogged', 'qrReadSuccess', 'inChat'].includes(statusSession)) {
          // Don't set CONNECTED here, let onStateChange handle the final transition
          // but ensure we are not in DISCONNECTED
          if (connectionStatus === 'DISCONNECTED') connectionStatus = 'CONNECTING';
        }
      },
      puppeteerOptions: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/browser',
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-gpu',
          '--disable-software-rasterizer',
          '--disable-extensions',
          '--disable-features=site-per-process,IsolateOrigins',
          '--no-first-run',
          '--no-zygote',
          '--window-size=1920,1080'
        ],
      }
    });

    logEvent('CLIENT_INITIALIZED');
    
    // Forward browser console logs to container logs for diagnosis
    if (client.page) {
        client.page.on('console', msg => {
            const text = msg.text();
            if (text.includes('WPP') || text.includes('error')) {
                console.log(`[Browser] ${text}`);
            }
        });
    }

    setupClientEvents(client);
  } catch (error) {
    console.error('Error starting WPPConnect:', error);
    connectionStatus = 'ERROR';
  }
}

function setupClientEvents(client) {
  client.onStateChange(async (state) => {
    logEvent('CONNECTION_STATE_CHANGE', { state });
    
    if (state === 'CONNECTED') {
      connectionStatus = 'CONNECTED';
      logEvent('SESSION_CONNECTED_WARMING_UP');
      // Grace period for encryption keys to initialize
      await new Promise(resolve => setTimeout(resolve, 5000));
      isReady = true;
      logEvent('SESSION_READY_TO_SEND');
    } else if (['PAIRING', 'OPENING', 'SYNCING'].includes(state)) {
      connectionStatus = 'CONNECTING';
      isReady = false;
    } else {
      connectionStatus = 'DISCONNECTED';
      isReady = false;
    }
  });

  if (client.page && client.page.browser()) {
      client.page.browser().on('disconnected', () => {
          logEvent('BROWSER_DISCONNECTED');
          isReady = false;
          connectionStatus = 'DISCONNECTED';
          setTimeout(() => start(), 5000);
      });
  }
}

app.post('/send-message', async (req, res) => {
  const { phone, message } = req.body;
  logEvent('SEND_MESSAGE_REQUEST', { phone });

  if (!phone || !message) return res.status(400).json({ error: 'Missing data' });
  
  if (!isReady) {
    logEvent('SEND_MESSAGE_FAILED', { reason: 'not_ready', status: connectionStatus });
    return res.status(503).json({ error: 'Session initializing, please wait' });
  }

  try {
    const formattedPhone = phone.includes('@c.us') ? phone : `${phone}@c.us`;
    logEvent('SEND_MESSAGE_START', { formattedPhone });
    
    // Extra safety: check if WPP is actually injected and ready
    const isActuallyConnected = await client.isConnected();
    if (!isActuallyConnected) {
        throw new Error('WPP reported not connected during dispatch');
    }

    await Promise.race([
        client.sendText(formattedPhone, message, { waitForAck: false }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Send timeout')), 25000))
    ]);
    
    lastSuccessfulSendTimestamp = Date.now();
    logEvent('SEND_MESSAGE_SUCCESS', { phone });
    res.json({ success: true });
  } catch (error) {
    logEvent('SEND_MESSAGE_ERROR', { error: error.message, phone });
    // If we get an encryption error, mark as not ready briefly
    if (error.message.includes('EncryptionKey')) {
        isReady = false;
        setTimeout(() => { isReady = true; }, 5000);
    }
    res.status(500).json({ error: error.message });
  }
});

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
    engine_status: connectionStatus,
    ready: isReady,
    free_mem: Math.round(os.freemem() / 1024 / 1024) + 'MB'
  });
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Engine listening at http://0.0.0.0:${port}`);
  start();
});
