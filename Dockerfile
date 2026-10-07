# Lets a cloud host (Railway, Fly.io, or any server with Docker) run the bot 24/7.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# The picks database lives in /data. Attach a persistent volume at /data on your
# host, otherwise the picks are wiped every time the bot is redeployed.
RUN mkdir -p /data
ENV DB_PATH=/data/picks.db \
    PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
