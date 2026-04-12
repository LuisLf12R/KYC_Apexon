from pathlib import Path
import pandas as pd
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))

DATA_ROOT = Path(__file__).parent / 'Data Clean'

print("[*] Loading data...")
customers = pd.read_csv(DATA_ROOT / 'customers_clean.csv')
id_verifications = pd.read_csv(DATA_ROOT / 'id_verifications_clean.csv')
documents = pd.read_csv(DATA_ROOT / 'documents_clean.csv')
screenings = pd.read_csv(DATA_ROOT / 'screenings_clean.csv')
transactions = pd.read_csv(DATA_ROOT / 'transactions_clean.csv')

with open(Path(__file__).parent / 'Data Raw' / 'ubo.json') as f:
    ubo = json.load(f)

data = {
    'customers': customers,
    'id_verifications': id_verifications,
    'documents': documents,
    'screenings': screenings,
    'transactions': transactions,
    'ubo': ubo,
}

print(f"[OK] Loaded {len(customers):,} customers\n")

from src.dimensions import ALL_DIMENSIONS

print("="*70)
print("BATCH EVALUATION - ALL 6 DIMENSIONS")
print("="*70)

results = []
sample_ids = customers['customer_id'].values[:100]

for i, dim in enumerate(ALL_DIMENSIONS, 1):
    print(f"\n[{i}] {dim.__class__.__name__}...")
    for cid in sample_ids:
        result = dim.evaluate(cid, data)
        results.append(result)
    
    dim_results = [r for r in results if r['dimension'] == dim.__class__.__name__]
    passed = sum(1 for r in dim_results if r.get('passed'))
    print(f"    Evaluated {len(dim_results)} | Passed: {passed}")

results_df = pd.DataFrame(results)

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

for dim in sorted(results_df['dimension'].unique()):
    d = results_df[results_df['dimension'] == dim]
    p = d['passed'].sum()
    f = (~d['passed']).sum()
    pct = (p / len(d)) * 100 if len(d) > 0 else 0
    print(f"{dim:35s} | {p:3d}/{len(d):3d} passed ({pct:5.1f}%)")

output_file = Path(__file__).parent / 'batch_results.csv'
results_df.to_csv(output_file, index=False)
print(f"\n[OK] Saved to batch_results.csv")
