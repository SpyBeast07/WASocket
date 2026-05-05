FROM node:20-slim

# Install Chromium, dumb-init and dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    dumb-init \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libdrm2 \
    libxkbcommon0 \
    libxshmfence1 \
    lsb-release \
    xdg-utils \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/chromium /usr/bin/browser

WORKDIR /app

# Puppeteer/WPPConnect config
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/browser
ENV PUPPETEER_CACHE_DIR=/app/.puppeteer_cache

COPY engine/package.json ./
RUN npm install

COPY engine/index.js ./

EXPOSE 3000

# Ensure tokens directory exists and is writable
RUN mkdir -p /app/tokens && chmod 777 /app/tokens

# Use dumb-init as entrypoint to manage zombie processes
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

CMD ["sh", "-c", "rm -rf /app/tokens/**/SingletonLock && NODE_OPTIONS='--max-old-space-size=4096' node index.js"]
