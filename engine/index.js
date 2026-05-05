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
let isReady = false;
let lastReloadTime = Date.now();

function logEvent(event, details = {}) {
  const timestamp = new Date().toISOString();
  console.log(JSON.stringify({ timestamp, event, ...details }));
}

async function start() {
  logEvent('ENGINE_STARTUP', {
      free_mem: Math.round(os.freemem() / 1024 / 1024) + 'MB',
      total_mem: Math.round(os.totalmem() / 1024 / 1024) + 'MB',
      node_heap: Math.round(process.memoryUsage().heapTotal / 1024 / 1024) + 'MB'
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
      headless: true,
      debug: false,
      logQR: true,
      whatsappVersion: '2.3000.1015901391',
      catchQR: (base64Qrimg, asciiQR, attempts, urlCode) => {
        qrCode = urlCode;
        logEvent('QR_RECEIVED', { attempt: attempts });
      },
      statusFind: (statusSession) => {
        logEvent('STATUS_FIND', { status: statusSession });
      },
      puppeteerOptions: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/browser',
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-extensions',
          '--no-zygote',
          '--window-size=1920,1080',
          '--disable-web-security',
          '--allow-running-insecure-content',
          '--user-data-dir=/app/tokens/browser_profile',
          '--test-type',
          '--no-first-run'
        ],
      }
    });

    logEvent('CLIENT_INITIALIZED');
    
    if (client.page) {
        // Fix for "storage bucket persistence denied"
        try {
            const context = client.page.browser().defaultBrowserContext();
            await context.overridePermissions('https://web.whatsapp.com', ['notifications', 'persistent-storage']);
            logEvent('PERMISSIONS_OVERRIDDEN');
        } catch (e) {
            logEvent('PERMISSIONS_ERROR', { error: e.message });
        }

        await client.page.setRequestInterception(true);
        client.page.on('request', (req) => {
            const type = req.resourceType();
            if (['media', 'font'].includes(type)) return req.abort();
            req.continue();
        });

        client.page.on('console', msg => {
            const text = msg.text();
            if (text.includes('WPP') || text.includes('error') || text.includes('storage') || text.includes('MasterDatabase')) {
                console.log(`[Browser] ${text}`);
            }
        });
    }

    setupClientEvents(client);
    startActiveMonitoring();
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
      // Wait for WPP to be injected and ready
      let attempts = 0;
      while (attempts < 10) {
          const wppReady = await client.page.evaluate(() => typeof WPP !== 'undefined' && WPP.isReady).catch(() => false);
          if (wppReady) break;
          await new Promise(r => setTimeout(r, 2000));
          attempts++;
      }
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
          logEvent('BROWSER_DISCONNECTED_RESTARTING');
          isReady = false;
          connectionStatus = 'DISCONNECTED';
          setTimeout(() => start(), 5000);
      });
  }
}

function startActiveMonitoring() {
    setInterval(async () => {
        if (!client || !client.page) return;
        try {
            // Ping
            await Promise.race([
                client.page.evaluate(() => 1 + 1),
                new Promise((_, r) => setTimeout(() => r(new Error('timeout')), 5000))
            ]);
        } catch (e) {
            logEvent('MONITOR_PING_FAILED', { error: e.message });
            if (Date.now() - lastReloadTime > 60000) {
                lastReloadTime = Date.now();
                client.page.reload().catch(() => {});
            }
        }
    }, 30000);
}

app.post('/send-message', async (req, res) => {
  const { phone, message } = req.body;
  logEvent('SEND_MESSAGE_REQUEST', { phone });

  if (!phone || !message) return res.status(400).json({ error: 'Missing data' });
  
  if (!isReady) {
    return res.status(503).json({ error: 'Session initializing' });
  }

  try {
    const formattedPhone = phone.includes('@c.us') ? phone : `${phone}@c.us`;
    logEvent('SEND_MESSAGE_START', { formattedPhone });
    
    // DIRECT WPP DISPATCH (Much more robust than client.sendText)
    const result = await Promise.race([
        client.page.evaluate(async (p, m) => {
            if (typeof WPP === 'undefined') throw new Error('WPP_NOT_INJECTED');
            if (!WPP.isReady) throw new Error('WPP_NOT_READY');
            // Check if phone exists first to avoid hangs
            const exists = await WPP.contact.queryExists(p);
            if (!exists) throw new Error('PHONE_NOT_ON_WHATSAPP');
            
            return await WPP.chat.sendTextMessage(p, m, {
                createChat: true,
                waitForAck: false
            });
        }, formattedPhone, message),
        new Promise((_, reject) => setTimeout(() => reject(new Error('DISPATCH_TIMEOUT')), 20000))
    ]);

    logEvent('SEND_MESSAGE_SUCCESS', { phone, msgId: result.id });
    res.json({ success: true, messageId: result.id });
  } catch (error) {
    logEvent('SEND_MESSAGE_ERROR', { error: error.message, phone });
    
    if (error.message.includes('TIMEOUT') || error.message.includes('NOT_READY')) {
        if (Date.now() - lastReloadTime > 30000) {
            lastReloadTime = Date.now();
            client.page.reload().catch(() => {});
        }
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
    ready: isReady,
    status_text: connectionStatus,
    free_mem: Math.round(os.freemem() / 1024 / 1024) + 'MB',
    heap: Math.round(process.memoryUsage().heapUsed / 1024 / 1024) + 'MB'
  });
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Engine listening at http://0.0.0.0:${port}`);
  start();
});
