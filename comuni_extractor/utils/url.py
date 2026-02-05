"""URL utilities for crawling and normalization."""

import re
from typing import Optional
from urllib.parse import urlparse


def normalize_host(host: str, allow_www_equivalence: bool = True) -> str:
    """Normalize a host for comparison.
    
    Converts to lowercase and optionally removes 'www.' prefix
    to treat www and non-www variants as equivalent.
    
    Args:
        host: Hostname to normalize
        allow_www_equivalence: If True, strip 'www.' prefix
        
    Returns:
        Normalized hostname
    """
    normalized = host.lower().strip()
    if allow_www_equivalence and normalized.startswith('www.'):
        normalized = normalized[4:]
    return normalized


def same_site(host_a: str, host_b: str, allow_www_equivalence: bool = True, 
              allow_subdomains: bool = False) -> bool:
    """Check if two hosts belong to the same site.
    
    Args:
        host_a: First hostname
        host_b: Second hostname
        allow_www_equivalence: Treat www and non-www as equivalent
        allow_subdomains: Allow different subdomains under same base domain
        
    Returns:
        True if hosts belong to same site
    """
    norm_a = normalize_host(host_a, allow_www_equivalence)
    norm_b = normalize_host(host_b, allow_www_equivalence)
    
    if norm_a == norm_b:
        return True
    
    # Check subdomains if enabled
    if allow_subdomains:
        # Extract base domain (last 2 parts, simplified)
        parts_a = norm_a.split('.')
        parts_b = norm_b.split('.')
        
        if len(parts_a) >= 2 and len(parts_b) >= 2:
            base_a = '.'.join(parts_a[-2:])
            base_b = '.'.join(parts_b[-2:])
            return base_a == base_b
    
    return False


def is_pdf_url(url: str) -> bool:
    """Check if URL points to a PDF file.
    
    Robust check that handles:
    - URLs with query strings: file.pdf?utm_source=x
    - URLs with fragments: file.pdf#page=2
    - Case-insensitive: file.PDF, FILE.Pdf
    - Relative paths: /cgi-bin/archivio/doc.pdf?x=y
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is a PDF
    """
    if not url:
        return False
    
    url_lower = url.lower().strip()
    
    # Regex pattern: .pdf followed by end, query, or fragment
    # Handles: .pdf, .pdf?, .pdf#
    if re.search(r'\.pdf(?:[?#]|$)', url_lower):
        return True
    
    return False


def extract_pdf_urls_from_html(html: str, base_url: str) -> list:
    """Extract PDF URLs from HTML using regex pattern matching.
    
    Finds PDF URLs that might not be in standard <a href> tags.
    Useful for PDFs embedded in JavaScript, JSON, or dynamic content.
    
    Args:
        html: HTML content
        base_url: Base URL for resolving relative URLs
        
    Returns:
        List of found PDF URLs (absolute)
    """
    if not html:
        return []
    
    # Parse base URL
    parsed_base = urlparse(base_url)
    base_scheme = parsed_base.scheme or 'https'
    base_netloc = parsed_base.netloc
    
    seen_canonical = set()  # Track canonical URLs to deduplicate
    pdf_urls = []
    
    # Pattern 1: Absolute URLs with http(s)
    # Matches: https://example.com/path/file.pdf or similar with query/fragment
    absolute_pattern = r'https?://[^\s"\'<>]*?\.pdf(?:\?[^\s"\'<>#]*)?'
    for match in re.finditer(absolute_pattern, html, re.IGNORECASE):
        url = match.group(0)
        can = canonical_url(url)
        if can not in seen_canonical:
            seen_canonical.add(can)
            pdf_urls.append(url)
    
    # Pattern 2: Relative URLs starting with /
    # Matches: /path/to/file.pdf or /cgi-bin/archivio/doc.pdf?param=value
    relative_pattern = r'/[^\s"\'<>]*?\.pdf(?:\?[^\s"\'<>#]*)?'
    for match in re.finditer(relative_pattern, html, re.IGNORECASE):
        relative_path = match.group(0)
        # Only process if not already captured as absolute
        # Check if this path is part of the same URL
        if not any(relative_path in abs_url for abs_url in pdf_urls):
            # Construct absolute URL
            absolute_url = f"{base_scheme}://{base_netloc}{relative_path}"
            can = canonical_url(absolute_url)
            if can not in seen_canonical:
                seen_canonical.add(can)
                pdf_urls.append(absolute_url)
    
    return pdf_urls


def canonical_url(url: str) -> str:
    """Return canonical form of URL for deduplication.
    
    Preserves query string and fragment (important for PDF links with tokens).
    Normalizes only the path part (lowercase, remove trailing slash).
    
    Args:
        url: URL to canonicalize
        
    Returns:
        Canonical URL
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    netloc = parsed.netloc.lower()
    scheme = parsed.scheme.lower()
    
    canonical = f"{scheme}://{netloc}{path}"
    if parsed.query:
        canonical += f"?{parsed.query}"
    if parsed.fragment:
        canonical += f"#{parsed.fragment}"
    
    return canonical
