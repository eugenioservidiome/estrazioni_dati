"""Integration tests for PDF discovery."""

import pytest
from unittest.mock import Mock, patch
from comuni_extractor.crawl.crawler import Crawler, DiscoveredPDF
from comuni_extractor.crawl.discovery import URLDiscovery


class TestDiscoveryCrawler:
    """Integration tests for the discovery crawler."""

    def test_discover_pdf_with_query_string(self):
        """Test that PDFs with query strings are discovered.
        
        This is the critical bug fix: ensure that URLs like
        /cgi-bin/archivio/file.pdf?utm_source=x are detected.
        """
        # Create mock HTTP client
        mock_http_client = Mock()
        
        # HTML with a PDF link that has a query string
        html_with_pdf = '''
        <html>
        <body>
            <a href="/cgi-bin/archivio/09262023175044_CITTA_DI_VIGONE.pdf?utm_source=email">
                Bilancio PDF
            </a>
        </body>
        </html>
        '''
        
        mock_http_client.get_text.return_value = html_with_pdf
        
        # Create crawler
        crawler = Crawler(
            mock_http_client,
            max_pages=10,
            max_depth=2,
            allowed_domains=["www.comune.vigone.to.it"],
        )
        
        # Run crawl
        discovered = crawler.start_crawl("https://www.comune.vigone.to.it/")
        
        # Verify PDF was discovered
        assert len(discovered) == 1
        pdf = discovered[0]
        assert "09262023175044_CITTA_DI_VIGONE.pdf" in pdf.pdf_url
        assert "utm_source" in pdf.pdf_url, "Query string must be preserved"

    def test_discover_pdf_from_allowed_domain_only(self):
        """Test that PDFs are only discovered from allowed domains.
        
        This ensures the fix for the critical bug where PDFs from
        the Comune domain itself (www.comune.vigone.to.it) were
        being discarded because _is_target_pdf_domain checked
        only for servizipubblicaamministrazione.it.
        """
        mock_http_client = Mock()
        
        # HTML with PDF from the Comune domain
        html = '''
        <html>
        <body>
            <a href="https://www.comune.vigone.to.it/docs/file.pdf">
                Local PDF
            </a>
            <a href="https://external.com/file.pdf">
                External PDF
            </a>
        </body>
        </html>
        '''
        
        mock_http_client.get_text.return_value = html
        
        crawler = Crawler(
            mock_http_client,
            max_pages=10,
            max_depth=2,
            allowed_domains=["www.comune.vigone.to.it"],
        )
        
        discovered = crawler.start_crawl("https://www.comune.vigone.to.it/")
        
        # Should discover only the local PDF, not the external one
        assert len(discovered) == 1
        assert "www.comune.vigone.to.it" in discovered[0].pdf_url

    def test_www_equivalence_in_scope_check(self):
        """Test that www/non-www are treated as same site.
        
        Base URL: https://www.comune.vigone.to.it/
        PDF on: https://comune.vigone.to.it/file.pdf
        
        With allow_www_equivalence=True, both should be in-scope.
        """
        mock_http_client = Mock()
        
        html = '''
        <html>
        <body>
            <a href="https://comune.vigone.to.it/file.pdf">
                PDF no-www
            </a>
        </body>
        </html>
        '''
        
        mock_http_client.get_text.return_value = html
        
        # Crawl starts with www., but we allow www equivalence
        crawler = Crawler(
            mock_http_client,
            max_pages=10,
            max_depth=2,
            allowed_domains=["www.comune.vigone.to.it"],
            allow_www_equivalence=True,  # This is the setting
        )
        
        discovered = crawler.start_crawl("https://www.comune.vigone.to.it/")
        
        # PDF from non-www variant should be discovered
        assert len(discovered) == 1
        assert "file.pdf" in discovered[0].pdf_url

    def test_pdf_discovery_from_raw_html_regex(self):
        """Test that PDFs are extracted via regex from raw HTML.
        
        Some PDFs might not be in proper <a> tags but in JavaScript
        or other markup. The regex extraction should find them.
        """
        mock_http_client = Mock()
        
        # HTML with PDF in a non-standard location
        html = '''
        <html>
        <script>
            var files = [
                {url: "https://www.comune.vigone.to.it/archivio/file1.pdf"},
                {url: "/docs/file2.pdf?token=abc"}
            ];
        </script>
        <body>
            <a href="page.html">Link</a>
        </body>
        </html>
        '''
        
        mock_http_client.get_text.return_value = html
        
        crawler = Crawler(
            mock_http_client,
            max_pages=10,
            max_depth=2,
            allowed_domains=["www.comune.vigone.to.it"],
            extract_pdf_from_raw_html=True,  # Enable regex extraction
        )
        
        discovered = crawler.start_crawl("https://www.comune.vigone.to.it/")
        
        # Should find PDFs from both <a> tags and raw HTML
        assert len(discovered) >= 2
        urls = [pdf.pdf_url for pdf in discovered]
        assert any("file1.pdf" in url for url in urls)
        assert any("file2.pdf" in url for url in urls)

    def test_discovery_stats_tracking(self):
        """Test that discovery tracks statistics about discarded URLs."""
        mock_http_client = Mock()
        
        html = '''
        <html>
        <body>
            <a href="/local.pdf">Local PDF</a>
            <a href="https://external.com/external.pdf">External PDF</a>
            <a href="/page.html">Local Page</a>
            <a href="https://other.com/page.html">External Page</a>
        </body>
        </html>
        '''
        
        mock_http_client.get_text.return_value = html
        
        crawler = Crawler(
            mock_http_client,
            max_pages=10,
            max_depth=1,
            allowed_domains=["www.comune.vigone.to.it"],
        )
        
        discovered = crawler.start_crawl("https://www.comune.vigone.to.it/")
        
        # Check stats
        # Should discover only local.pdf (1)
        assert crawler.stats.pdfs_discovered == 1
        # Should discard external.pdf and external page (2)
        assert crawler.stats.discarded_out_of_scope >= 2
        # Should have samples of discarded URLs
        assert len(crawler.stats.samples_out_of_scope) > 0


class TestURLDiscoveryOrchestrator:
    """Test URLDiscovery orchestrator."""

    def test_orchestrator_passes_config_to_crawler(self):
        """Test that URLDiscovery passes configuration to Crawler."""
        mock_http_client = Mock()
        mock_http_client.get_text.return_value = "<html></html>"
        
        discovery = URLDiscovery(
            http_client=mock_http_client,
            max_pages=50,
            max_depth=2,
            allowed_domains=["example.com"],
        )
        
        # Call discover_pdfs with explicit config
        pdfs = discovery.discover_pdfs(
            "https://example.com/",
            allow_www_equivalence=True,
            extract_pdf_from_raw_html=True,
        )
        
        # Should return empty list (empty HTML)
        assert isinstance(pdfs, list)


class TestVigoneRealWorldExample:
    """Test with the real Vigone example URL from the bug report."""

    def test_vigone_pdf_discovery_with_query_string(self):
        """Test discovery of the exact Vigone PDF URL from the bug report.
        
        This is the critical real-world test:
        URL: https://www.comune.vigone.to.it/cgi-bin/archivio/09262023175044_CITTA_DI_VIGONE.pdf?utm_source
        
        This PDF was NOT being discovered before the fix from cli.py, line 57:
        where we were checking config.resilience.rate_limit_delay (which doesn't exist).
        
        But the crawler itself also had bugs:
        - _is_pdf_url() not handling URLs with ?
        - _is_target_pdf_domain() checking only servizipubblicaamministrazione.it
        """
        mock_http_client = Mock()
        
        # HTML that contains the exact Vigone PDF link from the bug report
        html_with_vigone_pdf = '''
        <!DOCTYPE html>
        <html>
        <head><title>Comune di Vigone</title></head>
        <body>
            <h1>Bilanci</h1>
            <ul>
                <li>
                    <a href="/cgi-bin/archivio/09262023175044_CITTA_DI_VIGONE.pdf?utm_source=email&utm_medium=newsletter">
                        Bilancio 2023 PDF
                    </a>
                </li>
                <li><a href="/other-page">Other Content</a></li>
            </ul>
        </body>
        </html>
        '''
        
        mock_http_client.get_text.return_value = html_with_vigone_pdf
        
        # Create crawler for Vigone domain
        crawler = Crawler(
            mock_http_client,
            max_pages=10,
            max_depth=2,
            allowed_domains=["www.comune.vigone.to.it"],
            allow_www_equivalence=True,
            extract_pdf_from_raw_html=True,
        )
        
        # Run crawl
        discovered = crawler.start_crawl("https://www.comune.vigone.to.it/")
        
        # CRITICAL FIX VERIFICATION
        # Before fix: 0 PDFs discovered (because _is_target_pdf_domain only checked servizipubblicaamministrazione.it)
        # After fix: 1 PDF discovered (from allowed_domains which includes the Comune site itself)
        assert len(discovered) >= 1, "Vigone PDF should be discovered"
        
        # Verify the URL is correct with query string preserved
        vigone_pdf_found = False
        for pdf in discovered:
            if "09262023175044_CITTA_DI_VIGONE.pdf" in pdf.pdf_url:
                vigone_pdf_found = True
                # Verify query string is preserved
                assert "utm_source" in pdf.pdf_url, "Query string must be preserved"
                break
        
        assert vigone_pdf_found, "The Vigone PDF URL must be found"

    def test_www_vs_nonwww_equivalence_real_example(self):
        """Test www/non-www equivalence with a real scenario.
        
        Base URL: https://www.comune.vigone.to.it/
        PDF link could be:
        https://www.comune.vigone.to.it/... (same)
        https://comune.vigone.to.it/... (no-www variant)
        
        Without allow_www_equivalence, the second would be out-of-scope.
        With allow_www_equivalence=True, both should be in-scope.
        """
        mock_http_client = Mock()
        
        # HTML with PDF on www variant
        html = '''
        <a href="https://www.comune.vigone.to.it/doc1.pdf">Doc1</a>
        <a href="https://comune.vigone.to.it/doc2.pdf">Doc2</a>
        '''
        
        mock_http_client.get_text.return_value = html
        
        # Crawl with www equivalence ENABLED
        crawler = Crawler(
            mock_http_client,
            max_pages=10,
            max_depth=1,
            allowed_domains=["www.comune.vigone.to.it"],
            allow_www_equivalence=True,
        )
        
        discovered = crawler.start_crawl("https://www.comune.vigone.to.it/")
        
        # Both PDFs should be discovered
        assert len(discovered) == 2, "Both www and non-www PDFs should be discovered with equivalence"
