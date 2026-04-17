# KYC Apexon

A KYC (Know Your Customer) compliance dashboard built with Python and Streamlit, leveraging Claude AI (Anthropic) and Google Vision API for automated document verification and compliance scoring.

## Features

- **Document OCR** — Extract text from ID documents using Google Vision API
- **KYC Compliance Checks** — Automated validation of customer identity data
- **AI-Powered Scoring** — LLM-based compliance risk scoring via Claude
- **Interactive Dashboard** — Streamlit UI for real-time review and reporting

## Project Structure

```
KYC_Apexon/
├── app.py                  # Main Streamlit application
├── kyc_dashboard.py        # Dashboard components
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── src/                    # Core source modules
├── llm_integration/        # Claude AI integration
├── prompts/                # LLM prompt templates
├── tests/                  # Test suite
└── Notebooks/              # Exploratory analysis
    ├── 01_Data_Validation.ipynb
    └── 02_KYC_Checks.ipynb
```

## Getting Started

### Prerequisites

- Python 3.9+
- Anthropic API key
- Google Cloud Vision API service account

### Installation

```bash
git clone https://github.com/LuisLf12R/KYC_Apexon.git
cd KYC_Apexon
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

See `.env.example` for all required environment variables.

### Local Development - Google Vision API

1. Download `google-vision-sa-checkpoint.json` from Google Cloud.
2. Place the file in the project root.
3. Set in `.env`:
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=./google-vision-sa-checkpoint.json
   ```
4. Validate:
   ```bash
   python scripts/test_google_credentials.py
   ```
5. **Never commit the JSON file** (it is ignored by `.gitignore`).

### Run

```bash
streamlit run app.py
```

## Security

- **Never commit `.env`** or any credential files to Git.
- Store secrets in environment variables or a secrets manager.
- For cloud deployment (Vercel, etc.), add keys via the platform’s environment variable settings.

## License

MIT
