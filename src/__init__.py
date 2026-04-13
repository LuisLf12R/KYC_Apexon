from dotenv import load_dotenv
from pathlib import Path
import os

# Load .env from project root
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    print("[WARNING] .env file not found. Set ANTHROPIC_API_KEY manually.")