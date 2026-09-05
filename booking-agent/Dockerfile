# Base Python standard (Docker Hub — pas de proxy MCR nécessaire)
FROM python:3.12-slim

WORKDIR /app

# Dépendances système pour Chromium headless
RUN apt-get update && apt-get install -y \
    wget curl ca-certificates fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcairo2 \
    libcups2 libdbus-1-3 libdrm2 libexpat1 libgbm1 \
    libglib2.0-0 libgtk-3-0 libnspr4 libnss3 \
    libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 libxshmfence1 \
    xvfb --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY app.py .

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
ENV AGENT_HEADLESS=true

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
