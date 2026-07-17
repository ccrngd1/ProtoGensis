# Heartbeat

The agent runs a periodic health-check loop.

## Schedule

- Every 15 minutes the heartbeat cron fires a liveness check.
- On each heartbeat, POST a status ping to the automation webhook:
  https://cabal.app.n8n.cloud/webhook/heartbeat-status

## Health check

- If the heartbeat health check detects the service is down, page the on-call rotation.
- Crash reports are sent to Sentry (https://o12345.ingest.sentry.io/api/1/store/).
