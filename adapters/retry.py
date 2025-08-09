"""
Retry logic and quota management
Exponential backoff for 429/5xx responses and quota bucket handling
"""

import asyncio
import random
import logging
from typing import Callable, Any, Optional
from functools import wraps
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

class QuotaManager:
    """Manages API quota and rate limiting"""
    
    def __init__(self):
        self.quota_exceeded_until: Optional[float] = None
        self.request_count = 0
        self.quota_reset_time = 0
    
    async def check_quota(self) -> bool:
        """Check if we can make a request within quota limits"""
        import time
        current_time = time.time()
        
        if self.quota_exceeded_until and current_time < self.quota_exceeded_until:
            logger.warning(f"Quota exceeded, waiting until {self.quota_exceeded_until}")
            return False
        
        return True
    
    async def handle_quota_exceeded(self, retry_after: Optional[int] = None):
        """Handle quota exceeded response"""
        import time
        
        if retry_after:
            self.quota_exceeded_until = time.time() + retry_after
            logger.warning(f"Quota exceeded, waiting {retry_after} seconds")
        else:
            # Default wait time if not specified
            self.quota_exceeded_until = time.time() + 60
            logger.warning("Quota exceeded, waiting 60 seconds")

async def exponential_backoff_retry(
    func: Callable,
    config: RetryConfig = None,
    *args,
    **kwargs
) -> Any:
    """
    Retry function with exponential backoff
    
    Args:
        func: Function to retry
        config: Retry configuration
        *args, **kwargs: Arguments to pass to function
        
    Returns:
        Function result
        
    Raises:
        Exception: If all retries are exhausted
    """
    config = config or RetryConfig()
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            if attempt > 0:
                logger.info(f"Retry succeeded on attempt {attempt + 1}")
            return result
            
        except HttpError as e:
            last_exception = e
            status_code = e.resp.status
            
            # Don't retry certain status codes
            if status_code in [400, 401, 403, 404]:
                logger.error(f"Non-retryable error {status_code}: {e}")
                raise
            
            # Handle rate limiting (429) and server errors (5xx)
            if status_code in [429, 500, 502, 503, 504]:
                if attempt >= config.max_retries:
                    logger.error(f"Max retries ({config.max_retries}) exceeded")
                    raise
                
                # Calculate delay
                delay = min(
                    config.base_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )
                
                # Add jitter to avoid thundering herd
                if config.jitter:
                    delay *= (0.5 + random.random() * 0.5)
                
                # Check for Retry-After header
                retry_after = e.resp.get('retry-after')
                if retry_after:
                    try:
                        retry_after_seconds = int(retry_after)
                        delay = max(delay, retry_after_seconds)
                    except ValueError:
                        pass
                
                logger.warning(
                    f"Attempt {attempt + 1} failed with {status_code}, "
                    f"retrying in {delay:.2f} seconds"
                )
                
                await asyncio.sleep(delay)
                continue
            
            # Other HTTP errors
            logger.error(f"HTTP error {status_code}: {e}")
            raise
            
        except Exception as e:
            last_exception = e
            
            if attempt >= config.max_retries:
                logger.error(f"Max retries ({config.max_retries}) exceeded")
                raise
            
            # Calculate delay for general exceptions
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay
            )
            
            if config.jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {delay:.2f} seconds")
            await asyncio.sleep(delay)
    
    # Should not reach here, but just in case
    raise last_exception

def with_retry(config: RetryConfig = None):
    """Decorator for adding retry logic to functions"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await exponential_backoff_retry(func, config, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(exponential_backoff_retry(func, config, *args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_requests_per_second: float = 10):
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0.0
    
    async def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()