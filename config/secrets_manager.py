"""
Secrets management for AppDynamics Data Extractor.
"""
import yaml
from typing import List, Dict, Optional
from pathlib import Path


class SecretsManager:
    """Manages API credentials and secrets."""
    
    def __init__(self, secrets_file: str = "secrets.yml"):
        self.secrets_file = Path(secrets_file)
    
    def load_secrets(self) -> List[Dict]:
        """Load API credentials from secrets.yml if it exists."""
        try:
            if not self.secrets_file.exists():
                return []
            
            with open(self.secrets_file, "r") as file:
                secrets_data = yaml.safe_load(file)
                return secrets_data.get("secrets", [])
        except Exception as e:
            print(f"Error loading secrets: {e}")
            return []
    
    def save_secrets(self, secrets_data: List[Dict]) -> bool:
        """Save API credentials to secrets.yml."""
        try:
            with open(self.secrets_file, "w") as file:
                yaml.dump({"secrets": secrets_data}, file, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error saving secrets: {e}")
            return False
    
    def add_or_update_secret(self, account_name: str, api_client: str, api_key: str) -> bool:
        """Add or update a secret for the given account."""
        secrets = self.load_secrets()
        
        # Update existing secret if found
        for secret in secrets:
            if secret.get("account") == account_name:
                secret["api-client-name"] = api_client
                secret["api-key"] = api_key
                return self.save_secrets(secrets)
        
        # Add new secret
        secrets.append({
            "account": account_name,
            "api-client-name": api_client,
            "api-key": api_key
        })
        return self.save_secrets(secrets)
    
    def get_secret(self, account_name: str) -> Optional[Dict]:
        """Get secret for a specific account."""
        secrets = self.load_secrets()
        for secret in secrets:
            if secret.get("account") == account_name:
                return secret
        return None




