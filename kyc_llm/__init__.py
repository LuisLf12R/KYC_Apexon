from .ocr_handler import OCRHandler

try:
    from .execution_engine import ExecutionEngine
except ImportError:
    ExecutionEngine = None  # llm_integration module not present; ocr_extractor_v2 used directly

__all__ = ["OCRHandler", "ExecutionEngine"]
