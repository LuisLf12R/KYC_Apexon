# Railway Deployment Guide

## Google Vision API Setup

1. Obtain service account JSON from Google Cloud Console.
2. In Railway project settings → **Variables**:
   - Add secret: `GOOGLE_CREDENTIALS_JSON`
   - Paste full JSON content.
3. Dockerfile injects this secret to `/tmp/google-credentials.json` at build time.
4. Runtime environment points `GOOGLE_APPLICATION_CREDENTIALS` to that file.
5. Verify in deploy logs that there are no credential/secret errors.

## Deploy Steps
1. Push branch changes.
2. Wait for Railway build to complete.
3. Confirm app comes online.
4. Upload sample OCR document and run extraction.

## Post-Deploy Validation
- Run `python scripts/test_google_credentials.py` inside the container/session if available.
- Confirm OCR requests succeed end-to-end.
- Confirm logs do not print credential contents.

## Local Development - Google Vision API

1. Download `google-vision-sa-checkpoint.json` from Google Cloud.
2. Place it in project root.
3. In `.env`, set:
   ```
   GOOGLE_APPLICATION_CREDENTIALS=./google-vision-sa-checkpoint.json
   ```
4. Run `python scripts/test_google_credentials.py` to verify.
5. Never commit the JSON file.
