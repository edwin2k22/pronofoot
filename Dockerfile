FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8077 \
    LIVE_POLL=30 \
    PRONOFOOT_READONLY=1 \
    PRONOFOOT_ENABLE_SCHEDULER=1 \
    PRONOFOOT_REFRESH_ON_START=0

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x deploy/start-public.sh

EXPOSE 8077

CMD ["./deploy/start-public.sh"]
