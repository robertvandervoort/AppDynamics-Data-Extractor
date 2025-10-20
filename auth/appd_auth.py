"""
AppDynamics authentication module.
"""
import time
import requests
from typing import Optional, Tuple
from config import APICredentials


class AppDAuthenticator:
    """Handles AppDynamics API authentication and token management."""
    
    def __init__(self, credentials: APICredentials, verify_ssl: bool = True):
        self.credentials = credentials
        self.verify_ssl = verify_ssl
        self.session: Optional[requests.Session] = None
        self.last_token_fetch_time: float = 0
        self.token_expiration: int = 300
        self.expiration_buffer: int = 30
    
    def is_token_valid(self) -> bool:
        """Check if the access token is valid and not expired."""
        if self.session is None or not self.session:
            return False
        
        return time.time() < (self.token_expiration + self.last_token_fetch_time - self.expiration_buffer)
    
    def authenticate(self, force_refresh: bool = False) -> bool:
        """
        Authenticate with AppDynamics API and retrieve OAuth token.
        
        Args:
            force_refresh: Force token refresh even if current token is valid
            
        Returns:
            True if authentication successful, False otherwise
        """
        if not force_refresh and self.is_token_valid():
            return True
        
        self.session = requests.Session()
        
        url = (f"{self.credentials.base_url}/controller/api/oauth/access_token"
               f"?grant_type=client_credentials"
               f"&client_id={self.credentials.api_client}@{self.credentials.account_name}"
               f"&client_secret={self.credentials.api_secret}")
        
        payload = {}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        print(f"Logging into the controller at: {self.credentials.base_url}")
        
        try:
            response = self.session.request(
                "POST",
                url,
                headers=headers,
                data=payload,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            json_response = response.json()
            self.last_token_fetch_time = time.time()
            self.token_expiration = json_response['expires_in']
            
            self.session.headers['X-CSRF-TOKEN'] = json_response['access_token']
            self.session.headers['Authorization'] = f'Bearer {json_response["access_token"]}'
            
            print("Authenticated with controller.")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Authentication failed: {e}")
            return False
    
    def get_session(self) -> Optional[requests.Session]:
        """Get the authenticated session, refreshing token if necessary."""
        if not self.is_token_valid():
            if not self.authenticate():
                return None
        return self.session
    
    def ensure_authenticated(self) -> bool:
        """Ensure we have a valid authenticated session."""
        if not self.is_token_valid():
            return self.authenticate()
        return True




