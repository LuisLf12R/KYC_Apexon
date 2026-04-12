from pathlib import Path
import pandas as pd
import json
import sys
import traceback

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
print("DEBUG: Running first customer (C001) through all dimensions")
print("="*70)

cid = customers['customer_id'].iloc[0]
print(f"\nTesting customer: {cid}\n")

for dim in ALL_DIMENSIONS:
    print(f"\n[*] {dim.__class__.__name__}...")
    try:
        result = dim.evaluate(cid, data)
        print(f"    Passed: {result.get('passed')}")
        if not result.get('passed'):
            findings = result.get('findings', [])
            for f in findings[:3]:
                print(f"      {f}")
    except Exception as e:
        print(f"    ERROR: {e}")
        traceback.print_exc()
