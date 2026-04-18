"""
Backward-compatible module path for LLMCodeGenerator.

Historically, callers imported:
    from llm_integration.llm_code_generator import LLMCodeGenerator

The implementation currently lives in llm_code_generator_v1_BACKUP.py.
This shim preserves the stable import path expected by src/schema_harmonizer.py
and containerized runtime entrypoints.
"""

from .llm_code_generator_v1_BACKUP import GeneratedScript, LLMCodeGenerator

__all__ = ["GeneratedScript", "LLMCodeGenerator"]
