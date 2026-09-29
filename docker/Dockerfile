# syntax=docker/dockerfile:1.7
#
# Manager Warsztatów application image: gunicorn web process by default, `manage.py qcluster`
# for the worker. Built for linux/amd64 and linux/arm64 by .github/workflows/docker-publish.yml.

ARG PYTHON_VERSION=3.13

# --- Build stage: resolve the locked dependencies into /opt/venv ------------------------------
FROM python:${PYTHON_VERSION}-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /bin/uv

# The venv lives outside /app so the DEV bind mount of the source tree never hides it.
# Inside the image the interpreter is the base image's Python, not a uv-managed download.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    uv sync --locked --no-dev --no-install-project

# --- Runtime stage -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="Manager Warsztatów" \
      org.opencontainers.image.description="Workshop registration and management" \
      org.opencontainers.image.source="https://github.com/MarekWo/manager-warsztatow" \
      org.opencontainers.image.licenses="MIT"

# WeasyPrint (attendance lists, certificates) renders with Pango; DejaVu covers Polish glyphs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core sqlite3 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=workshop_manager.config.settings.prod \
    STATIC_ROOT=/opt/static \
    DATA_DIR=/data

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app --no-create-home app \
    && mkdir -p /data/media \
    && chown -R app:app /data

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY . /app

# Static files are collected at build time; the dummy values exist only for this command.
RUN SECRET_KEY=collectstatic-only DATA_DIR=/tmp/build \
    python manage.py collectstatic --noinput --verbosity 0 \
    && rm -rf /tmp/build

COPY --chmod=0755 docker/entrypoint.sh /usr/local/bin/entrypoint

# Last, so a new commit does not invalidate the collectstatic layer. `.git` is not in the build
# context, hence a build argument (docker-publish.yml passes the commit SHA).
ARG GIT_SHA=""
ENV APP_BUILD=${GIT_SHA}

USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=4)"]

ENTRYPOINT ["entrypoint"]
# Two workers are plenty for this scale and keep memory low on a shared server.
CMD ["gunicorn", "workshop_manager.config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--control-socket", "/tmp/gunicorn.ctl"]
