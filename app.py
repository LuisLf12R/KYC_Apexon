"""
app.py
KYC Compliance Dashboard for Vercel
- Streamlit on Vercel
- API keys from environment variables
- Same setup as weiss-demo
- Zero local setup on demo day

Deploy to Vercel:
1. Push to GitHub
2. Connect to Vercel
3. Add environment variables
4. Auto-deploy!

Usage locally:
    pip install streamlit pandas plotly anthropic google-cloud-vision python-dotenv
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys
import os
from datetime import datetime
import plotly.graph_objects as go
from dotenv import load_dotenv
import base64

# Load .env file (for local testing)
load_dotenv()

# Page config
st.set_page_config(
    page_title="KYC Compliance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INITIALIZE API KEYS FROM ENVIRONMENT
# ============================================================================

@st.cache_resource
def init_api_keys():
    """Initialize API keys from environment variables."""
    try:
        # Claude API key
        claude_key = os.getenv('ANTHROPIC_API_KEY')
        if not claude_key:
            return False, "ANTHROPIC_API_KEY not configured"
        
        os.environ['ANTHROPIC_API_KEY'] = claude_key
        
        # Google Vision API - try multiple approaches
        google_key_json = None
        
        # Approach 1: Direct JSON path (local testing)
        google_path = os.getenv('GOOGLE_VISION_JSON_PATH')
        if google_path and Path(google_path).exists():
            with open(google_path) as f:
                google_key_json = json.load(f)
        
        # Approach 2: Base64 encoded JSON (Vercel recommended)
        if not google_key_json:
            google_base64 = os.getenv('GOOGLE_VISION_JSON_BASE64')
            if google_base64:
                try:
                    decoded = base64.b64decode(google_base64).decode('utf-8')
                    google_key_json = json.loads(decoded)
                except Exception as e:
                    return False, f"Invalid base64 Google Vision key: {str(e)}"
        
        # Approach 3: Direct JSON string (alternative)
        if not google_key_json:
            google_json = os.getenv('GOOGLE_VISION_JSON')
            if google_json:
                try:
                    google_key_json = json.loads(google_json)
                except Exception as e:
                    return False, f"Invalid JSON Google Vision key: {str(e)}"
        
        if not google_key_json:
            return False, "Google Vision API key not configured"
        
        # Write Google credentials to temp file
        creds_path = Path.home() / '.kyc_google_creds.json'
        with open(creds_path, 'w') as f:
            json.dump(google_key_json, f)
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(creds_path)
        
        return True, "API keys loaded successfully"
    
    except Exception as e:
        return False, f"Error loading API keys: {str(e)}"


# Initialize keys
keys_ok, keys_msg = init_api_keys()

if not keys_ok:
    st.error(f"❌ Configuration Error: {keys_msg}")
    st.warning("""
    **For Local Testing:**
    Create a `.env` file with:
    ```
    ANTHROPIC_API_KEY=sk-ant-...
    GOOGLE_VISION_JSON_PATH=/path/to/service-account.json
    ```
    
    **For Vercel:**
    Add environment variables in Vercel dashboard:
    - ANTHROPIC_API_KEY
    - GOOGLE_VISION_JSON_BASE64 (base64-encoded JSON)
    """)
    st.stop()

# ============================================================================
# SESSION STATE & INITIALIZATION
# ============================================================================

if 'kyc_engine' not in st.session_state:
    st.session_state.kyc_engine = None

if 'engines_initialized' not in st.session_state:
    st.session_state.engines_initialized = False

if 'customers_df' not in st.session_state:
    st.session_state.customers_df = None


@st.cache_resource
def init_kyc_engine():
    """Initialize KYC engine with API keys from environment."""
    try:
        sys.path.insert(0, str(Path.cwd() / 'src'))
        from kyc_engine import KYCComplianceEngine
        
        data_clean = Path.cwd() / 'Data Clean'
        if not data_clean.exists():
            st.error(f"❌ Data Clean directory not found at {data_clean}")
            return None, None
        
        engine = KYCComplianceEngine(data_clean_dir=data_clean)
        return engine, engine.customers
    
    except Exception as e:
        st.error(f"❌ Failed to initialize KYC engine: {str(e)}")
        return None, None


# Initialize on load
with st.spinner("Initializing KYC Engine..."):
    engine, customers = init_kyc_engine()
    if engine:
        st.session_state.kyc_engine = engine
        st.session_state.customers_df = customers
        st.session_state.engines_initialized = True


# ============================================================================
# SIDEBAR - STATUS & INFO
# ============================================================================

with st.sidebar:
    st.title("⚙️ System Status")
    
    if st.session_state.engines_initialized:
        st.success("✅ System Ready")
        if st.session_state.customers_df is not None:
            st.info(f"📊 {len(st.session_state.customers_df)} customers loaded")
            st.metric("Data Source", "Codex Generated")
            st.metric("API Keys", "✅ Configured")
    else:
        st.error("❌ System Not Ready")
    
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
    st.markdown("""
    **Running on:** Vercel
    
    **API Keys:**
    ✅ Claude (Anthropic)
    ✅ Google Vision
    
    Configured via environment variables
    No manual setup!
    """)


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

st.title("🏦 KYC Compliance Dashboard")
st.markdown("Production Edition - Real-time Compliance Evaluation")

if not st.session_state.engines_initialized:
    st.error("""
    ❌ System not initialized. Please ensure:
    1. Environment variables are set
    2. `Data Clean/` folder has CSV files
    3. `src/kyc_engine.py` exists
    """)

else:
    # Tabs
    tab1, tab2, tab3 = st.tabs(["Individual Evaluation", "Batch Results", "System Info"])
    
    # ========================================================================
    # TAB 1: INDIVIDUAL CUSTOMER EVALUATION
    # ========================================================================
    
    with tab1:
        st.header("Search & Evaluate Customer")
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            customer_id = st.text_input(
                "Enter Customer ID",
                placeholder="C00001",
                key="customer_search"
            )
        
        with col2:
            search_button = st.button("🔍 Evaluate", use_container_width=True)
        
        if search_button and customer_id:
            customer_id = customer_id.upper()
            
            with st.spinner(f"Evaluating {customer_id}..."):
                try:
                    result = st.session_state.kyc_engine.evaluate_customer(customer_id)
                    
                    # Overall Score Card
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            "Overall Score",
                            f"{result['overall_score']}/100",
                            delta=f"Status: {result['overall_status']}"
                        )
                    
                    with col2:
                        st.metric(
                            "Entity Type",
                            result.get('entity_type', 'N/A')
                        )
                    
                    with col3:
                        st.metric(
                            "Risk Rating",
                            result.get('risk_rating', 'N/A')
                        )
                    
                    # Status Badge
                    status = result['overall_status']
                    if status == 'Compliant':
                        st.success(f"✅ {status}")
                    elif 'Minor' in status:
                        st.warning(f"⚠️ {status}")
                    else:
                        st.error(f"❌ {status}")
                    
                    # Dimension Scores
                    st.subheader("Dimension Breakdown")
                    
                    dimensions_data = {
                        'Dimension': [
                            'AML Screening',
                            'Identity Verification',
                            'Account Activity',
                            'Proof of Address',
                            'Beneficial Ownership',
                            'Data Quality'
                        ],
                        'Score': [
                            result['aml_screening_score'],
                            result['identity_verification_score'],
                            result['account_activity_score'],
                            result['proof_of_address_score'],
                            result['beneficial_ownership_score'],
                            result['data_quality_score']
                        ],
                        'Weight': [25, 20, 15, 15, 15, 10],
                        'Details': [
                            result['aml_screening_details'].get('finding', 'N/A'),
                            result['identity_verification_details'].get('finding', 'N/A'),
                            result['account_activity_details'].get('finding', 'N/A'),
                            result['proof_of_address_details'].get('finding', 'N/A'),
                            result['beneficial_ownership_details'].get('finding', 'N/A'),
                            result['data_quality_details'].get('finding', 'N/A')
                        ]
                    }
                    
                    dimensions_df = pd.DataFrame(dimensions_data)
                    
                    # Dimension Charts
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig = go.Figure(data=[
                            go.Bar(
                                x=dimensions_df['Dimension'],
                                y=dimensions_df['Score'],
                                marker_color=['#28a745' if x >= 70 else '#ffc107' if x >= 50 else '#dc3545' for x in dimensions_df['Score']],
                                text=dimensions_df['Score'],
                                textposition='outside'
                            )
                        ])
                        fig.update_layout(
                            title="Dimension Scores",
                            yaxis_title="Score",
                            xaxis_title="",
                            height=400,
                            xaxis_tickangle=-45
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        fig = go.Figure(data=[
                            go.Pie(
                                labels=['Compliant', 'Minor Gaps', 'Non-Compliant'],
                                values=[
                                    100 if status == 'Compliant' else 0,
                                    100 if 'Minor' in status else 0,
                                    100 if 'Non' in status else 0
                                ],
                                marker=dict(colors=['#28a745', '#ffc107', '#dc3545'])
                            )
                        ])
                        fig.update_layout(
                            title="Compliance Status",
                            height=400
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Detailed Findings Table
                    st.subheader("Detailed Findings")
                    st.dataframe(
                        dimensions_df[['Dimension', 'Score', 'Weight', 'Details']],
                        use_container_width=True,
                        hide_index=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ Error evaluating customer: {str(e)}")
    
    # ========================================================================
    # TAB 2: BATCH RESULTS
    # ========================================================================
    
    with tab2:
        st.header("Batch Compliance Results")
        
        if st.button("📊 Load Batch Results", use_container_width=True):
            with st.spinner("Evaluating batch..."):
                try:
                    # Try to load pre-computed results
                    results_file = Path.cwd() / 'Data Clean' / 'batch_results_demo.csv'
                    
                    if results_file.exists():
                        results_df = pd.read_csv(results_file)
                    else:
                        # Run evaluation on first 100 customers
                        customer_ids = st.session_state.customers_df['customer_id'].head(100).tolist()
                        results_df = st.session_state.kyc_engine.evaluate_batch(customer_ids)
                    
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    total = len(results_df)
                    compliant = len(results_df[results_df['overall_status'] == 'Compliant'])
                    minor_gaps = len(results_df[results_df['overall_status'] == 'Compliant with Minor Gaps'])
                    non_compliant = len(results_df[results_df['overall_status'] == 'Non-Compliant'])
                    
                    with col1:
                        st.metric("Total Evaluated", total)
                    
                    with col2:
                        st.metric("✅ Compliant", f"{compliant} ({compliant/total*100:.1f}%)")
                    
                    with col3:
                        st.metric("⚠️ Minor Gaps", f"{minor_gaps} ({minor_gaps/total*100:.1f}%)")
                    
                    with col4:
                        st.metric("❌ Non-Compliant", f"{non_compliant} ({non_compliant/total*100:.1f}%)")
                    
                    st.metric("Average Score", f"{results_df['overall_score'].mean():.1f}/100")
                    
                    # Compliance Distribution
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig = go.Figure(data=[
                            go.Pie(
                                labels=['Compliant', 'Minor Gaps', 'Non-Compliant'],
                                values=[compliant, minor_gaps, non_compliant],
                                marker=dict(colors=['#28a745', '#ffc107', '#dc3545'])
                            )
                        ])
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
                        
                        fig = go.Figure(data=[
                            go.Bar(
                                x=list(avg_scores.keys()),
                                y=list(avg_scores.values()),
                                marker_color='rgba(102, 126, 234, 0.7)',
                                text=[f'{v:.1f}' for v in avg_scores.values()],
                                textposition='outside'
                            )
                        ])
                        fig.update_layout(
                            title="Average Dimension Scores",
                            yaxis_title="Score",
                            height=400
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Results Table
                    st.subheader("Top Performers")
                    top_performers = results_df.nlargest(10, 'overall_score')[
                        ['customer_id', 'overall_score', 'overall_status']
                    ]
                    st.dataframe(top_performers, use_container_width=True, hide_index=True)
                    
                    st.subheader("Risk Areas")
                    risk_areas = results_df.nsmallest(10, 'overall_score')[
                        ['customer_id', 'overall_score', 'overall_status']
                    ]
                    st.dataframe(risk_areas, use_container_width=True, hide_index=True)
                
                except Exception as e:
                    st.error(f"❌ Error loading batch results: {str(e)}")
    
    # ========================================================================
    # TAB 3: SYSTEM INFO
    # ========================================================================
    
    with tab3:
        st.header("System Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Data Loaded")
            if st.session_state.customers_df is not None:
                st.metric("Customers", len(st.session_state.customers_df))
                st.metric("AML Screenings", len(st.session_state.kyc_engine.screenings))
                st.metric("ID Verifications", len(st.session_state.kyc_engine.id_verifications))
                st.metric("Transactions", len(st.session_state.kyc_engine.transactions))
        
        with col2:
            st.subheader("🎯 KYC Dimensions")
            st.markdown("""
            1. **AML Screening** (25%)
               Sanctions list checks
            
            2. **Identity Verification** (20%)
               Document verification
            
            3. **Account Activity** (15%)
               Transaction patterns
            
            4. **Proof of Address** (15%)
               Address verification
            
            5. **Beneficial Ownership** (15%)
               UBO documentation
            
            6. **Data Quality** (10%)
               Data completeness
            """)
        
        st.divider()
        
        st.subheader("🚀 Platform")
        st.markdown("""
        **Hosting:**
        - Vercel (https://vercel.com/)
        
        **Framework:**
        - Streamlit
        - Python 3.9+
        
        **Configuration:**
        - API keys from environment variables
        - Credentials auto-loaded
        - Zero setup needed on demo day!
        """)
        
        st.subheader("📈 Performance")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Evaluation", "Real-time")
        with col2:
            st.metric("Batch Size", "5,120")
        with col3:
            st.metric("Cost", "Free (Vercel)")


# ============================================================================
# FOOTER
# ============================================================================

st.divider()
st.markdown(f"""
<div style='text-align: center; color: gray; font-size: 12px;'>
    Apexon KYC Compliance Platform | Vercel Edition | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>
""", unsafe_allow_html=True)
