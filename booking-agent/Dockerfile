# Service agent navigateur (zéro-clic). Image Playwright officielle = Chromium + deps préinstallés.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app
COPY requirements.txt .
# pin playwright==1.47.0 pour matcher le Chromium de l'image de base v1.47.0-jammy
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium
COPY app.py .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
