# Railway Secrets Configuration

## Required Secrets for KYC_Apexon Deployment

### 1. GOOGLE_CREDENTIALS_JSON
- **Type:** Secret (paste full JSON content)
- **Value:** Complete service account JSON from `google-vision-sa-checkpoint.json`
- **Used by:** Dockerfile build arg → `/tmp/google-credentials.json`
- **Consumed by:** `OCRHandler` via `GOOGLE_APPLICATION_CREDENTIALS` env var

## Setup Steps
1. In Railway project dashboard, go to **Variables**.
2. Click **New Variable** and choose **Secret**.
3. Name: `GOOGLE_CREDENTIALS_JSON`.
4. Value: paste the full JSON content from your local service account file.
5. Click **Add**.

## Verification Steps
1. Trigger a deployment.
2. Open deployment logs and confirm there are no credential-not-found errors.
3. Run OCR flow in the app and confirm Vision client initializes.

## Security Notes
- Never commit credential JSON files into Git.
- Keep `google-vision-sa-checkpoint.json` local only.
- Rotate service account keys immediately if accidental exposure occurs.
