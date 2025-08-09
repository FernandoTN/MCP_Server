"""
Secret management integration
Google Secret Manager SDK for secure credential storage
"""

import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from google.api_core import exceptions
from services.config import get_settings

logger = logging.getLogger(__name__)

class SecretManager:
    """Manages secrets using Google Cloud Secret Manager"""
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[secretmanager.SecretManagerServiceClient] = None
        self.project_id = self.settings.google_cloud_project
    
    def _get_client(self) -> secretmanager.SecretManagerServiceClient:
        """Get or create Secret Manager client"""
        if not self._client:
            if not self.project_id:
                raise ValueError(
                    "Google Cloud project not configured. Set GOOGLE_CLOUD_PROJECT environment variable."
                )
            
            try:
                self._client = secretmanager.SecretManagerServiceClient()
                logger.info("Connected to Google Cloud Secret Manager")
            except Exception as e:
                logger.error(f"Failed to initialize Secret Manager client: {e}")
                raise
        
        return self._client
    
    async def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """
        Get a secret value from Google Secret Manager
        
        Args:
            secret_name: Name of the secret (can include full path or just name)
            version: Version of the secret to retrieve
            
        Returns:
            Secret value as string
            
        Raises:
            Exception: If secret cannot be retrieved
        """
        try:
            client = self._get_client()
            
            # Handle both full paths and simple names
            if secret_name.startswith("projects/"):
                name = f"{secret_name}/versions/{version}"
            else:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            
            logger.debug(f"Retrieving secret: {name}")
            
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret_value
            
        except exceptions.NotFound:
            logger.error(f"Secret not found: {secret_name}")
            raise Exception(f"Secret '{secret_name}' not found")
        except exceptions.PermissionDenied:
            logger.error(f"Permission denied accessing secret: {secret_name}")
            raise Exception(f"Permission denied accessing secret '{secret_name}'")
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise Exception(f"Failed to retrieve secret: {e}")
    
    async def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Store or update a secret in Google Secret Manager
        
        Args:
            secret_name: Name of the secret
            secret_value: Value to store
            labels: Optional labels for the secret
            
        Returns:
            Secret version name
            
        Raises:
            Exception: If secret cannot be stored
        """
        try:
            client = self._get_client()
            parent = f"projects/{self.project_id}"
            
            # Try to create the secret first (will fail if it exists)
            try:
                secret_request = {
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {
                        "replication": {"automatic": {}},
                        "labels": labels or {}
                    }
                }
                client.create_secret(request=secret_request)
                logger.info(f"Created new secret: {secret_name}")
                
            except exceptions.AlreadyExists:
                logger.debug(f"Secret {secret_name} already exists, will add new version")
            
            # Add a new version to the secret
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            version_request = {
                "parent": secret_path,
                "payload": {"data": secret_value.encode("UTF-8")}
            }
            
            response = client.add_secret_version(request=version_request)
            logger.info(f"Successfully stored secret version: {response.name}")
            
            return response.name
            
        except Exception as e:
            logger.error(f"Failed to store secret {secret_name}: {e}")
            raise Exception(f"Failed to store secret: {e}")
    
    async def delete_secret(self, secret_name: str) -> bool:
        """
        Delete a secret from Google Secret Manager
        
        Args:
            secret_name: Name of the secret to delete
            
        Returns:
            True if successfully deleted
        """
        try:
            client = self._get_client()
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            
            client.delete_secret(request={"name": secret_path})
            logger.info(f"Successfully deleted secret: {secret_name}")
            
            return True
            
        except exceptions.NotFound:
            logger.warning(f"Secret {secret_name} not found for deletion")
            return True  # Already doesn't exist
        except Exception as e:
            logger.error(f"Failed to delete secret {secret_name}: {e}")
            return False
    
    async def list_secrets(self) -> list[str]:
        """
        List all secrets in the project
        
        Returns:
            List of secret names
        """
        try:
            client = self._get_client()
            parent = f"projects/{self.project_id}"
            
            secrets = []
            for secret in client.list_secrets(request={"parent": parent}):
                # Extract secret name from the full path
                secret_name = secret.name.split("/")[-1]
                secrets.append(secret_name)
            
            logger.debug(f"Found {len(secrets)} secrets")
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []
    
    async def secret_exists(self, secret_name: str) -> bool:
        """
        Check if a secret exists
        
        Args:
            secret_name: Name of the secret to check
            
        Returns:
            True if secret exists
        """
        try:
            await self.get_secret(secret_name)
            return True
        except:
            return False

# Global instance
_secret_manager: Optional[SecretManager] = None

def get_secret_manager() -> SecretManager:
    """Get global SecretManager instance"""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager