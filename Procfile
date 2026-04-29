web: sh -c 'if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then printf "%s" "$GOOGLE_CREDENTIALS_JSON" > /tmp/google-credentials.json; fi && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}'
