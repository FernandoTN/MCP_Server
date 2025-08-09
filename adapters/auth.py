"""
Google API authentication
OAuth token management and service account JWT handling
"""

import json
import logging
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.exceptions import RefreshError
from services.config import get_settings
from services.secrets import SecretManager

logger = logging.getLogger(__name__)

class GoogleAuthManager:
    """Manages Google API authentication credentials"""
    
    def __init__(self):
        self.settings = get_settings()
        self.secret_manager = SecretManager()
        self._credentials: Optional[Credentials] = None
        self._service_account_info: Optional[Dict[str, Any]] = None
    
    async def get_credentials(self) -> Credentials:
        """
        Get valid Google API credentials
        
        Returns:
            Valid Credentials object
            
        Raises:
            Exception: If unable to obtain valid credentials
        """
        # Try service account first
        if self.settings.google_service_account_key_path:
            return await self._get_service_account_credentials()
        
        # Fall back to OAuth flow
        if self.settings.google_client_id and self.settings.google_client_secret:
            return await self._get_oauth_credentials()
        
        raise Exception("No Google authentication method configured")
    
    async def _get_service_account_credentials(self) -> Credentials:
        """Get credentials from service account key"""
        try:
            if not self._service_account_info:
                # Load from file or secret manager
                if self.settings.google_service_account_key_path.startswith('projects/'):
                    # Secret Manager path
                    key_data = await self.secret_manager.get_secret(
                        self.settings.google_service_account_key_path
                    )
                    self._service_account_info = json.loads(key_data)
                else:
                    # Local file path
                    with open(self.settings.google_service_account_key_path, 'r') as f:
                        self._service_account_info = json.load(f)
            
            credentials = service_account.Credentials.from_service_account_info(
                self._service_account_info,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            logger.info("Successfully loaded service account credentials")
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to load service account credentials: {e}")
            raise
    
    async def _get_oauth_credentials(self) -> Credentials:
        """Get credentials from OAuth flow"""
        try:
            # Try to load existing token
            if self._credentials and self._credentials.valid:
                return self._credentials
            
            # Try to refresh token
            if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                try:
                    self._credentials.refresh(Request())
                    logger.info("Successfully refreshed OAuth credentials")
                    await self._save_credentials(self._credentials)
                    return self._credentials
                except RefreshError as e:
                    logger.warning(f"Failed to refresh credentials: {e}")
            
            # Load credentials from secret manager or perform OAuth flow
            token_data = await self._load_oauth_token()
            if token_data:
                self._credentials = Credentials.from_authorized_user_info(
                    token_data,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
                
                if self._credentials.valid:
                    return self._credentials
                
                # Try to refresh
                if self._credentials.expired and self._credentials.refresh_token:
                    try:
                        self._credentials.refresh(Request())
                        await self._save_credentials(self._credentials)
                        return self._credentials
                    except RefreshError:
                        pass
            
            # If we get here, we need to perform initial OAuth flow
            raise Exception(
                "No valid OAuth credentials found. "
                "Please run the OAuth setup process to obtain initial credentials."
            )
            
        except Exception as e:
            logger.error(f"Failed to get OAuth credentials: {e}")
            raise
    
    async def _load_oauth_token(self) -> Optional[Dict[str, Any]]:
        """Load OAuth token from secret manager"""
        try:
            if hasattr(self.settings, 'google_oauth_token_secret'):
                token_json = await self.secret_manager.get_secret(
                    self.settings.google_oauth_token_secret
                )
                return json.loads(token_json)
        except Exception as e:
            logger.debug(f"Could not load OAuth token: {e}")
        return None
    
    async def _save_credentials(self, credentials: Credentials):
        """Save credentials to secret manager"""
        try:
            if hasattr(self.settings, 'google_oauth_token_secret'):
                token_data = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                }
                
                await self.secret_manager.store_secret(
                    self.settings.google_oauth_token_secret,
                    json.dumps(token_data)
                )
                logger.info("Saved OAuth credentials")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    async def setup_oauth_flow(self) -> str:
        """
        Generate OAuth authorization URL for initial setup
        
        Returns:
            Authorization URL for user to visit
        """
        from google_auth_oauthlib.flow import Flow
        
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.settings.google_client_id,
                        "client_secret": self.settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.settings.google_redirect_uri]
                    }
                },
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            flow.redirect_uri = self.settings.google_redirect_uri
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to setup OAuth flow: {e}")
            raise
    
    async def complete_oauth_flow(self, authorization_code: str) -> Credentials:
        """
        Complete OAuth flow with authorization code
        
        Args:
            authorization_code: Code received from OAuth callback
            
        Returns:
            Valid credentials
        """
        from google_auth_oauthlib.flow import Flow
        
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.settings.google_client_id,
                        "client_secret": self.settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.settings.google_redirect_uri]
                    }
                },
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            flow.redirect_uri = self.settings.google_redirect_uri
            flow.fetch_token(code=authorization_code)
            
            self._credentials = flow.credentials
            await self._save_credentials(self._credentials)
            
            logger.info("Successfully completed OAuth flow")
            return self._credentials
            
        except Exception as e:
            logger.error(f"Failed to complete OAuth flow: {e}")
            raise