FROM python:3.12-slim

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin sandbox \
    && pip install --no-cache-dir pytest==8.3.4

USER sandbox
WORKDIR /tmp
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# No secrets, credentials, or application source are baked into this image.
# Repositories are mounted read-only at runtime.
