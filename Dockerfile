FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-credentials.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "if [ -n \"$GOOGLE_CREDENTIALS_JSON\" ]; then printf '%s' \"$GOOGLE_CREDENTIALS_JSON\" > /tmp/google-credentials.json; fi && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
