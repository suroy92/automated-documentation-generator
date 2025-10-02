# src/rate_limiter.py

"""
Rate limiter for controlling API call frequency.
Prevents exceeding API quotas and reduces costs.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for API calls."""
    
    def __init__(self, calls_per_minute: int = 20):
        """
        Initialize the rate limiter.
        
        Args:
            calls_per_minute: Maximum number of calls allowed per minute
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute if calls_per_minute > 0 else 0
        self.last_call_time: Optional[float] = None
        self.call_count = 0
        
        logger.info(f"Rate limiter initialized: {calls_per_minute} calls/minute "
                   f"(min interval: {self.min_interval:.2f}s)")
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limits."""
        if self.calls_per_minute <= 0:
            return
        
        current_time = time.time()
        
        if self.last_call_time is not None:
            elapsed = current_time - self.last_call_time
            
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s before next call")
                time.sleep(wait_time)
                current_time = time.time()
        
        self.last_call_time = current_time
        self.call_count += 1
    
    def reset(self) -> None:
        """Reset the rate limiter state."""
        self.last_call_time = None
        self.call_count = 0
        logger.debug("Rate limiter reset")
    
    def get_stats(self) -> dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with rate limiter statistics
        """
        return {
            'calls_per_minute': self.calls_per_minute,
            'min_interval': self.min_interval,
            'total_calls': self.call_count,
            'last_call_time': self.last_call_time
        }