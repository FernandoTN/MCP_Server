"""
Idempotency cache implementation
Redis-based deduplication for request processing
"""

import redis
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import timedelta
from services.config import get_settings

logger = logging.getLogger(__name__)

class IdempotencyCache:
    """Redis-based idempotency cache for preventing duplicate requests"""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = self._create_redis_client()
        self.default_ttl = 300  # 5 minutes default TTL
    
    def _create_redis_client(self) -> redis.Redis:
        """Create Redis client with connection pooling"""
        try:
            client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            client.ping()
            logger.info("Connected to Redis for idempotency cache")
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Return mock client for development
            return MockRedisClient()
    
    def generate_key(self, tool_name: str, arguments: Dict[str, Any], user_id: str = None) -> str:
        """
        Generate idempotency key from tool call parameters
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            user_id: Optional user identifier
            
        Returns:
            Idempotency key string
        """
        # Create deterministic hash of the request
        key_data = {
            "tool": tool_name,
            "args": arguments,
            "user": user_id
        }
        
        # Sort keys for consistent hashing
        key_json = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()
        
        return f"mcp:idempotency:{key_hash}"
    
    async def check_and_set(self, key: str, result: Dict[str, Any], ttl: int = None) -> Optional[Dict[str, Any]]:
        """
        Check if request has been processed and optionally set result
        
        Args:
            key: Idempotency key
            result: Result to store if not already processed
            ttl: TTL in seconds (defaults to self.default_ttl)
            
        Returns:
            Existing result if found, None if new request
        """
        ttl = ttl or self.default_ttl
        
        try:
            # Check if key exists
            existing_result = self.redis_client.get(key)
            if existing_result:
                logger.info(f"Found existing result for idempotency key: {key}")
                return json.loads(existing_result)
            
            # Set new result with TTL
            if result:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(result, default=str)
                )
                logger.debug(f"Stored result for idempotency key: {key}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error in idempotency cache operation: {e}")
            # Return None to allow request to proceed
            return None
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached result by key"""
        try:
            result = self.redis_client.get(key)
            if result:
                return json.loads(result)
            return None
        except Exception as e:
            logger.error(f"Error getting cached result: {e}")
            return None
    
    async def set(self, key: str, result: Dict[str, Any], ttl: int = None) -> bool:
        """Set cached result"""
        ttl = ttl or self.default_ttl
        try:
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(result, default=str)
            )
            return True
        except Exception as e:
            logger.error(f"Error setting cached result: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete cached result"""
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cached result: {e}")
            return False
    
    async def clear_expired(self):
        """Clear expired keys (Redis handles this automatically with TTL)"""
        # Redis automatically cleans up expired keys
        pass

class MockRedisClient:
    """Mock Redis client for development/testing when Redis is unavailable"""
    
    def __init__(self):
        self._data = {}
        logger.warning("Using mock Redis client - idempotency cache disabled")
    
    def ping(self):
        return True
    
    def get(self, key):
        return self._data.get(key)
    
    def setex(self, key, ttl, value):
        self._data[key] = value
        return True
    
    def delete(self, key):
        return self._data.pop(key, None) is not None