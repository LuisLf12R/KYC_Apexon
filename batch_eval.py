from pathlib import Path
import pandas as pd
from src.data_loader import DataLoader
from src.dimensions import ALL_DIMENSIONS

print("[*] Loading...")
loader = DataLoader(Path(__file__).parent)
data = loader.load_all()
customers = data['customers']
print(f"[OK] {len(customers):,} customers\n")

print("="*70)
print("BATCH EVALUATION - ALL 6 DIMENSIONS")
print("="*70)

results = []
for i, dim in enumerate(ALL_DIMENSIONS, 1):
    print(f"\n[{i}] {dim.__class__.__name__}...")
    dim_results = dim.batch_evaluate(customers['customer_id'].values[:100], data)
    results.extend(dim_results)
    passed = sum(1 for r in dim_results if r.get('passed'))
    print(f"    Evaluated 100 | Passed: {passed}/100")

results_df = pd.DataFrame(results)

print("\n" + "="*70)
print("DIMENSION SUMMARY")
print("="*70)

for dim in results_df['dimension'].unique():
    d = results_df[results_df['dimension'] == dim]
    p = d['passed'].sum()
    f = (~d['passed']).sum()
    pct = (p / len(d)) * 100 if len(d) > 0 else 0
    print(f"\n{dim:30s} | Pass: {p:3d} | Fail: {f:3d} | {pct:5.1f}%")

output_file = Path(__file__).parent / 'batch_results_sample.csv'
results_df.to_csv(output_file, index=False)
print(f"\n[OK] Results saved to batch_results_sample.csv")
print("[DONE]")
