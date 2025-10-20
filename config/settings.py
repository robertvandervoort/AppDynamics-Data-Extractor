"""
Configuration settings for AppDynamics Data Extractor.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    """Application configuration settings."""
    # Debug settings
    debug: bool = False
    snes_sounds: bool = False
    
    # API settings
    verify_ssl: bool = True
    token_expiration: int = 300
    expiration_buffer: int = 30
    
    # Data processing settings
    normalize_data: bool = True
    metric_rollup: str = "false"
    
    # Default durations (in minutes)
    default_apm_metric_duration: int = 60
    default_machine_metric_duration: int = 60
    default_snapshot_duration: int = 60
    
    # Snapshot settings
    first_in_chain: bool = True
    need_exit_calls: bool = False
    need_props: bool = False
    
    # Output settings
    keep_status_open: bool = False


@dataclass
class APICredentials:
    """API credentials for AppDynamics."""
    account_name: str
    api_client: str
    api_secret: str
    base_url: Optional[str] = None
    
    def __post_init__(self):
        if self.base_url is None:
            self.base_url = f"https://{self.account_name}.saas.appdynamics.com"


def get_config() -> AppConfig:
    """Get application configuration."""
    return AppConfig(
        debug=os.getenv('DEBUG', 'false').lower() == 'true',
        snes_sounds=os.getenv('SNES_SOUNDS', 'false').lower() == 'true',
        verify_ssl=os.getenv('VERIFY_SSL', 'true').lower() == 'true',
    )




