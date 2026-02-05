"""Unit tests for URL utilities."""

import pytest
from comuni_extractor.utils.url import (
    is_pdf_url,
    normalize_host,
    same_site,
    extract_pdf_urls_from_html,
    canonical_url,
)


class TestIsPdfUrl:
    """Test is_pdf_url function with various URL formats."""

    def test_simple_pdf(self):
        """Test simple PDF URL."""
        assert is_pdf_url("https://example.com/file.pdf") is True

    def test_pdf_with_query_string(self):
        """Test PDF URL with query string."""
        assert is_pdf_url("https://example.com/file.pdf?utm_source=x") is True

    def test_pdf_with_multiple_query_params(self):
        """Test PDF with multiple query parameters."""
        url = "https://www.comune.vigone.to.it/cgi-bin/archivio/09262023175044_CITTA_DI_VIGONE.pdf?utm_source=email&utm_medium=newsletter"
        assert is_pdf_url(url) is True

    def test_pdf_with_fragment(self):
        """Test PDF URL with fragment."""
        assert is_pdf_url("https://example.com/file.pdf#page=2") is True

    def test_pdf_case_insensitive_uppercase(self):
        """Test uppercase PDF extension."""
        assert is_pdf_url("https://example.com/file.PDF") is True

    def test_pdf_case_insensitive_mixed(self):
        """Test mixed case PDF extension."""
        assert is_pdf_url("https://example.com/file.Pdf") is True

    def test_relative_pdf_url(self):
        """Test relative PDF URL."""
        assert is_pdf_url("/cgi-bin/archivio/doc.pdf") is True

    def test_relative_pdf_with_query(self):
        """Test relative PDF with query string."""
        assert is_pdf_url("/cgi-bin/archivio/doc.pdf?x=1&y=2") is True

    def test_not_pdf_html(self):
        """Test HTML file is not PDF."""
        assert is_pdf_url("https://example.com/index.html") is False

    def test_not_pdf_png(self):
        """Test image file is not PDF."""
        assert is_pdf_url("https://example.com/image.png") is False

    def test_not_pdf_txt(self):
        """Test text file is not PDF."""
        assert is_pdf_url("https://example.com/document.txt") is False

    def test_empty_url(self):
        """Test empty URL."""
        assert is_pdf_url("") is False

    def test_none_like_string(self):
        """Test None-like string."""
        assert is_pdf_url("   ") is False

    def test_pdf_in_filename_but_not_extension(self):
        """Test URL with 'pdf' in filename but not as extension."""
        assert is_pdf_url("https://example.com/pdf_document.html") is False

    def test_pdf_with_query_and_fragment(self):
        """Test PDF with both query and fragment."""
        assert is_pdf_url("https://example.com/file.pdf?key=value#section") is True


class TestNormalizeHost:
    """Test normalize_host function."""

    def test_normalize_lowercase(self):
        """Test that hosts are lowercased."""
        assert normalize_host("EXAMPLE.COM") == "example.com"

    def test_normalize_www_removed(self):
        """Test that www. is removed when allow_www_equivalence=True."""
        assert normalize_host("www.example.com", allow_www_equivalence=True) == "example.com"

    def test_normalize_www_kept(self):
        """Test that www. is kept when allow_www_equivalence=False."""
        assert normalize_host("www.example.com", allow_www_equivalence=False) == "www.example.com"

    def test_normalize_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        assert normalize_host("  example.com  ") == "example.com"


class TestSameSite:
    """Test same_site function."""

    def test_exact_match(self):
        """Test exact hostname match."""
        assert same_site("example.com", "example.com") is True

    def test_www_equivalence_enabled(self):
        """Test that www/non-www are equivalent when enabled."""
        assert same_site("www.example.com", "example.com", allow_www_equivalence=True) is True

    def test_www_equivalence_disabled(self):
        """Test that www/non-www are different when disabled."""
        assert same_site("www.example.com", "example.com", allow_www_equivalence=False) is False

    def test_case_insensitive(self):
        """Test case-insensitive comparison."""
        assert same_site("WWW.EXAMPLE.COM", "www.example.com") is True

    def test_subdomain_allowed(self):
        """Test subdomain matching when allowed."""
        assert same_site("api.example.com", "example.com", allow_subdomains=True) is True

    def test_subdomain_not_allowed(self):
        """Test subdomain matching when not allowed."""
        assert same_site("api.example.com", "example.com", allow_subdomains=False) is False

    def test_different_domains(self):
        """Test different domains."""
        assert same_site("example.com", "other.com") is False


class TestExtractPdfUrlsFromHtml:
    """Test extract_pdf_urls_from_html function."""

    def test_no_pdfs(self):
        """Test HTML with no PDFs."""
        html = "<html><body><a href='page.html'>Link</a></body></html>"
        urls = extract_pdf_urls_from_html(html, "https://example.com/")
        assert len(urls) == 0

    def test_absolute_pdf_url(self):
        """Test extraction of absolute PDF URL."""
        html = '<a href="https://example.com/document.pdf">Download</a>'
        urls = extract_pdf_urls_from_html(html, "https://example.com/")
        assert len(urls) == 1
        assert "document.pdf" in urls[0]

    def test_relative_pdf_url(self):
        """Test extraction of relative PDF URL."""
        html = '<a href="/docs/document.pdf">Download</a>'
        urls = extract_pdf_urls_from_html(html, "https://example.com/page")
        assert len(urls) == 1
        assert urls[0] == "https://example.com/docs/document.pdf"

    def test_pdf_with_query_in_html(self):
        """Test extraction of PDF with query string."""
        html = '<a href="/cgi-bin/archivio/file.pdf?utm_source=email">Download</a>'
        urls = extract_pdf_urls_from_html(html, "https://example.com/")
        assert len(urls) == 1
        assert "utm_source" in urls[0]

    def test_vigone_example(self):
        """Test with real Vigone example URL."""
        html = '<a href="/cgi-bin/archivio/09262023175044_CITTA_DI_VIGONE.pdf?utm_source">Download</a>'
        urls = extract_pdf_urls_from_html(html, "https://www.comune.vigone.to.it/")
        assert len(urls) == 1
        assert "09262023175044_CITTA_DI_VIGONE.pdf" in urls[0]

    def test_multiple_pdfs(self):
        """Test extraction of multiple PDFs."""
        html = '''
        <a href="/doc1.pdf">Doc 1</a>
        <a href="/doc2.pdf?x=1">Doc 2</a>
        <a href="/doc3.pdf#page=5">Doc 3</a>
        '''
        urls = extract_pdf_urls_from_html(html, "https://example.com/")
        assert len(urls) >= 3

    def test_duplicate_pdfs(self):
        """Test that duplicate PDFs are not added twice."""
        html = '''
        <a href="/doc.pdf">Doc 1</a>
        <a href="/doc.pdf">Doc 2</a>
        '''
        urls = extract_pdf_urls_from_html(html, "https://example.com/")
        # Should find the PDF once
        assert urls.count("https://example.com/doc.pdf") == 1


class TestCanonicalUrl:
    """Test canonical_url function."""

    def test_canonical_preserves_query(self):
        """Test that canonical form preserves query string."""
        url = "https://example.com/file.pdf?utm_source=x"
        canonical = canonical_url(url)
        assert "utm_source=x" in canonical

    def test_canonical_preserves_fragment(self):
        """Test that canonical form preserves fragment."""
        url = "https://example.com/file.pdf#page=2"
        canonical = canonical_url(url)
        assert "#page=2" in canonical

    def test_canonical_removes_trailing_slash(self):
        """Test that canonical form removes trailing slash from path."""
        url1 = "https://example.com/path/"
        url2 = "https://example.com/path"
        assert canonical_url(url1) == canonical_url(url2)

    def test_canonical_lowercase_scheme_netloc(self):
        """Test that scheme and netloc are lowercased."""
        url = "HTTPS://EXAMPLE.COM/Path"
        canonical = canonical_url(url)
        assert canonical.startswith("https://example.com")

    def test_canonical_idempotent(self):
        """Test that canonical is idempotent."""
        url = "https://example.com/file.pdf?x=1#s"
        canonical1 = canonical_url(url)
        canonical2 = canonical_url(canonical1)
        assert canonical1 == canonical2
