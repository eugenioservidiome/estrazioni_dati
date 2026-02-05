"""HTML text extraction and cleaning."""

from typing import Optional

from bs4 import BeautifulSoup


def extract_text_from_html(html_content: str) -> str:
    """Extract clean text from HTML content.
    
    Args:
        html_content: HTML content
        
    Returns:
        Extracted text
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text
    except Exception:
        return ""


def extract_links_from_html(html_content: str) -> list[str]:
    """Extract all links from HTML content.
    
    Args:
        html_content: HTML content
        
    Returns:
        List of URLs
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        links = []

        for link in soup.find_all("a", href=True):
            url = link["href"]
            if url:
                links.append(url)

        return links
    except Exception:
        return []


def extract_title_from_html(html_content: str) -> Optional[str]:
    """Extract page title from HTML.
    
    Args:
        html_content: HTML content
        
    Returns:
        Page title or None
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text().strip()
        return None
    except Exception:
        return None


def extract_h1_from_html(html_content: str) -> Optional[str]:
    """Extract first H1 from HTML.
    
    Args:
        html_content: HTML content
        
    Returns:
        H1 text or None
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        h1_tag = soup.find("h1")
        if h1_tag:
            return h1_tag.get_text().strip()
        return None
    except Exception:
        return None
