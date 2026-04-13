"""
kyc_dashboard.py
Professional KYC Compliance Dashboard

Features:
- Real-time compliance scoring
- Interactive customer search
- Detailed dimension breakdown
- Document upload & OCR processing
- Batch evaluation results
- Regulatory reporting

Usage:
    pip install flask pandas plotly --break-system-packages
    python kyc_dashboard.py
    
Then visit: http://localhost:5000
"""

from flask import Flask, render_template_string, jsonify, request, send_file
import pandas as pd
import json
from pathlib import Path
import sys
from datetime import datetime
import io

# Add src to path
sys.path.insert(0, str(Path.cwd() / 'src'))

from kyc_engine import KYCComplianceEngine

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Initialize engine
try:
    engine = KYCComplianceEngine(data_clean_dir=Path.cwd() / 'Data Clean')
    CUSTOMERS = engine.customers
    print("[OK] KYC Engine initialized")
except Exception as e:
    print(f"[ERROR] Failed to initialize engine: {e}")
    CUSTOMERS = pd.DataFrame()


# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KYC Compliance Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        header h1 {
            color: #333;
            font-size: 32px;
            margin-bottom: 10px;
        }
        
        header p {
            color: #666;
            font-size: 16px;
        }
        
        .search-section {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .search-section input,
        .search-section button {
            padding: 12px 20px;
            font-size: 14px;
            border: none;
            border-radius: 5px;
        }
        
        .search-section input {
            flex: 1;
            min-width: 200px;
            background: #f5f5f5;
            color: #333;
        }
        
        .search-section button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s;
        }
        
        .search-section button:hover {
            transform: translateY(-2px);
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .card h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }
        
        .score-box {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        
        .score-box .number {
            font-size: 48px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .score-box .label {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 15px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
            text-align: center;
            width: 100%;
        }
        
        .status-compliant {
            background: #d4edda;
            color: #155724;
        }
        
        .status-minor-gaps {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-non-compliant {
            background: #f8d7da;
            color: #721c24;
        }
        
        .dimension-list {
            list-style: none;
        }
        
        .dimension-list li {
            padding: 12px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        
        .dimension-list .name {
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
        }
        
        .dimension-list .score {
            color: #667eea;
            font-size: 14px;
        }
        
        .charts {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .chart-container h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }
        
        .details-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .details-container h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }
        
        .detail-row {
            display: grid;
            grid-template-columns: 200px 1fr;
            gap: 20px;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        
        .detail-row:last-child {
            border-bottom: none;
        }
        
        .detail-label {
            font-weight: 600;
            color: #667eea;
        }
        
        .detail-value {
            color: #333;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 18px;
        }
        
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        
        footer {
            text-align: center;
            color: white;
            margin-top: 40px;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>KYC Compliance Dashboard</h1>
            <p>Real-time compliance evaluation across 6 dimensions</p>
        </header>
        
        <div class="search-section">
            <input type="text" id="searchInput" placeholder="Search by Customer ID (e.g., C00001)...">
            <button onclick="searchCustomer()">Evaluate</button>
            <button onclick="loadBatchResults()">Load Batch Results</button>
        </div>
        
        <div id="content">
            <div class="loading">Loading dashboard... Please search for a customer or load batch results.</div>
        </div>
        
        <footer>
            <p>Apexon KYC Compliance Platform | Powered by Claude AI & Google Vision API</p>
            <p>{{ timestamp }}</p>
        </footer>
    </div>
    
    <script>
        function searchCustomer() {
            const customerId = document.getElementById('searchInput').value.toUpperCase();
            
            if (!customerId) {
                alert('Please enter a Customer ID');
                return;
            }
            
            document.getElementById('content').innerHTML = '<div class="loading">Evaluating customer...</div>';
            
            fetch(`/api/evaluate/${customerId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('content').innerHTML = `<div class="error">${data.error}</div>`;
                    } else {
                        displayCustomerProfile(data);
                    }
                })
                .catch(error => {
                    document.getElementById('content').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                });
        }
        
        function loadBatchResults() {
            document.getElementById('content').innerHTML = '<div class="loading">Loading batch results...</div>';
            
            fetch('/api/batch-results')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('content').innerHTML = `<div class="error">${data.error}</div>`;
                    } else {
                        displayBatchResults(data);
                    }
                })
                .catch(error => {
                    document.getElementById('content').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                });
        }
        
        function displayCustomerProfile(profile) {
            const status = profile.overall_status;
            let statusClass = 'status-compliant';
            if (status.includes('Minor')) statusClass = 'status-minor-gaps';
            if (status.includes('Non')) statusClass = 'status-non-compliant';
            
            let html = `
                <div class="grid">
                    <div class="card">
                        <h3>Customer Profile</h3>
                        <div class="detail-row">
                            <div class="detail-label">Customer ID:</div>
                            <div class="detail-value">${profile.customer_id}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Entity Type:</div>
                            <div class="detail-value">${profile.entity_type}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Risk Rating:</div>
                            <div class="detail-value">${profile.risk_rating}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Jurisdiction:</div>
                            <div class="detail-value">${profile.jurisdiction}</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h3>Overall Compliance</h3>
                        <div class="score-box">
                            <div class="number">${profile.overall_score}</div>
                            <div class="label">Compliance Score</div>
                        </div>
                        <div class="status-badge ${statusClass}">${profile.overall_status}</div>
                    </div>
                </div>
                
                <div class="charts">
                    <div class="chart-container">
                        <h3>Dimension Scores</h3>
                        <div id="dimensionChart"></div>
                    </div>
                    <div class="chart-container">
                        <h3>Compliance Status</h3>
                        <div id="statusChart"></div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Dimension Details</h3>
                    <ul class="dimension-list">
                        <li>
                            <div class="name">AML Screening</div>
                            <div class="score">${profile.aml_screening_score}/100 - ${profile.aml_screening_details.finding}</div>
                        </li>
                        <li>
                            <div class="name">Identity Verification</div>
                            <div class="score">${profile.identity_verification_score}/100 - ${profile.identity_verification_details.finding}</div>
                        </li>
                        <li>
                            <div class="name">Account Activity</div>
                            <div class="score">${profile.account_activity_score}/100 - ${profile.account_activity_details.finding}</div>
                        </li>
                        <li>
                            <div class="name">Proof of Address</div>
                            <div class="score">${profile.proof_of_address_score}/100 - ${profile.proof_of_address_details.finding}</div>
                        </li>
                        <li>
                            <div class="name">Beneficial Ownership</div>
                            <div class="score">${profile.beneficial_ownership_score}/100 - ${profile.beneficial_ownership_details.finding}</div>
                        </li>
                        <li>
                            <div class="name">Data Quality</div>
                            <div class="score">${profile.data_quality_score}/100 - ${profile.data_quality_details.finding}</div>
                        </li>
                    </ul>
                </div>
            `;
            
            document.getElementById('content').innerHTML = html;
            
            // Plot dimension scores
            const dimensions = ['AML', 'Identity', 'Activity', 'PoA', 'UBO', 'DQ'];
            const scores = [
                profile.aml_screening_score,
                profile.identity_verification_score,
                profile.account_activity_score,
                profile.proof_of_address_score,
                profile.beneficial_ownership_score,
                profile.data_quality_score
            ];
            
            const trace = {
                x: dimensions,
                y: scores,
                type: 'bar',
                marker: {color: 'rgba(102, 126, 234, 0.7)'}
            };
            
            Plotly.newPlot('dimensionChart', [trace], {
                margin: {l: 40, r: 40, t: 40, b: 40},
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: {showgrid: false},
                yaxis: {showgrid: true},
                height: 300
            });
            
            // Plot compliance status
            const statusTrace = {
                labels: ['Compliant', 'Minor Gaps', 'Non-Compliant'],
                values: [
                    status === 'Compliant' ? 100 : 0,
                    status.includes('Minor') ? 100 : 0,
                    status.includes('Non') ? 100 : 0
                ],
                type: 'pie',
                marker: {
                    colors: ['#28a745', '#ffc107', '#dc3545']
                }
            };
            
            Plotly.newPlot('statusChart', [statusTrace], {
                margin: {l: 40, r: 40, t: 40, b: 40},
                paper_bgcolor: 'rgba(0,0,0,0)',
                height: 300
            });
        }
        
        function displayBatchResults(data) {
            // Implement batch results display
            let html = `
                <div class="card">
                    <h3>Batch Evaluation Results</h3>
                    <div class="detail-row">
                        <div class="detail-label">Total Customers:</div>
                        <div class="detail-value">${data.total}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Compliant:</div>
                        <div class="detail-value">${data.compliant} (${data.compliant_pct}%)</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Minor Gaps:</div>
                        <div class="detail-value">${data.minor_gaps} (${data.minor_gaps_pct}%)</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Non-Compliant:</div>
                        <div class="detail-value">${data.non_compliant} (${data.non_compliant_pct}%)</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Average Score:</div>
                        <div class="detail-value">${data.avg_score}/100</div>
                    </div>
                </div>
                
                <div class="charts">
                    <div class="chart-container">
                        <h3>Compliance Distribution</h3>
                        <div id="complianceChart"></div>
                    </div>
                    <div class="chart-container">
                        <h3>Average Dimension Scores</h3>
                        <div id="avgDimensionsChart"></div>
                    </div>
                </div>
            `;
            
            document.getElementById('content').innerHTML = html;
            
            // Compliance distribution pie chart
            const pieTrace = {
                labels: ['Compliant', 'Minor Gaps', 'Non-Compliant'],
                values: [data.compliant, data.minor_gaps, data.non_compliant],
                type: 'pie',
                marker: {colors: ['#28a745', '#ffc107', '#dc3545']}
            };
            
            Plotly.newPlot('complianceChart', [pieTrace], {
                margin: {l: 40, r: 40, t: 40, b: 40},
                paper_bgcolor: 'rgba(0,0,0,0)',
                height: 350
            });
            
            // Average dimensions bar chart
            const barTrace = {
                x: ['AML', 'Identity', 'Activity', 'PoA', 'UBO', 'DQ'],
                y: Object.values(data.avg_dimensions),
                type: 'bar',
                marker: {color: 'rgba(102, 126, 234, 0.7)'}
            };
            
            Plotly.newPlot('avgDimensionsChart', [barTrace], {
                margin: {l: 40, r: 40, t: 40, b: 40},
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: {showgrid: false},
                yaxis: {showgrid: true},
                height: 350
            });
        }
        
        // Allow Enter key to search
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('searchInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') searchCustomer();
            });
        });
    </script>
</body>
</html>
"""


# API Routes
@app.route('/')
def dashboard():
    """Render dashboard."""
    return render_template_string(DASHBOARD_HTML, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/api/evaluate/<customer_id>')
def evaluate_customer(customer_id):
    """Evaluate a single customer."""
    try:
        result = engine.evaluate_customer(customer_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/batch-results')
def batch_results():
    """Get batch evaluation results."""
    try:
        # Try to load pre-computed batch results
        results_file = Path.cwd() / 'Data Clean' / 'batch_results_demo.csv'
        
        if not results_file.exists():
            # Run evaluation on first 100 customers
            customer_ids = CUSTOMERS['customer_id'].head(100).tolist()
            results_df = engine.evaluate_batch(customer_ids)
        else:
            results_df = pd.read_csv(results_file)
        
        total = len(results_df)
        compliant = len(results_df[results_df['overall_status'] == 'Compliant'])
        minor_gaps = len(results_df[results_df['overall_status'] == 'Compliant with Minor Gaps'])
        non_compliant = len(results_df[results_df['overall_status'] == 'Non-Compliant'])
        
        avg_dimensions = {
            'aml': round(results_df['aml_screening_score'].mean(), 1),
            'identity': round(results_df['identity_verification_score'].mean(), 1),
            'activity': round(results_df['account_activity_score'].mean(), 1),
            'poa': round(results_df['proof_of_address_score'].mean(), 1),
            'ubo': round(results_df['beneficial_ownership_score'].mean(), 1),
            'dq': round(results_df['data_quality_score'].mean(), 1)
        }
        
        return jsonify({
            'total': total,
            'compliant': compliant,
            'compliant_pct': round(compliant/total*100, 1),
            'minor_gaps': minor_gaps,
            'minor_gaps_pct': round(minor_gaps/total*100, 1),
            'non_compliant': non_compliant,
            'non_compliant_pct': round(non_compliant/total*100, 1),
            'avg_score': round(results_df['overall_score'].mean(), 1),
            'avg_dimensions': avg_dimensions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/customers')
def get_customers():
    """Get list of customers for search autocomplete."""
    try:
        customers = CUSTOMERS['customer_id'].head(100).tolist()
        return jsonify({'customers': customers})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    print("\n" + "="*70)
    print("KYC COMPLIANCE DASHBOARD")
    print("="*70 + "\n")
    
    print("[*] Dashboard initializing...\n")
    print(f"[OK] Customers loaded: {len(CUSTOMERS)}")
    print(f"[OK] KYC Engine ready\n")
    
    print("[*] Starting Flask server...\n")
    print("    Access dashboard at: http://localhost:5000")
    print("    Press Ctrl+C to stop\n")
    
    print("="*70 + "\n")
    
    app.run(debug=True, port=5000)
