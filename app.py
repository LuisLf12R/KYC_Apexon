"""
app.py
KYC Compliance Dashboard - Full Platform Edition
- Streamlit on Railway
- API keys from environment variables
- Data Management: upload raw files, clean, reload engine
- Document OCR: upload image, Google Vision + Claude LLM
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys
import os
import io
import tempfile
from datetime import datetime
import plotly.graph_objects as go
from dotenv import load_dotenv
import base64

load_dotenv()

st.set_page_config(
    page_title="KYC Compliance Dashboard",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INITIALIZE API KEYS FROM ENVIRONMENT
# ============================================================================

@st.cache_resource
def init_api_keys():
    try:
        claude_key = os.getenv('ANTHROPIC_API_KEY')
        if not claude_key:
            return False, "ANTHROPIC_API_KEY not configured"
        os.environ['ANTHROPIC_API_KEY'] = claude_key

        google_key_json = None

        google_path = os.getenv('GOOGLE_VISION_JSON_PATH')
        if google_path and Path(google_path).exists():
            with open(google_path) as f:
                google_key_json = json.load(f)

        if not google_key_json:
            google_base64 = os.getenv('GOOGLE_VISION_JSON_BASE64')
            if google_base64:
                try:
                    decoded = base64.b64decode(google_base64).decode('utf-8')
                    google_key_json = json.loads(decoded)
                except Exception as e:
                    return False, f"Invalid base64 Google Vision key: {str(e)}"

        if not google_key_json:
            google_json = os.getenv('GOOGLE_VISION_JSON')
            if google_json:
                try:
                    google_key_json = json.loads(google_json)
                except Exception as e:
                    return False, f"Invalid JSON Google Vision key: {str(e)}"

        if not google_key_json:
            return False, "Google Vision API key not configured"

        creds_path = Path(tempfile.gettempdir()) / '.kyc_google_creds.json'
        with open(creds_path, 'w') as f:
            json.dump(google_key_json, f)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(creds_path)

        return True, "API keys loaded successfully"

    except Exception as e:
        return False, f"Error loading API keys: {str(e)}"


keys_ok, keys_msg = init_api_keys()

if not keys_ok:
    st.error(f"❌ Configuration Error: {keys_msg}")
    st.warning("""
    **For Local Testing:** Create a `.env` file with:
    ```
    ANTHROPIC_API_KEY=sk-ant-...
    GOOGLE_VISION_JSON_PATH=/path/to/service-account.json
    ```
    **For Railway:** Add environment variables in Railway dashboard.
    """)
    st.stop()

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

for key, default in {
    'kyc_engine': None,
    'engines_initialized': False,
    'customers_df': None,
    'data_dir': None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================================
# KYC ENGINE LOADER (supports custom data directory)
# ============================================================================

def load_engine(data_dir: Path):
    """Load KYC engine from given data directory."""
    try:
        sys.path.insert(0, str(Path.cwd() / 'src'))
        from kyc_engine import KYCComplianceEngine
        engine = KYCComplianceEngine(data_clean_dir=data_dir)
        return engine, engine.customers
    except Exception as e:
        return None, str(e)


# Try default Data Clean/ on startup
if not st.session_state.engines_initialized:
    default_data_dir = Path.cwd() / 'Data Clean'
    if default_data_dir.exists():
        engine, customers = load_engine(default_data_dir)
        if engine is not None:
            st.session_state.kyc_engine = engine
            st.session_state.customers_df = customers
            st.session_state.engines_initialized = True
            st.session_state.data_dir = default_data_dir


# ============================================================================
# DATA CLEANING UTILITIES
# ============================================================================

def clean_dataframe(df: pd.DataFrame, dataset_type: str) -> pd.DataFrame:
    """
    Generic cleaner: normalize columns, parse dates, strip whitespace.
    Maps common column name variants to expected names.
    """
    # Normalize column names
    df.columns = [c.strip().lower().replace(' ', '_').replace('-', '_') for c in df.columns]

    # Column aliases for common variants
    ALIASES = {
        'customers': {
            'id': 'customer_id', 'cust_id': 'customer_id', 'client_id': 'customer_id',
            'type': 'entity_type', 'entity': 'entity_type',
            'country': 'jurisdiction', 'region': 'jurisdiction',
            'risk': 'risk_rating', 'risk_level': 'risk_rating',
            'open_date': 'account_open_date', 'account_date': 'account_open_date',
            'kyc_date': 'last_kyc_review_date', 'last_review': 'last_kyc_review_date',
            'origin': 'country_of_origin',
        },
        'screenings': {
            'id': 'customer_id', 'cust_id': 'customer_id',
            'date': 'screening_date', 'screen_date': 'screening_date',
            'result': 'screening_result', 'status': 'screening_result',
            'match': 'match_name', 'matched_name': 'match_name',
            'list': 'list_reference', 'list_ref': 'list_reference',
            'hit': 'hit_status',
        },
        'id_verifications': {
            'id': 'customer_id', 'cust_id': 'customer_id',
            'doc_type': 'document_type', 'type': 'document_type',
            'issue': 'issue_date', 'issued': 'issue_date',
            'expiry': 'expiry_date', 'expires': 'expiry_date', 'expiration': 'expiry_date',
            'verify_date': 'verification_date', 'verified_date': 'verification_date',
            'status': 'document_status', 'doc_status': 'document_status',
        },
        'transactions': {
            'id': 'customer_id', 'cust_id': 'customer_id',
            'last_date': 'last_txn_date', 'last_transaction': 'last_txn_date',
            'count': 'txn_count', 'num_txn': 'txn_count', 'transactions': 'txn_count',
            'volume': 'total_volume', 'amount': 'total_volume', 'total': 'total_volume',
        },
        'documents': {
            'id': 'customer_id', 'cust_id': 'customer_id',
            'doc_type': 'document_type', 'type': 'document_type',
            'issue': 'issue_date', 'issued': 'issue_date',
            'expiry': 'expiry_date', 'expires': 'expiry_date',
            'category': 'document_category', 'doc_category': 'document_category',
        },
        'beneficial_ownership': {
            'id': 'customer_id', 'cust_id': 'customer_id',
            'name': 'ubo_name', 'owner_name': 'ubo_name', 'beneficial_owner': 'ubo_name',
            'ownership': 'ownership_percentage', 'pct': 'ownership_percentage', 'percent': 'ownership_percentage',
            'nationality': 'nationality',
            'date': 'date_identified', 'identified': 'date_identified',
        },
    }

    aliases = ALIASES.get(dataset_type, {})
    df = df.rename(columns=aliases)

    # Parse date columns
    date_keywords = ['date', 'expiry', 'expiration', 'issued', 'verified']
    for col in df.columns:
        if any(kw in col for kw in date_keywords):
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Strip string whitespace
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].str.strip()

    # Normalize string values to uppercase where expected
    upper_cols = ['screening_result', 'hit_status', 'document_status', 'risk_rating']
    for col in upper_cols:
        if col in df.columns:
            df[col] = df[col].str.upper()

    return df


def save_to_temp_dir(dataframes: dict) -> Path:
    """Save cleaned DataFrames to a temp directory. Returns path."""
    tmp_dir = Path(tempfile.gettempdir()) / 'kyc_data_clean'
    tmp_dir.mkdir(parents=True, exist_ok=True)

    filename_map = {
        'customers': 'customers_clean.csv',
        'screenings': 'screenings_clean.csv',
        'id_verifications': 'id_verifications_clean.csv',
        'transactions': 'transactions_clean.csv',
        'documents': 'documents_clean.csv',
        'beneficial_ownership': 'beneficial_ownership_clean.csv',
    }

    for key, df in dataframes.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            filename = filename_map.get(key, f'{key}_clean.csv')
            df.to_csv(tmp_dir / filename, index=False)

    return tmp_dir


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.title("⚙️ System Status")

    if st.session_state.engines_initialized:
        st.success("✅ System Ready")
        if st.session_state.customers_df is not None:
            st.info(f"📊 {len(st.session_state.customers_df)} customers loaded")
        st.metric("API Keys", "✅ Configured")
        if st.session_state.data_dir:
            st.caption(f"Data: {st.session_state.data_dir}")
    else:
        st.warning("⚠️ No data loaded — use Data Management tab to upload files")

    st.divider()

    st.subheader("📋 About")
    st.markdown("""
    **KYC Compliance Dashboard**

    6-Dimension Compliance Evaluation:
    - AML Screening (25%)
    - Identity Verification (20%)
    - Account Activity (15%)
    - Proof of Address (15%)
    - Beneficial Ownership (15%)
    - Data Quality (10%)
    """)

    st.divider()
    st.subheader("🚀 Deployment")
    st.markdown("**Running on:** Railway\n\n**Framework:** Streamlit")


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

st.title("🏦 KYC Compliance Dashboard")
st.markdown("Production Edition — Real-time Compliance Evaluation")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Individual Evaluation",
    "📊 Batch Results",
    "⚙️ System Info",
    "📁 Data Management",
    "🔬 Document OCR & AI"
])

# ============================================================================
# TAB 1: INDIVIDUAL EVALUATION
# ============================================================================

with tab1:
    if not st.session_state.engines_initialized:
        st.warning("⚠️ No data loaded. Go to the **Data Management** tab to upload your files.")
    else:
        st.header("Search & Evaluate Customer")

        col1, col2 = st.columns([4, 1])
        with col1:
            customer_id = st.text_input("Enter Customer ID", placeholder="C00001", key="customer_search")
        with col2:
            search_button = st.button("🔍 Evaluate", use_container_width=True)

        if search_button and customer_id:
            customer_id = customer_id.upper()
            with st.spinner(f"Evaluating {customer_id}..."):
                try:
                    result = st.session_state.kyc_engine.evaluate_customer(customer_id)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Overall Score", f"{result['overall_score']}/100",
                                  delta=f"Status: {result['overall_status']}")
                    with col2:
                        st.metric("Entity Type", result.get('entity_type', 'N/A'))
                    with col3:
                        st.metric("Risk Rating", result.get('risk_rating', 'N/A'))

                    status = result['overall_status']
                    if status == 'Compliant':
                        st.success(f"✅ {status}")
                    elif 'Minor' in status:
                        st.warning(f"⚠️ {status}")
                    else:
                        st.error(f"❌ {status}")

                    st.subheader("Dimension Breakdown")
                    dimensions_data = {
                        'Dimension': ['AML Screening', 'Identity Verification', 'Account Activity',
                                      'Proof of Address', 'Beneficial Ownership', 'Data Quality'],
                        'Score': [
                            result['aml_screening_score'], result['identity_verification_score'],
                            result['account_activity_score'], result['proof_of_address_score'],
                            result['beneficial_ownership_score'], result['data_quality_score']
                        ],
                        'Weight': [25, 20, 15, 15, 15, 10],
                        'Details': [
                            result['aml_screening_details'].get('finding', 'N/A'),
                            result['identity_verification_details'].get('finding', 'N/A'),
                            result['account_activity_details'].get('finding', 'N/A'),
                            result['proof_of_address_details'].get('finding', 'N/A'),
                            result['beneficial_ownership_details'].get('finding', 'N/A'),
                            result['data_quality_details'].get('finding', 'N/A'),
                        ]
                    }
                    dimensions_df = pd.DataFrame(dimensions_data)

                    col1, col2 = st.columns(2)
                    with col1:
                        fig = go.Figure(data=[go.Bar(
                            x=dimensions_df['Dimension'], y=dimensions_df['Score'],
                            marker_color=['#28a745' if x >= 70 else '#ffc107' if x >= 50 else '#dc3545'
                                          for x in dimensions_df['Score']],
                            text=dimensions_df['Score'], textposition='outside'
                        )])
                        fig.update_layout(title="Dimension Scores", yaxis_title="Score",
                                          height=400, xaxis_tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)

                    with col2:
                        fig = go.Figure(data=[go.Pie(
                            labels=['Compliant', 'Minor Gaps', 'Non-Compliant'],
                            values=[
                                100 if status == 'Compliant' else 0,
                                100 if 'Minor' in status else 0,
                                100 if 'Non' in status else 0
                            ],
                            marker=dict(colors=['#28a745', '#ffc107', '#dc3545'])
                        )])
                        fig.update_layout(title="Compliance Status", height=400)
                        st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Detailed Findings")
                    st.dataframe(dimensions_df[['Dimension', 'Score', 'Weight', 'Details']],
                                 use_container_width=True, hide_index=True)

                except Exception as e:
                    st.error(f"❌ Error evaluating customer: {str(e)}")

# ============================================================================
# TAB 2: BATCH RESULTS
# ============================================================================

with tab2:
    if not st.session_state.engines_initialized:
        st.warning("⚠️ No data loaded. Go to the **Data Management** tab to upload your files.")
    else:
        st.header("Batch Compliance Results")

        if st.button("📊 Run Batch Evaluation", use_container_width=True):
            with st.spinner("Evaluating batch..."):
                try:
                    customer_ids = st.session_state.customers_df['customer_id'].head(100).tolist()
                    results_df = st.session_state.kyc_engine.evaluate_batch(customer_ids)

                    total = len(results_df)
                    compliant = len(results_df[results_df['overall_status'] == 'Compliant'])
                    minor_gaps = len(results_df[results_df['overall_status'] == 'Compliant with Minor Gaps'])
                    non_compliant = len(results_df[results_df['overall_status'] == 'Non-Compliant'])

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Evaluated", total)
                    with col2:
                        st.metric("✅ Compliant", f"{compliant} ({compliant/total*100:.1f}%)")
                    with col3:
                        st.metric("⚠️ Minor Gaps", f"{minor_gaps} ({minor_gaps/total*100:.1f}%)")
                    with col4:
                        st.metric("❌ Non-Compliant", f"{non_compliant} ({non_compliant/total*100:.1f}%)")

                    st.metric("Average Score", f"{results_df['overall_score'].mean():.1f}/100")

                    col1, col2 = st.columns(2)
                    with col1:
                        fig = go.Figure(data=[go.Pie(
                            labels=['Compliant', 'Minor Gaps', 'Non-Compliant'],
                            values=[compliant, minor_gaps, non_compliant],
                            marker=dict(colors=['#28a745', '#ffc107', '#dc3545'])
                        )])
                        fig.update_layout(title="Compliance Distribution")
                        st.plotly_chart(fig, use_container_width=True)

                    with col2:
                        avg_scores = {
                            'AML': results_df['aml_screening_score'].mean(),
                            'Identity': results_df['identity_verification_score'].mean(),
                            'Activity': results_df['account_activity_score'].mean(),
                            'PoA': results_df['proof_of_address_score'].mean(),
                            'UBO': results_df['beneficial_ownership_score'].mean(),
                            'Data Quality': results_df['data_quality_score'].mean()
                        }
                        fig = go.Figure(data=[go.Bar(
                            x=list(avg_scores.keys()), y=list(avg_scores.values()),
                            marker_color='rgba(102, 126, 234, 0.7)',
                            text=[f'{v:.1f}' for v in avg_scores.values()],
                            textposition='outside'
                        )])
                        fig.update_layout(title="Average Dimension Scores", yaxis_title="Score", height=400)
                        st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Top Performers")
                    st.dataframe(results_df.nlargest(10, 'overall_score')[
                        ['customer_id', 'overall_score', 'overall_status']
                    ], use_container_width=True, hide_index=True)

                    st.subheader("Risk Areas")
                    st.dataframe(results_df.nsmallest(10, 'overall_score')[
                        ['customer_id', 'overall_score', 'overall_status']
                    ], use_container_width=True, hide_index=True)

                    # Download button
                    csv_buf = io.StringIO()
                    results_df.to_csv(csv_buf, index=False)
                    st.download_button(
                        "⬇️ Download Full Results CSV",
                        csv_buf.getvalue(),
                        file_name=f"kyc_batch_results_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# ============================================================================
# TAB 3: SYSTEM INFO
# ============================================================================

with tab3:
    st.header("System Information")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Data Loaded")
        if st.session_state.engines_initialized and st.session_state.customers_df is not None:
            engine = st.session_state.kyc_engine
            st.metric("Customers", len(st.session_state.customers_df))
            st.metric("AML Screenings", len(engine.screenings) if engine.screenings is not None else 0)
            st.metric("ID Verifications", len(engine.id_verifications) if engine.id_verifications is not None else 0)
            st.metric("Transactions", len(engine.transactions) if engine.transactions is not None else 0)
        else:
            st.info("No data loaded yet.")

    with col2:
        st.subheader("🎯 KYC Dimensions")
        st.markdown("""
        1. **AML Screening** (25%) — Sanctions list checks
        2. **Identity Verification** (20%) — Document verification
        3. **Account Activity** (15%) — Transaction patterns
        4. **Proof of Address** (15%) — Address verification
        5. **Beneficial Ownership** (15%) — UBO documentation
        6. **Data Quality** (10%) — Data completeness
        """)

    st.divider()
    st.subheader("🚀 Platform")
    st.markdown("""
    **Hosting:** Railway | **Framework:** Streamlit | **Python:** 3.9+
    **API Keys:** Loaded from environment variables — zero manual setup on demo day.
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Evaluation", "Real-time")
    with col2:
        st.metric("Batch Size", "100 customers")
    with col3:
        st.metric("Data Source", "Uploaded or pre-loaded")

# ============================================================================
# TAB 4: DATA MANAGEMENT
# ============================================================================

with tab4:
    st.header("📁 Data Management")
    st.markdown("Upload your raw data files here. The platform will clean and load them automatically.")

    st.subheader("Upload Data Files")
    st.info("Upload CSV files for each dataset. Column names will be auto-normalized.")

    col1, col2 = st.columns(2)

    with col1:
        customers_file = st.file_uploader("👤 Customers CSV", type=['csv'], key="up_customers")
        screenings_file = st.file_uploader("🛡️ AML Screenings CSV", type=['csv'], key="up_screenings")
        id_file = st.file_uploader("🪪 ID Verifications CSV", type=['csv'], key="up_id")

    with col2:
        transactions_file = st.file_uploader("💳 Transactions CSV", type=['csv'], key="up_transactions")
        documents_file = st.file_uploader("📄 Documents CSV", type=['csv'], key="up_documents")
        ubo_file = st.file_uploader("🏢 Beneficial Ownership CSV", type=['csv'], key="up_ubo")

    st.divider()

    if st.button("🧹 Clean & Load Data into Engine", type="primary", use_container_width=True):

        uploaded = {
            'customers': customers_file,
            'screenings': screenings_file,
            'id_verifications': id_file,
            'transactions': transactions_file,
            'documents': documents_file,
            'beneficial_ownership': ubo_file,
        }

        has_any = any(f is not None for f in uploaded.values())

        if not has_any:
            st.error("Please upload at least the Customers CSV to proceed.")
        else:
            cleaned = {}
            preview_data = {}

            with st.spinner("Cleaning data..."):
                for dataset_name, file_obj in uploaded.items():
                    if file_obj is not None:
                        try:
                            df_raw = pd.read_csv(file_obj)
                            df_clean = clean_dataframe(df_raw, dataset_name)
                            cleaned[dataset_name] = df_clean
                            preview_data[dataset_name] = df_clean
                            st.success(f"✅ {dataset_name}: {len(df_clean)} rows cleaned")
                        except Exception as e:
                            st.error(f"❌ {dataset_name}: {str(e)}")

            if cleaned:
                # Save to temp dir
                with st.spinner("Saving cleaned files..."):
                    tmp_dir = save_to_temp_dir(cleaned)
                    st.info(f"Saved to temp directory: `{tmp_dir}`")

                # Reinitialize engine
                with st.spinner("Loading KYC Engine with new data..."):
                    engine, customers = load_engine(tmp_dir)
                    if engine is not None and customers is not None and len(customers) > 0:
                        st.session_state.kyc_engine = engine
                        st.session_state.customers_df = customers
                        st.session_state.engines_initialized = True
                        st.session_state.data_dir = tmp_dir
                        st.success(f"🎉 Engine loaded! {len(customers)} customers ready for evaluation.")
                        st.rerun()
                    else:
                        st.error("Engine failed to initialize. Check that your Customers CSV has a `customer_id` column.")

                # Previews
                st.subheader("Data Previews")
                for name, df in preview_data.items():
                    with st.expander(f"{name} ({len(df)} rows, {len(df.columns)} columns)"):
                        st.dataframe(df.head(5), use_container_width=True)

    st.divider()

    st.subheader("⬇️ Download Cleaned Files")
    st.markdown("After loading data, download the cleaned CSVs for backup.")

    if st.session_state.engines_initialized and st.session_state.data_dir:
        data_dir = Path(st.session_state.data_dir)
        csv_files = list(data_dir.glob("*.csv"))
        if csv_files:
            for csv_file in csv_files:
                df = pd.read_csv(csv_file)
                buf = io.StringIO()
                df.to_csv(buf, index=False)
                st.download_button(
                    f"⬇️ {csv_file.name}",
                    buf.getvalue(),
                    file_name=csv_file.name,
                    mime="text/csv",
                    key=f"dl_{csv_file.stem}"
                )
        else:
            st.info("No cleaned files available yet.")
    else:
        st.info("Load data first to enable downloads.")

# ============================================================================
# TAB 5: DOCUMENT OCR & AI ANALYSIS
# ============================================================================

with tab5:
    st.header("🔬 Document OCR & AI Analysis")
    st.markdown("Upload a compliance document image. The platform will extract text via Google Vision OCR, then analyze it with Claude AI.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📤 Upload Document")
        uploaded_image = st.file_uploader(
            "Upload document image",
            type=['png', 'jpg', 'jpeg', 'tiff', 'bmp', 'gif'],
            key="ocr_upload"
        )

        doc_type = st.selectbox("Document Type", [
            "Identity Document (Passport / ID)",
            "Proof of Address (Utility Bill / Bank Statement)",
            "Corporate Document",
            "Beneficial Ownership Declaration",
            "AML Screening Result",
            "Other"
        ])

        customer_id_ocr = st.text_input("Customer ID (optional, for linking)", placeholder="C00001")

        run_ocr = st.button("🔍 Run OCR + AI Analysis", type="primary", use_container_width=True)

    with col2:
        if uploaded_image:
            st.subheader("Preview")
            st.image(uploaded_image, use_column_width=True)

    if run_ocr and uploaded_image:
        # Step 1: Google Vision OCR
        with st.spinner("Running Google Vision OCR..."):
            try:
                from google.cloud import vision
                client = vision.ImageAnnotatorClient()

                image_bytes = uploaded_image.read()
                image = vision.Image(content=image_bytes)
                response = client.text_detection(image=image)

                if response.error.message:
                    st.error(f"Google Vision error: {response.error.message}")
                    extracted_text = ""
                else:
                    texts = response.text_annotations
                    extracted_text = texts[0].description if texts else ""
                    ocr_confidence = None
                    if response.full_text_annotation.pages:
                        confidences = [
                            block.confidence
                            for page in response.full_text_annotation.pages
                            for block in page.blocks
                        ]
                        ocr_confidence = sum(confidences) / len(confidences) if confidences else None

                    st.success(f"✅ OCR complete — {len(extracted_text)} characters extracted")

            except Exception as e:
                st.error(f"❌ OCR failed: {str(e)}")
                extracted_text = ""
                ocr_confidence = None

        if extracted_text:
            # Show raw OCR text
            with st.expander("📝 Raw OCR Text"):
                st.text_area("Extracted Text", extracted_text, height=200, disabled=True)

            if ocr_confidence is not None:
                st.metric("OCR Confidence", f"{ocr_confidence*100:.1f}%")

            # Step 2: Claude LLM Analysis
            with st.spinner("Sending to Claude AI for compliance analysis..."):
                try:
                    import anthropic
                    client_llm = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

                    system_prompt = """You are a KYC compliance specialist AI. 
Analyze extracted document text and return a structured JSON object with these fields:
{
  "document_type": "detected document type",
  "customer_name": "full name if found",
  "customer_id": "ID/reference number if found",
  "document_number": "document number if found",
  "date_of_birth": "DOB if found",
  "issue_date": "issue date if found",
  "expiry_date": "expiry date if found",
  "address": "address if found",
  "nationality": "nationality/country if found",
  "issuing_authority": "issuing body if found",
  "compliance_flags": ["list of compliance concerns if any"],
  "data_completeness": "percentage of key fields found (0-100)",
  "risk_indicators": ["any suspicious elements noted"],
  "extraction_summary": "brief 2-sentence summary of findings"
}
Return ONLY the JSON object. No preamble, no markdown fences."""

                    user_prompt = f"""Document Type Context: {doc_type}
Customer ID Context: {customer_id_ocr if customer_id_ocr else 'Not provided'}

Extracted OCR Text:
{extracted_text[:3000]}

Extract all compliance-relevant fields from this document text."""

                    response = client_llm.messages.create(
                        model="claude-opus-4-20250514",
                        max_tokens=1500,
                        messages=[{"role": "user", "content": user_prompt}],
                        system=system_prompt
                    )

                    raw_response = response.content[0].text.strip()

                    try:
                        analysis = json.loads(raw_response)
                        st.success("✅ AI Analysis complete")
                        st.subheader("🧠 AI Extraction Results")

                        # Key fields
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Document Type", analysis.get('document_type', 'Unknown'))
                        with col2:
                            st.metric("Data Completeness", f"{analysis.get('data_completeness', '?')}%")
                        with col3:
                            flags = analysis.get('compliance_flags', [])
                            st.metric("Compliance Flags", len(flags))

                        # Extracted fields table
                        fields = {
                            'Customer Name': analysis.get('customer_name'),
                            'Document Number': analysis.get('document_number'),
                            'Date of Birth': analysis.get('date_of_birth'),
                            'Issue Date': analysis.get('issue_date'),
                            'Expiry Date': analysis.get('expiry_date'),
                            'Address': analysis.get('address'),
                            'Nationality': analysis.get('nationality'),
                            'Issuing Authority': analysis.get('issuing_authority'),
                        }
                        fields_df = pd.DataFrame([
                            {'Field': k, 'Extracted Value': v or 'Not found'}
                            for k, v in fields.items()
                        ])
                        st.dataframe(fields_df, use_container_width=True, hide_index=True)

                        # Compliance flags
                        if flags:
                            st.warning("⚠️ Compliance Flags Detected:")
                            for flag in flags:
                                st.markdown(f"- {flag}")
                        else:
                            st.success("✅ No compliance flags detected")

                        # Risk indicators
                        risks = analysis.get('risk_indicators', [])
                        if risks:
                            st.error("🚨 Risk Indicators:")
                            for risk in risks:
                                st.markdown(f"- {risk}")

                        # Summary
                        st.subheader("📋 Summary")
                        st.info(analysis.get('extraction_summary', 'No summary available'))

                        # Full JSON download
                        analysis['ocr_text'] = extracted_text
                        analysis['document_type_context'] = doc_type
                        analysis['customer_id_context'] = customer_id_ocr
                        analysis['analysis_timestamp'] = datetime.now().isoformat()

                        st.download_button(
                            "⬇️ Download Full Analysis JSON",
                            json.dumps(analysis, indent=2),
                            file_name=f"ocr_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                            mime="application/json"
                        )

                    except json.JSONDecodeError:
                        st.warning("Could not parse JSON response — showing raw output:")
                        st.text_area("Raw AI Response", raw_response, height=300)

                except Exception as e:
                    st.error(f"❌ AI analysis failed: {str(e)}")
        else:
            st.warning("No text extracted from the image. Try a clearer image.")

    elif run_ocr and not uploaded_image:
        st.warning("Please upload an image first.")

# ============================================================================
# FOOTER
# ============================================================================

st.divider()
st.markdown(f"""
<div style='text-align: center; color: gray; font-size: 12px;'>
    Apexon KYC Compliance Platform | Railway Edition | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>
""", unsafe_allow_html=True)
