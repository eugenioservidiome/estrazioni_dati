"""robots.txt parser and compliance."""

from urllib.parse import urljoin, urlparse

from comuni_extractor.http.client import HTTPClient


class RobotsParser:
    """Parse and check robots.txt."""

    def __init__(self, http_client: HTTPClient):
        """Initialize parser.
        
        Args:
            http_client: HTTP client
        """
        self.http_client = http_client

    def can_crawl(self, url: str) -> bool:
        """Check if URL can be crawled via robots.txt.
        
        Args:
            url: URL to check
            
        Returns:
            True if crawling is allowed
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            # Try to fetch robots.txt
            robots_content = self.http_client.get_text(robots_url)

            # Simple check: if User-agent blocks crawling, return False
            # This is a simplified parser - full implementation would parse rules
            if "Disallow: /" in robots_content:
                return False

            return True

        except Exception:
            # If robots.txt can't be fetched, assume crawling is allowed
            return True
