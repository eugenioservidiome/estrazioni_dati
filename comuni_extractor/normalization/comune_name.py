"""Normalization for municipality names."""

import re

from slugify import slugify


def normalize_comune_name(name: str, fallback: str = "comune_unknown") -> str:
    """Normalize municipality name to slug format.
    
    Converts:
    - "Città di Roma" → "roma"
    - "San Giorgio/Mantova" → "san_giorgio_mantova"
    - "Città" → "citta" (removes accents)
    
    Args:
        name: Municipality name
        fallback: Value to return if name is empty/invalid
        
    Returns:
        Normalized name (lowercase, slugified)
    """
    if not name or not isinstance(name, str):
        return fallback

    try:
        # Strip whitespace
        name = name.strip()

        if not name:
            return fallback

        # Remove common prefixes
        prefixes = [
            r"^Città di ",
            r"^Comune di ",
            r"^Provincia di ",
            r"^Regione ",
        ]

        for prefix_pattern in prefixes:
            name = re.sub(prefix_pattern, "", name, flags=re.IGNORECASE)

        # Replace special characters with underscores or spaces
        # Keep letters, numbers, spaces, and hyphens
        name = re.sub(r"[^\w\s-]", " ", name)

        # Replace slashes and other separators with underscores
        name = re.sub(r"[\s/\-]+", "_", name)

        # Use python-slugify for proper slug conversion
        slugified = slugify(name, separator="_", lowercase=True)

        return slugified if slugified else fallback

    except Exception:
        return fallback


def extract_comune_from_url(url: str) -> str:
    """Try to extract comune name from URL.
    
    From "https://www.comune.roma.it" extracts "roma"
    
    Args:
        url: URL to parse
        
    Returns:
        Comune name or empty string if not found
    """
    try:
        # Extract domain
        domain_match = re.search(r"://(?:www\.)?([^/]+)", url)
        if not domain_match:
            return ""

        domain = domain_match.group(1)

        # Extract comune from standard pattern (comune.XXX.it)
        comune_match = re.search(r"comune\.([^\.]+)", domain)
        if comune_match:
            return comune_match.group(1).lower()

        # Try first subdomain
        parts = domain.split(".")
        if parts:
            return parts[0].lower()

        return ""
    except Exception:
        return ""


def extract_comune_from_html_title(html_title: str) -> str:
    """Extract comune name from HTML title tag.
    
    From "Comune di Roma - Amministrazione Trasparente" extracts "roma"
    
    Args:
        html_title: HTML title tag content
        
    Returns:
        Comune name or empty string
    """
    try:
        # Common patterns
        patterns = [
            r"Città di ([\w\s]+)",
            r"Comune di ([\w\s]+)",
            r"Provincia di ([\w\s]+)",
            r"^([\w\s]+)\s*[-–]\s*(?:Amministrazione|Trasparenza)",
        ]

        for pattern in patterns:
            match = re.search(pattern, html_title, re.IGNORECASE)
            if match:
                return match.group(1).strip().lower()

        return ""
    except Exception:
        return ""


def extract_comune_from_h1(h1_text: str) -> str:
    """Extract comune name from H1 tag.
    
    From "<h1>Città di Roma</h1>" extracts "roma"
    
    Args:
        h1_text: H1 tag content
        
    Returns:
        Comune name or empty string
    """
    try:
        # Remove HTML tags if present
        clean_text = re.sub(r"<[^>]+>", "", h1_text)

        # Extract comune name using normalize function
        normalized = normalize_comune_name(clean_text, fallback="")

        return normalized
    except Exception:
        return ""
