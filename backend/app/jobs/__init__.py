"""Scheduled work that belongs to `elestrals-api` rather than to the harvester.

There is deliberately no scheduler in here. `harvest-api` carries Celery and beat because it has
long-running, retryable, rate-limited jobs; this service has one nightly job that finishes in
seconds, and adding a broker to run it would be a large amount of infrastructure for a `cron`
line. `DEPLOY.md` documents the invocation.
"""
