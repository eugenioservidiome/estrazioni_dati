"""HTTP client with caching and resilience."""

import hashlib
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class HTTPClient:
    """HTTP client with retry, caching, and rate limiting."""

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_delay: float = 0.0,
        cache_dir: Optional[Path] = None,
    ):
        """Initialize HTTP client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
            rate_limit_delay: Delay between requests (seconds)
            cache_dir: Optional cache directory
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.last_request_time: dict[str, float] = {}

    def _get_cache_path(self, url: str) -> Optional[Path]:
        """Get cache file path for URL.
        
        Args:
            url: URL to cache
            
        Returns:
            Cache file path or None
        """
        if not self.cache_dir:
            return None

        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.cache"

    def _load_from_cache(self, url: str) -> Optional[bytes]:
        """Load response from cache.
        
        Args:
            url: URL to load
            
        Returns:
            Cached content or None
        """
        cache_path = self._get_cache_path(url)
        if not cache_path or not cache_path.exists():
            return None

        try:
            return cache_path.read_bytes()
        except Exception:
            return None

    def _save_to_cache(self, url: str, content: bytes) -> None:
        """Save response to cache.
        
        Args:
            url: URL being cached
            content: Response content
        """
        cache_path = self._get_cache_path(url)
        if cache_path:
            try:
                cache_path.write_bytes(content)
            except Exception:
                pass

    def _apply_rate_limit(self, url: str) -> None:
        """Apply rate limiting per domain.
        
        Args:
            url: URL being requested
        """
        if self.rate_limit_delay <= 0:
            return

        domain = urlparse(url).netloc
        last_time = self.last_request_time.get(domain, 0)
        elapsed = time.time() - last_time

        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        self.last_request_time[domain] = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def get(self, url: str, use_cache: bool = True) -> bytes:
        """GET request with retries and optional caching.
        
        Args:
            url: URL to request
            use_cache: Whether to use cache
            
        Returns:
            Response content
            
        Raises:
            httpx.HTTPError: If request fails after retries
        """
        # Try cache first
        if use_cache:
            cached = self._load_from_cache(url)
            if cached:
                return cached

        # Apply rate limit
        self._apply_rate_limit(url)

        # Make request
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()

            content = response.content

            # Cache response
            if use_cache:
                self._save_to_cache(url, content)

            return content

    def get_text(self, url: str, use_cache: bool = True) -> str:
        """GET request returning text.
        
        Args:
            url: URL to request
            use_cache: Whether to use cache
            
        Returns:
            Response text
        """
        content = self.get(url, use_cache=use_cache)
        return content.decode("utf-8")

    def head(self, url: str) -> int:
        """HEAD request to check content length.
        
        Args:
            url: URL to request
            
        Returns:
            Content length in bytes
            
        Raises:
            httpx.HTTPError: If request fails
        """
        self._apply_rate_limit(url)

        with httpx.Client(timeout=self.timeout) as client:
            response = client.head(url, follow_redirects=True)
            response.raise_for_status()

            return int(response.headers.get("content-length", 0))

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        if self.cache_dir and self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
