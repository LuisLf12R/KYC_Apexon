import json
import os

from google.cloud import vision


def main() -> int:
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")

    ok = True

    if creds_path:
        try:
            with open(creds_path, encoding="utf-8") as f:
                creds = json.load(f)
            print(f"✓ Credentials file loaded: {creds.get('type')}")
            print(f"  Project: {creds.get('project_id')}")
            print(f"  Service Account: {creds.get('client_email')}")
        except Exception as e:
            ok = False
            print(f"✗ Failed to load credentials: {e}")
    else:
        ok = False
        print("✗ GOOGLE_APPLICATION_CREDENTIALS not set")

    try:
        _ = vision.ImageAnnotatorClient()
        print("✓ Vision client initialized successfully")
    except Exception as e:
        ok = False
        print(f"✗ Failed to initialize Vision client: {e}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
