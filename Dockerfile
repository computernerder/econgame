FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    EMPIRE_DATA_DIR=/data \
    EMPIRE_PORT=8000

WORKDIR /app
COPY pyproject.toml ./
COPY economic_simulation/ ./economic_simulation/
RUN pip install --no-cache-dir . \
    && mkdir -p /data \
    && chown 10001:10001 /data

USER 10001:10001
VOLUME ["/data"]
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-m", "economic_simulation.server", "--healthcheck"]
ENTRYPOINT ["python", "-m", "economic_simulation.server"]
