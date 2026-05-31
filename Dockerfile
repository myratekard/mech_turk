# mech_turk backend — FastAPI engine + API (DO App Platform service)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# OpenCV (headless) runtime dep.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code + bundled CV badge templates (the live CV second opinion needs these).
COPY app ./app
COPY badges ./badges

EXPOSE 8080
# App Platform injects $PORT (defaults to 8080).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
