# harvest-api image — the second backend.
#
# Simpler than backend/Dockerfile on purpose: this service does not use the platform's admin SDK,
# so there is no named build context and no unpublished wheel to smuggle in. One `pip install -r`
# and it resolves from PyPI.
#
# The same image runs all three roles — API, Celery worker, Celery beat — differing only in the
# command. One image means one build, one tag and one thing to be sure is the version you think
# it is; three images that must stay in lockstep is a deployment bug waiting for a hurried
# afternoon.
FROM python:3.12-slim

# tini: uvicorn and celery as PID 1 do not reap children or forward signals, so `docker stop`
# takes the full timeout instead of shutting down cleanly. For the worker that also means a scan
# is killed rather than stopped.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# alembic/ and alembic.ini are NOT optional: without them the container cannot run
# `alembic upgrade head`, which is how `elestrals_harvest` gets created on a fresh deployment.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Run unprivileged. The service writes nothing to disk — logs go to stdout, everything else to
# its own schema.
RUN useradd --create-home --uid 10002 harvest && chown -R harvest:harvest /app
USER harvest

EXPOSE 9100

# /health reports MySQL and Redis separately, so an unhealthy container is one that cannot serve.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:9100/api/v1/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9100"]
