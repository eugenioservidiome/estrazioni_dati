"""URL discovery orchestrator."""

from typing import List, Optional

from comuni_extractor.crawl.crawler import Crawler, DiscoveredPDF
from comuni_extractor.crawl.robots import RobotsParser
from comuni_extractor.http.client import HTTPClient


class URLDiscovery:
    """Orchestrate URL discovery with robots.txt compliance."""

    def __init__(
        self,
        http_client: HTTPClient,
        max_pages: int = 200,
        max_depth: int = 3,
        keywords: Optional[List[str]] = None,
        respect_robots: bool = True,
        allowed_domains: Optional[List[str]] = None,
    ):
        """Initialize discovery.
        
        Args:
            http_client: HTTP client
            max_pages: Max pages to crawl
            max_depth: Max crawl depth
            keywords: Keywords for prioritization
            respect_robots: Respect robots.txt
            allowed_domains: Domains allowed for crawling
        """
        self.http_client = http_client
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.keywords = keywords
        self.respect_robots = respect_robots
        self.allowed_domains = allowed_domains

        self.robots_parser = RobotsParser(http_client)

    def discover_pdfs(self, site_url: str, allow_www_equivalence: bool = True,
                      extract_pdf_from_raw_html: bool = True) -> List[DiscoveredPDF]:
        """Discover PDF URLs from site.
        
        Args:
            site_url: Base site URL
            allow_www_equivalence: Treat www/non-www as same site
            extract_pdf_from_raw_html: Extract PDFs via regex from raw HTML
            
        Returns:
            List of discovered PDFs with metadata
        """
        # Check robots.txt if enabled
        if self.respect_robots:
            if not self.robots_parser.can_crawl(site_url):
                return []

        # Start crawler
        crawler = Crawler(
            self.http_client,
            max_pages=self.max_pages,
            max_depth=self.max_depth,
            keywords=self.keywords,
            allowed_domains=self.allowed_domains,
            allow_www_equivalence=allow_www_equivalence,
            extract_pdf_from_raw_html=extract_pdf_from_raw_html,
        )

        discovered_pdfs = crawler.start_crawl(site_url)
        return discovered_pdfs


