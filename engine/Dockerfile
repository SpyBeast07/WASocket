FROM node:20-slim

# Install dependencies based on architecture
RUN apt-get update && apt-get install -y wget gnupg ca-certificates \
    && ARCH=$(uname -m) \
    && if [ "$ARCH" = "x86_64" ]; then \
        echo "Installing Google Chrome for AMD64" \
        && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
        && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
        && apt-get update && apt-get install -y google-chrome-stable; \
    else \
        echo "Installing Chromium for ARM64" \
        && apt-get update && apt-get install -y chromium; \
    fi \
    && apt-get install -y \
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
    && rm -rf /var/lib/apt/lists/* \
    && ln -s $(which google-chrome-stable || which chromium || which google-chrome) /usr/bin/browser

WORKDIR /app

# Puppeteer/WPPConnect config
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/browser

COPY engine/package.json ./
RUN npm install

COPY engine/index.js ./

EXPOSE 3000

CMD ["sh", "-c", "rm -rf /app/tokens/**/SingletonLock && node index.js"]
