"""Integration tests for crawler domain scoping."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from comuni_extractor.crawl.crawler import Crawler, DiscoveredPDF


class TestCrawlerDomainScoping:
    """Test that crawler respects domain boundaries."""

    @patch("comuni_extractor.crawl.crawler.HTTPClient")
    def test_crawler_stays_within_allowed_domain(self, mock_http_client):
        """Test crawler doesn't visit external domains."""
        # Mock HTTP responses
        mock_client_instance = Mock()
        mock_http_client.return_value = mock_client_instance

        # Response for main page
        main_page_html = """
        <html>
        <body>
            <a href="/page1.html">Page 1</a>
            <a href="https://other-comune.it/page2.html">External Page</a>
            <a href="https://comune.example.it/docs/file.pdf">Internal PDF</a>
            <a href="https://servizipubblicaamministrazione.it/doc.pdf">External PDF</a>
        </body>
        </html>
        """

        # Response for internal page
        page1_html = """
        <html>
        <body>
            <a href="/docs/documento.pdf">Documento PDF</a>
        </body>
        </html>
        """

        def mock_get(url):
            """Mock HTTP GET responses."""
            mock_resp = Mock()
            if "comune.example.it" in url and "page1" in url:
                mock_resp.text = page1_html
                mock_resp.status_code = 200
            elif "comune.example.it" in url:
                mock_resp.text = main_page_html
                mock_resp.status_code = 200
            else:
                # External domains should never be called
                raise AssertionError(f"Crawler tried to visit external domain: {url}")
            return mock_resp

        mock_client_instance.get.side_effect = mock_get

        # Run crawler
        crawler = Crawler(
            start_url="https://comune.example.it/",
            http_client=mock_client_instance,
            max_pages=10,
            max_depth=2,
            allowed_domains=["comune.example.it"],
        )

        discovered_pdfs = crawler.crawl()

        # Assertions
        # Should find both internal and external PDFs
        assert len(discovered_pdfs) >= 2

        # Check that external PDFs were discovered (but not crawled)
        pdf_urls = [pdf.pdf_url for pdf in discovered_pdfs]
        assert any("servizipubblicaamministrazione.it" in url for url in pdf_urls)
        assert any("comune.example.it/docs/file.pdf" in url for url in pdf_urls)

        # Verify HTTP client was NOT called for external domains
        called_urls = [call[0][0] for call in mock_client_instance.get.call_args_list]
        for url in called_urls:
            assert "comune.example.it" in url, f"Crawler visited external domain: {url}"

    @patch("comuni_extractor.crawl.crawler.HTTPClient")
    def test_discovered_pdf_metadata(self, mock_http_client):
        """Test that discovered PDFs contain complete metadata."""
        mock_client_instance = Mock()
        mock_http_client.return_value = mock_client_instance

        html = """
        <html>
        <body>
            <a href="/docs/bilancio.pdf">Bilancio Previsione 2023</a>
        </body>
        </html>
        """

        mock_resp = Mock()
        mock_resp.text = html
        mock_resp.status_code = 200
        mock_client_instance.get.return_value = mock_resp

        crawler = Crawler(
            start_url="https://comune.test.it/",
            http_client=mock_client_instance,
            max_pages=1,
        )

        discovered_pdfs = crawler.crawl()

        # Should find the PDF
        assert len(discovered_pdfs) == 1

        pdf = discovered_pdfs[0]
        # Check DiscoveredPDF fields
        assert pdf.pdf_url == "https://comune.test.it/docs/bilancio.pdf"
        assert pdf.source_page_url == "https://comune.test.it/"
        assert pdf.anchor_text == "Bilancio Previsione 2023"
        assert isinstance(pdf.discovered_at, str)
        assert len(pdf.discovered_at) > 0  # Should be ISO datetime

    @patch("comuni_extractor.crawl.crawler.HTTPClient")
    def test_url_deduplication_preserves_query_strings(self, mock_http_client):
        """Test that URLs with different query strings are treated as distinct."""
        mock_client_instance = Mock()
        mock_http_client.return_value = mock_client_instance

        html = """
        <html>
        <body>
            <a href="/doc.pdf?year=2023">PDF 2023</a>
            <a href="/doc.pdf?year=2024">PDF 2024</a>
            <a href="/doc.pdf?year=2023">PDF 2023 Duplicate</a>
        </body>
        </html>
        """

        mock_resp = Mock()
        mock_resp.text = html
        mock_resp.status_code = 200
        mock_client_instance.get.return_value = mock_resp

        crawler = Crawler(
            start_url="https://comune.test.it/",
            http_client=mock_client_instance,
            max_pages=1,
        )

        discovered_pdfs = crawler.crawl()

        # Should find 2 unique PDFs (different query strings)
        # The duplicate with same query string should be deduplicated
        assert len(discovered_pdfs) == 2

        urls = [pdf.pdf_url for pdf in discovered_pdfs]
        assert "https://comune.test.it/doc.pdf?year=2023" in urls
        assert "https://comune.test.it/doc.pdf?year=2024" in urls
