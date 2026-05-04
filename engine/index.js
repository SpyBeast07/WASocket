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

async function start() {
  try {
    client = await wppconnect.create({
      session: sessionName,
      autoClose: 0,
      whatsappVersion: '2.3000.1015901307', // Force a known stable version
      catchQR: (base64Qrimg, asciiQR, attempts, urlCode) => {
        console.log('Number of attempts to read the qrcode: ', attempts);
        qrCode = urlCode;
      },
      statusFind: (statusSession, session) => {
        connectionStatus = statusSession;
      },
      folderNameToken: 'tokens',
      headless: true,
      useChrome: true,
      debug: false,
      browserArgs: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--single-process',
        '--disable-gpu'
      ],
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
    console.log('State changed: ', state);
    connectionStatus = state;
  });

  client.onIncomingCall((call) => {
    console.log('Incoming call from: ', call.peerJid);
  });
}

// API Endpoints

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'engine' });
});

app.get('/status', async (req, res) => {
  let isConnected = false;
  if (client) {
    try {
      isConnected = await client.isConnected();
    } catch (e) {
      isConnected = false;
    }
  }

  res.json({
    status: connectionStatus,
    connected: isConnected,
    qrCode: isConnected ? null : qrCode,
    session: sessionName
  });
});

app.get('/session', async (req, res) => {
  if (!client || (connectionStatus !== 'CONNECTED' && connectionStatus !== 'qrRead-SUCCESS')) {
    const isActuallyConnected = client ? await client.isConnected().catch(() => false) : false;
    if (!isActuallyConnected) {
      return res.status(401).json({ error: 'Client not connected', status: connectionStatus });
    }
  }

  try {
    const hostDevice = await client.getHostDevice();
    res.json({
      wid: hostDevice.wid,
      pushname: hostDevice.pushname,
      platform: hostDevice.platform,
      phone: hostDevice.wid.user
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/send-message', async (req, res) => {
  const { phone, message } = req.body;

  if (!phone || !message) {
    return res.status(400).json({ error: 'Phone and message are required' });
  }

  if (!client || (connectionStatus !== 'CONNECTED' && connectionStatus !== 'qrRead-SUCCESS')) {
    const isActuallyConnected = client ? await client.isConnected().catch(() => false) : false;
    if (!isActuallyConnected) {
      return res.status(401).json({ error: 'Client not connected', status: connectionStatus });
    }
  }

  try {
    // Ensure number is in correct format (with @c.us)
    const formattedPhone = phone.includes('@c.us') ? phone : `${phone}@c.us`;
    
    const result = await client.sendText(formattedPhone, message);
    res.json({ success: true, result });
  } catch (error) {
    // Workaround for known WPPConnect 'msgChunks' bug
    if (error.message && error.message.includes('msgChunks')) {
      console.warn('Caught msgChunks error, but message was likely sent.');
      return res.json({ 
        success: true, 
        warning: 'Message sent but metadata retrieval failed (msgChunks bug)',
        phone 
      });
    }

    console.error('Error sending message:', error);
    res.status(500).json({ error: error.message });
  }
});

// Heartbeat to monitor connection health
setInterval(async () => {
  if (client) {
    const isConnected = await client.isConnected().catch(() => false);
    console.log(`[Heartbeat] Status: ${connectionStatus} | Connected: ${isConnected}`);
  }
}, 30000);

app.listen(port, () => {
  console.log(`Engine listening at http://localhost:${port}`);
  start();
});
