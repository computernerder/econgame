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

# Build identity is baked into this image; ordinary saves never change it.
ARG EMPIRE_BUILD_NUMBER=local
ARG EMPIRE_GIT_SHA=unknown
ENV EMPIRE_BUILD_NUMBER=$EMPIRE_BUILD_NUMBER EMPIRE_GIT_SHA=$EMPIRE_GIT_SHA
LABEL org.opencontainers.image.source="https://github.com/computernerder/econgame" \
    org.opencontainers.image.revision=$EMPIRE_GIT_SHA \
    io.econgame.build-number=$EMPIRE_BUILD_NUMBER

USER 10001:10001
VOLUME ["/data"]
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-m", "economic_simulation.server", "--healthcheck"]
ENTRYPOINT ["python", "-m", "economic_simulation.server"]
