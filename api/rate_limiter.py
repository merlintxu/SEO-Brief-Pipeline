# api/rate_limiter.py
"""
Custom rate limiting middleware for FastAPI.
Uses a simple in-memory token bucket algorithm to limit requests per IP.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from threading import Lock


class RateLimiter:
    """
    Token bucket rate limiter with per-IP tracking.
    
    Args:
        rate: Number of requests allowed per window
        window: Time window in seconds
    """
    
    def __init__(self, rate: int = 5, window: int = 60):
        self.rate = rate
        self.window = window
        # Store: IP -> (last_reset_time, token_count)
        self._buckets: Dict[str, Tuple[float, int]] = defaultdict(lambda: (time.time(), rate))
        self._lock = Lock()
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request from this IP should be allowed."""
        with self._lock:
            now = time.time()
            last_reset, tokens = self._buckets[client_ip]
            
            # Reset bucket if window has passed
            if now - last_reset >= self.window:
                self._buckets[client_ip] = (now, self.rate)
                tokens = self.rate
            
            # Check if tokens available
            if tokens > 0:
                self._buckets[client_ip] = (last_reset, tokens - 1)
                return True
            
            return False
    
    def cleanup_old_entries(self):
        """Remove old entries to prevent memory leak."""
        with self._lock:
            now = time.time()
            to_remove = [
                ip for ip, (last_reset, _) in self._buckets.items()
                if now - last_reset > self.window * 2
            ]
            for ip in to_remove:
                del self._buckets[ip]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Args:
        app: FastAPI application
        rate: Requests per window (default: 10)
        window: Window in seconds (default: 60)
        exempt_paths: List of paths to exempt from rate limiting (e.g., ["/health"])
    """
    
    def __init__(self, app, rate: int = 10, window: int = 60, exempt_paths: list[str] = None):
        super().__init__(app)
        self.limiter = RateLimiter(rate=rate, window=window)
        self.exempt_paths = exempt_paths or []
        self._cleanup_counter = 0
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        if not self.limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded: {self.limiter.rate} requests per {self.limiter.window} seconds"
                },
                headers={"Retry-After": str(self.limiter.window)}
            )
        
        # Periodic cleanup (every 100 requests)
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self.limiter.cleanup_old_entries()
            self._cleanup_counter = 0
        
        response = await call_next(request)
        return response
