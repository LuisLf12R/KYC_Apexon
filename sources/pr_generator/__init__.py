"""KYC PR generator — diffs staged overlays, runs regression gate, emits PR description."""
from .pr_generator import generate_pr

__all__ = ["generate_pr"]
