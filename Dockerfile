# Lets a cloud host (Railway, Fly.io, or any server with Docker) run the bot 24/7.
FROM python:3.12-slim

# ffmpeg + opus play audio in voice channels; espeak-ng is a backup voice if Google TTS is unreachable;
# tesseract reads slip screenshots for free.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 espeak-ng tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY paper-bots ./paper-bots
# Staff APEX-CITY SPA (built Vite bundle). Rebuild with: cd trading-city && npm ci && npm run build
COPY trading-city/dist ./trading-city/dist
COPY trading-city/bridge.py ./trading-city/bridge.py
COPY trading-city/README.md ./trading-city/README.md

# The picks database lives in /data. When /data is a mounted volume, closed paper
# settlements are kept in /data/paper-bots. Attach a persistent volume at /data
# on your host, otherwise picks and closed paper trades are wiped on redeploy.
RUN mkdir -p /data
ENV DB_PATH=/data/picks.db \
    PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
