"""
config.py
---------
Single source for all pipeline configuration.

"""

from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration for KYC evaluation pipeline."""
    
    # PATHS
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    RAW_DATA_PATH: Path = None
    CLEAN_DATA_PATH: Path = None
    OUTPUT_PATH: Path = None
    
    # DATES 
    EVALUATION_DATE: datetime = datetime(2026, 4, 9)
    
    # LOGGING
    LOG_LEVEL: str = "INFO"
    
    # DATA PROCESSING 
    CHUNK_SIZE: int = 500
    CACHE_ENABLED: bool = True
    
    # VALIDATION THRESHOLDS
    ID_EXPIRY_WARNING_DAYS: int = 90
    KYC_REVIEW_FREQUENCY_MONTHS: int = 12
    
    def __post_init__(self):
        """Initialize derived paths and create directories."""
        # Set defaults if not provided
        if self.RAW_DATA_PATH is None:
            self.RAW_DATA_PATH = self.PROJECT_ROOT / "Data Raw"
        
        if self.CLEAN_DATA_PATH is None:
            self.CLEAN_DATA_PATH = self.PROJECT_ROOT / "Data Clean"
        
        if self.OUTPUT_PATH is None:
            self.OUTPUT_PATH = self.PROJECT_ROOT / "Output"
        
        # Create directories if they don't exist
        self.CLEAN_DATA_PATH.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> bool:
        """Check that required data paths exist."""
        if not self.RAW_DATA_PATH.exists():
            raise FileNotFoundError(f"Raw data path missing: {self.RAW_DATA_PATH}")
        return True
    
    def to_dict(self) -> dict:
        """Export config as dictionary (useful for logging)."""
        return {
            'PROJECT_ROOT': str(self.PROJECT_ROOT),
            'RAW_DATA_PATH': str(self.RAW_DATA_PATH),
            'CLEAN_DATA_PATH': str(self.CLEAN_DATA_PATH),
            'OUTPUT_PATH': str(self.OUTPUT_PATH),
            'EVALUATION_DATE': self.EVALUATION_DATE.isoformat(),
            'LOG_LEVEL': self.LOG_LEVEL,
            'CHUNK_SIZE': self.CHUNK_SIZE,
        }


# Default instance
config = Config()

if __name__ == "__main__":
    # Quick test
    cfg = Config()
    cfg.validate()
    print("✓ Config loaded successfully!")
    print(f"  PROJECT_ROOT: {cfg.PROJECT_ROOT}")
    print(f"  EVALUATION_DATE: {cfg.EVALUATION_DATE}")
    print(f"  RAW_DATA_PATH: {cfg.RAW_DATA_PATH}")
    print(f"  CLEAN_DATA_PATH: {cfg.CLEAN_DATA_PATH}")
