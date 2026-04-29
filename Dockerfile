FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-credentials.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${PORT:-8000}

CMD ["sh", "start.sh"]
