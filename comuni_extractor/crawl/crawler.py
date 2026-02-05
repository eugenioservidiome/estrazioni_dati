"""Web crawler for discovering PDF URLs."""

from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from comuni_extractor.http.client import HTTPClient
from comuni_extractor.documents.html_extractor import extract_links_from_html
from comuni_extractor.utils.url import (
    is_pdf_url,
    same_site,
    extract_pdf_urls_from_html,
    canonical_url,
)


@dataclass
class DiscoveredPDF:
    """Discovered PDF metadata."""
    
    pdf_url: str
    source_page_url: str
    anchor_text: str
    discovered_at: str


@dataclass
class CrawlerStats:
    """Statistics about the crawl."""
    
    pages_crawled: int = 0
    pdfs_discovered: int = 0
    discarded_out_of_scope: int = 0
    discarded_not_pdf: int = 0
    discarded_non_html_in_queue: int = 0
    discarded_duplicate: int = 0
    # Sample of discarded URLs per reason (max 20)
    samples_out_of_scope: List[str] = field(default_factory=list)
    samples_not_pdf: List[str] = field(default_factory=list)
    
    def add_sample(self, reason: str, url: str, max_samples: int = 20) -> None:
        """Add a sample URL for a discard reason."""
        if reason == "out_of_scope" and len(self.samples_out_of_scope) < max_samples:
            self.samples_out_of_scope.append(url)
        elif reason == "not_pdf" and len(self.samples_not_pdf) < max_samples:
            self.samples_not_pdf.append(url)


class Crawler:
    """BFS-based web crawler for discovering PDF links."""

    def __init__(
        self,
        http_client: HTTPClient,
        max_pages: int = 200,
        max_depth: int = 3,
        keywords: Optional[List[str]] = None,
        allowed_domains: Optional[List[str]] = None,
        allow_www_equivalence: bool = True,
        extract_pdf_from_raw_html: bool = True,
    ):
        """Initialize crawler.
        
        Args:
            http_client: HTTP client instance
            max_pages: Maximum pages to crawl
            max_depth: Maximum crawl depth
            keywords: Keywords to prioritize
            allowed_domains: Domains allowed for crawling (page visits)
            allow_www_equivalence: Treat www/non-www as same site
            extract_pdf_from_raw_html: Extract PDFs via regex from raw HTML
        """
        self.http_client = http_client
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.keywords = keywords or [
            "bilancio",
            "trasparenza",
            "rendiconto",
        ]
        self.allowed_domains = allowed_domains or []
        self.allow_www_equivalence = allow_www_equivalence
        self.extract_pdf_from_raw_html = extract_pdf_from_raw_html

        # Tracking
        self.visited: Set[str] = set()
        self.discovered_pdfs: List[DiscoveredPDF] = []
        self.queue: deque = deque()
        self.stats = CrawlerStats()

    def start_crawl(self, start_url: str) -> List[DiscoveredPDF]:
        """Start crawling from initial URL.
        
        Args:
            start_url: Starting URL
            
        Returns:
            List of discovered PDFs with metadata
        """
        self.visited.clear()
        self.discovered_pdfs.clear()
        self.queue.clear()
        self.stats = CrawlerStats()

        # Initialize queue with start URL
        self.queue.append((start_url, 0))
        self.visited.add(canonical_url(start_url))
        
        # Auto-detect allowed domain from start_url if not specified
        if not self.allowed_domains:
            start_domain = urlparse(start_url).netloc
            self.allowed_domains = [start_domain]

        while self.queue and self.stats.pages_crawled < self.max_pages:
            url, depth = self.queue.popleft()

            if depth > self.max_depth:
                continue

            try:
                # Fetch page
                html = self.http_client.get_text(url)
                self.stats.pages_crawled += 1

                # Extract links with anchor text from <a> tags
                links_from_html = self._extract_links_with_anchors(html, url)
                
                # Track canonical URLs of already-found links to avoid duplicates
                seen_canonical_in_page = set()
                for link_url, _ in links_from_html:
                    absolute_url = urljoin(url, link_url)
                    seen_canonical_in_page.add(canonical_url(absolute_url))
                
                # Also extract PDFs from raw HTML (regex-based)
                if self.extract_pdf_from_raw_html:
                    pdf_urls_from_regex = extract_pdf_urls_from_html(html, url)
                    # Convert to (url, anchor_text) tuples, avoiding duplicates
                    for pdf_url in pdf_urls_from_regex:
                        can = canonical_url(pdf_url)
                        if can not in seen_canonical_in_page:
                            links_from_html.append((pdf_url, "(found in page content)"))
                            seen_canonical_in_page.add(can)

                # Process all links
                for link_url, anchor_text in links_from_html:
                    # Resolve relative URLs
                    absolute_url = urljoin(url, link_url)

                    # Check if PDF
                    if is_pdf_url(absolute_url):
                        # Check if PDF is from allowed domains (Comune itself or partners)
                        if self._is_pdf_in_scope(absolute_url):
                            # Record PDF (with full URL including query string)
                            is_new = self._record_pdf(absolute_url, url, anchor_text)
                            if is_new:
                                self.stats.pdfs_discovered += 1
                        else:
                            self.stats.discarded_out_of_scope += 1
                            self.stats.add_sample("out_of_scope", absolute_url)
                        continue

                    # For non-PDF links: check if should crawl
                    if not self._is_allowed_domain(absolute_url):
                        # External link: don't crawl
                        self.stats.discarded_out_of_scope += 1
                        self.stats.add_sample("out_of_scope", absolute_url)
                        continue

                    # Check if visited (canonicalize for deduplication)
                    canonical = canonical_url(absolute_url)
                    if canonical in self.visited:
                        self.stats.discarded_duplicate += 1
                        continue

                    # Add to queue
                    self.visited.add(canonical)
                    self.queue.append((absolute_url, depth + 1))

            except Exception as e:
                # Silently skip failed pages
                continue

        return self.discovered_pdfs

    def _extract_links_with_anchors(self, html: str, base_url: str) -> List[tuple]:
        """Extract links with anchor text from multiple sources.
        
        Extracts from:
        - <a href>
        - <link href>
        - <embed src>
        - <object data>
        - <iframe src>
        
        Args:
            html: HTML content
            base_url: Base URL for context
            
        Returns:
            List of (url, anchor_text) tuples
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        # Extract from <a> tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            anchor_text = a_tag.get_text(strip=True) or "(no text)"
            links.append((href, anchor_text))
        
        # Extract from <link> tags (stylesheets, etc.)
        for link_tag in soup.find_all('link', href=True):
            href = link_tag['href']
            links.append((href, "(link tag)"))
        
        # Extract from <embed> and <object> tags
        for embed_tag in soup.find_all('embed', src=True):
            src = embed_tag['src']
            links.append((src, "(embed)"))
        
        for obj_tag in soup.find_all('object', data=True):
            data = obj_tag['data']
            links.append((data, "(object)"))
        
        # Extract from <iframe> tags
        for iframe_tag in soup.find_all('iframe', src=True):
            src = iframe_tag['src']
            links.append((src, "(iframe)"))
        
        return links

    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL domain is allowed for crawling.
        
        Uses same_site() to handle www/non-www equivalence.
        
        Args:
            url: URL to check
            
        Returns:
            True if allowed
        """
        domain = urlparse(url).netloc
        
        for allowed in self.allowed_domains:
            # Use same_site helper for robust comparison
            if same_site(domain, allowed, self.allow_www_equivalence):
                return True
        
        return False

    def _is_pdf_in_scope(self, url: str) -> bool:
        """Check if PDF URL is from allowed domains (Comune itself).
        
        PDFs should be from the same Comune sites (allowed_domains).
        This was the critical bug: hardcoded check for servizipubblicaamministrazione.it
        now checks the allowed_domains instead.
        
        Args:
            url: PDF URL
            
        Returns:
            True if from allowed domain
        """
        # PDFs are only recorded if they're from allowed domains
        # (i.e., the Comune site itself)
        return self._is_allowed_domain(url)

    def _record_pdf(self, pdf_url: str, source_page_url: str, anchor_text: str) -> bool:
        """Record discovered PDF.
        
        Args:
            pdf_url: PDF URL (full, with query string preserved)
            source_page_url: Page where PDF was found
            anchor_text: Anchor text of the link
            
        Returns:
            True if new PDF was recorded, False if duplicate
        """
        # Check if already recorded (exact URL match)
        for existing in self.discovered_pdfs:
            if existing.pdf_url == pdf_url:
                return False  # Already recorded (duplicate)
        
        pdf = DiscoveredPDF(
            pdf_url=pdf_url,
            source_page_url=source_page_url,
            anchor_text=anchor_text,
            discovered_at=datetime.now().isoformat(),
        )
        
        self.discovered_pdfs.append(pdf)
        return True



