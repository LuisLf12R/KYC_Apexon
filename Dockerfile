FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Google Vision API credentials are injected via Railway secret at build time
# Secret name: GOOGLE_CREDENTIALS_JSON (set in Railway project settings)
# File location: /tmp/google-credentials.json
# Environment variable: GOOGLE_APPLICATION_CREDENTIALS
ARG GOOGLE_CREDENTIALS_JSON=""
RUN if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then \
      printf '%s' "$GOOGLE_CREDENTIALS_JSON" > /tmp/google-credentials.json; \
    fi
ENV GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-credentials.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Health check for credentials (non-blocking during image build)
RUN python scripts/test_google_credentials.py || echo "Warning: Could not validate credentials"

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
