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
let connectionStatus = 'DISCONNECTED';
let qrCode = null;
let lastSuccessfulSendTimestamp = 0;

function logEvent(event, details = {}) {
  const timestamp = new Date().toISOString();
  console.log(JSON.stringify({ timestamp, event, ...details }));
}

async function start() {
  logEvent('ENGINE_STARTUP', {
      free_mem: Math.round(os.freemem() / 1024 / 1024) + 'MB',
      total_mem: Math.round(os.totalmem() / 1024 / 1024) + 'MB',
      cores: os.cpus().length,
      platform: os.platform(),
      arch: os.arch()
  });

  try {
    // Robust launch for resource-rich environments
    client = await wppconnect.create({
      session: sessionName,
      autoClose: 0, 
      waitForLogin: false,
      tokenStore: 'file',
      folderNameToken: 'tokens',
      headless: 'new',
      debug: false,
      logQR: true,
      catchQR: (base64Qrimg, asciiQR, attempts, urlCode) => {
        qrCode = urlCode;
        logEvent('QR_RECEIVED', { attempt: attempts });
        console.log(asciiQR);
      },
      statusFind: (statusSession) => {
        logEvent('STATUS_FIND', { status: statusSession });
        if (['isLogged', 'qrReadSuccess'].includes(statusSession)) {
          connectionStatus = 'CONNECTED';
        } else if (['browserClose', 'autocloseCalled', 'disconnectedMobile'].includes(statusSession)) {
          connectionStatus = 'DISCONNECTED';
        }
      },
      puppeteerOptions: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/browser',
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-gpu', // Keep disabled for stability in Docker unless specifically needed
          '--disable-software-rasterizer',
          '--disable-extensions',
          '--disable-features=site-per-process,IsolateOrigins',
          '--no-first-run',
          '--no-zygote',
          '--window-size=1920,1080',
          '--disable-notifications',
          '--disable-remote-fonts',
          '--hide-scrollbars'
        ],
      }
    });

    logEvent('CLIENT_INITIALIZED');
    setupClientEvents(client);
  } catch (error) {
    console.error('Error starting WPPConnect:', error);
    connectionStatus = 'ERROR';
  }
}

function setupClientEvents(client) {
  client.onStateChange((state) => {
    logEvent('CONNECTION_STATE_CHANGE', { state });
    if (['CONNECTED', 'PAIRING', 'OPENING', 'SYNCING'].includes(state)) {
      connectionStatus = 'CONNECTED';
    } else {
      connectionStatus = 'AUTH_REQUIRED';
    }
  });

  // Reconnection logic if browser crashes
  if (client.page && client.page.browser()) {
      client.page.browser().on('disconnected', () => {
          logEvent('BROWSER_DISCONNECTED');
          connectionStatus = 'DISCONNECTED';
          // Wait and restart
          setTimeout(() => start(), 5000);
      });
  }
}

// API Endpoints
app.get('/screenshot', async (req, res) => {
    if (!client || !client.page) return res.status(404).json({ error: 'Browser not active' });
    try {
        // High quality PNG for resource-rich environments
        const screenshot = await client.page.screenshot({ 
            type: 'png', 
            fullPage: true 
        });
        res.set('Content-Type', 'image/png');
        res.send(screenshot);
    } catch (e) {
        logEvent('SCREENSHOT_ERROR', { error: e.message });
        res.status(500).json({ error: e.message });
    }
});

app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    engine_status: connectionStatus,
    free_mem: Math.round(os.freemem() / 1024 / 1024) + 'MB',
    total_mem: Math.round(os.totalmem() / 1024 / 1024) + 'MB'
  });
});

app.get('/status', (req, res) => {
  res.json({ 
    status: connectionStatus, 
    qr_code: connectionStatus === 'AUTH_REQUIRED' ? qrCode : null
  });
});

app.post('/send-message', async (req, res) => {
  const { phone, message } = req.body;
  logEvent('SEND_MESSAGE_REQUEST', { phone });

  if (!phone || !message) return res.status(400).json({ error: 'Missing data' });
  
  if (connectionStatus !== 'CONNECTED') {
    logEvent('SEND_MESSAGE_FAILED', { reason: 'not_connected', status: connectionStatus });
    return res.status(401).json({ error: 'Client not connected' });
  }

  try {
    const formattedPhone = phone.includes('@c.us') ? phone : `${phone}@c.us`;
    logEvent('SEND_MESSAGE_START', { formattedPhone });
    
    // Use waitForAck: false to just ensure the message is dispatched to WhatsApp
    // without waiting for delivery confirmation which can be flaky.
    await Promise.race([
        client.sendText(formattedPhone, message, { waitForAck: false }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Send timeout')), 25000))
    ]);
    
    lastSuccessfulSendTimestamp = Date.now();
    logEvent('SEND_MESSAGE_SUCCESS', { phone });
    res.json({ success: true });
  } catch (error) {
    logEvent('SEND_MESSAGE_ERROR', { error: error.message, phone });
    res.status(500).json({ error: error.message });
  }
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Engine listening at http://0.0.0.0:${port}`);
  start();
});
