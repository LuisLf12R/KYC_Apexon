from src.kyc_input_orchestrator import KYCInputOrchestrator
from pathlib import Path

orch = KYCInputOrchestrator(project_root=Path.cwd())
print("Success!")
print(f"Cache stats: {orch.get_extraction_stats()}")