# Elestral Vault backend image.
#
# The platform's Python admin SDK (`lars-kluijtmans-admin-sdk`) is NOT on PyPI, so it comes in
# through a NAMED BUILD CONTEXT — the same technique the platform uses for its own in-repo
# libtenancy/libservice, except ours lives in a sibling repository:
#
#   docker build --build-context adminsdk=../../auth/packages/python/admin-sdk-python -t elestrals-api .
#
# docker-compose wires it via `additional_contexts`, and the release workflow checks the auth
# repo out first and points the context at it. Once `publish-admin-sdk-python.yml` has pushed
# 0.2.0 to PyPI this whole mechanism can be deleted and requirements.txt will resolve on its own.
FROM python:3.12-slim

# tini: uvicorn as PID 1 does not reap children or forward signals, so `docker stop` takes the
# full 10s timeout instead of shutting down cleanly.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The unpublished SDK first, so the `==0.2.0` pin in requirements.txt is already satisfied and
# pip never reaches for PyPI.
COPY --from=adminsdk . /tmp/admin-sdk
RUN pip install --no-cache-dir /tmp/admin-sdk && rm -rf /tmp/admin-sdk

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# alembic/ and alembic.ini are NOT optional: without them the container cannot run
# `alembic upgrade head`, which is how the schema gets created on a fresh deployment.
# data/ carries the curated catalog seed the importer reads (adr-001).
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY data ./data
COPY scripts ./scripts

# Run unprivileged. The app writes nothing to disk — logs go to stdout and to app_logs.
RUN useradd --create-home --uid 10001 elestrals && chown -R elestrals:elestrals /app
USER elestrals

EXPOSE 9000

# /health reports database reachability, so an unhealthy container is one that cannot serve.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:9000/api/v1/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
