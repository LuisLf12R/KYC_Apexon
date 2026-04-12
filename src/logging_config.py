"""
logging_config.py
-----------------
Structured logging setup for the pipeline.
"""

import logging


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """
    Configure structured logging.
    
    Usage:
        from src.logging_config import setup_logging
        logger = setup_logging("INFO")
        logger.info("Pipeline started")
    """
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers (avoid duplicates)
    root_logger.handlers = []
    
    # Add console handler
    root_logger.addHandler(console_handler)
    
    # Optional: file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


if __name__ == "__main__":
    # Test logging
    logger = setup_logging("INFO")
    logger.info("✓ Logging configured")
    logger.debug("This is a debug message")
    logger.warning("This is a warning")
