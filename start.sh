#!/bin/sh
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
    printf '%s' "$GOOGLE_CREDENTIALS_JSON" > /tmp/google-credentials.json
fi
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" --loop asyncio
