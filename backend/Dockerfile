# syntax=docker/dockerfile:1.7
# type-10022026-Maurice: Pinned non-root API image for deterministic local deployment.
FROM python:3.12.8-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY requirements.txt /app/requirements.txt
ARG PIP_VERSION=25.2
ARG SETUPTOOLS_VERSION=75.6.0
ARG WHEEL_VERSION=0.45.1
ARG PIP_INSTALL_TIMEOUT=60
ARG PIP_INSTALL_RETRIES=5
# type-10022026-Maurice: Keep PyPI's normal TLS/index behavior while bounding transient failures.
RUN --mount=type=cache,target=/root/.cache/pip \
    test "${PIP_INSTALL_TIMEOUT}" -ge 1 && test "${PIP_INSTALL_TIMEOUT}" -le 300 && \
    test "${PIP_INSTALL_RETRIES}" -ge 0 && test "${PIP_INSTALL_RETRIES}" -le 10 && \
    python -m pip install --disable-pip-version-check --no-input \
      --timeout="${PIP_INSTALL_TIMEOUT}" --retries="${PIP_INSTALL_RETRIES}" \
      "pip==${PIP_VERSION}" "setuptools==${SETUPTOOLS_VERSION}" "wheel==${WHEEL_VERSION}" && \
    python -m pip install --disable-pip-version-check --no-input \
      --timeout="${PIP_INSTALL_TIMEOUT}" --retries="${PIP_INSTALL_RETRIES}" \
      --requirement /app/requirements.txt gunicorn==23.0.0 celery==5.4.0 redis==5.2.1
COPY backend /app/backend
RUN mkdir -p /run/ehr && chown -R app:app /app /run/ehr
USER app
EXPOSE 8000
