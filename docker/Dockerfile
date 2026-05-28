FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -g 1234 appgroup \
    && useradd -u 1234 -g appgroup -M -d /app -s /sbin/nologin appuser

COPY --chown=1234:1234 . .

USER 1234:1234

EXPOSE 8000
