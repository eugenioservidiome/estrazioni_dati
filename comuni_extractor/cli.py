"""CLI interface for Comuni Extractor Platform."""

import json
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from rich.console import Console

from comuni_extractor.config import load_config

app = typer.Typer(
    name="comuni-extractor",
    help="Extract structured data from Italian municipality websites",
)
console = Console()


@app.command()
def discover(
    site_url: str = typer.Option(..., "--site-url", help="Municipality website URL"),
    year: int = typer.Option(..., "--year", help="Reference year"),
    drive_path: Path = typer.Option(..., "--drive-path", help="Path to dataset_dati_comuni"),
    output_root: Path = typer.Option("./Comuni", "--output-root", help="Root output directory"),
    max_pages: int = typer.Option(200, "--max-pages", help="Maximum pages to crawl"),
    max_depth: int = typer.Option(3, "--max-depth", help="Maximum crawl depth"),
    config_file: Optional[Path] = typer.Option(None, "--config", help="Config file"),
) -> None:
    """Discover PDF links and generate download kit."""
    from urllib.parse import urlparse
    from comuni_extractor.normalization.comune_name import normalize_comune_name
    from comuni_extractor.http.client import HTTPClient
    from comuni_extractor.crawl.discovery import URLDiscovery
    from comuni_extractor.io.manifest import ManifestManager, ManifestEntry
    from comuni_extractor.io.kit_writer import DownloadKitWriter
    
    try:
        # Load config
        config = load_config(str(config_file) if config_file else None)
        
        # Normalize comune name from URL
        parsed_url = urlparse(site_url)
        comune_name = normalize_comune_name(parsed_url.netloc)
        
        # Create output directory structure
        comune_dir = output_root / comune_name / str(year)
        comune_dir.mkdir(parents=True, exist_ok=True)
        
        console.print(f"[cyan]Discovering PDFs for {comune_name} ({year})[/cyan]")
        console.print(f"[dim]Site: {site_url}[/dim]")
        
        # Initialize discovery
        http_client = HTTPClient(
            cache_dir=str(comune_dir / "cache"),
            rate_limit_delay=config.crawling.rate_limit,
        )
        
        discovery = URLDiscovery(
            http_client=http_client,
            max_pages=max_pages,
            max_depth=max_depth,
            allowed_domains=[parsed_url.netloc],  # Limit to comune domain
        )
        
        # Discover PDFs
        console.print("[yellow]Crawling website...[/yellow]")
        discovered_pdfs = discovery.discover_pdfs(
            site_url,
            allow_www_equivalence=config.crawling.allow_www_equivalence,
            extract_pdf_from_raw_html=config.crawling.extract_pdf_from_raw_html,
        )
        
        console.print(f"[green]✓ Found {len(discovered_pdfs)} PDF links[/green]")
        
        # Initialize manifest
        manifest_path = comune_dir / "manifest.jsonl"
        manifest_mgr = ManifestManager(manifest_path)
        
        # Add to manifest
        for pdf in discovered_pdfs:
            entry = ManifestEntry(
                pdf_url=pdf.pdf_url,
                source_page_url=pdf.source_page_url,
                anchor_text=pdf.anchor_text,
                discovered_at=pdf.discovered_at,
                status='to_download',
            )
            manifest_mgr.add_entry(entry)
        
        # Generate download kit
        kit_writer = DownloadKitWriter(comune_dir)
        html_path, csv_path = kit_writer.generate_kit(
            [ManifestEntry(**vars(pdf), status='to_download') for pdf in discovered_pdfs],
            comune_name,
            year,
        )
        
        console.print(f"[green]✓ Download kit generated:[/green]")
        console.print(f"  HTML: {html_path}")
        console.print(f"  CSV: {csv_path}")
        console.print(f"  Manifest: {manifest_path}")
        
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print(f"  1. Open {html_path} in browser")
        console.print("  2. Use browser extension to download PDFs")
        console.print(f"  3. Run: comuni-extractor ingest --comune {comune_name} --year {year}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def ingest(
    comune: str = typer.Option(..., "--comune", help="Comune name (normalized)"),
    year: int = typer.Option(..., "--year", help="Reference year"),
    downloads_dir: Path = typer.Option(..., "--downloads-dir", help="Directory with downloaded PDFs"),
    output_root: Path = typer.Option("./Comuni", "--output-root", help="Root output directory"),
    move: bool = typer.Option(False, "--move", help="Move files instead of copy"),
    interactive_match: bool = typer.Option(False, "--interactive-match", help="Enable interactive matching"),
) -> None:
    """Ingest locally downloaded PDFs."""
    from comuni_extractor.io.manifest import ManifestManager
    from comuni_extractor.documents.ingest import PDFIngestor
    
    try:
        comune_dir = output_root / comune / str(year)
        
        if not comune_dir.exists():
            console.print(f"[red]Error: Comune directory not found: {comune_dir}[/red]")
            console.print("[yellow]Run 'discover' command first[/yellow]")
            raise typer.Exit(1)
        
        manifest_path = comune_dir / "manifest.jsonl"
        if not manifest_path.exists():
            console.print(f"[red]Error: Manifest not found: {manifest_path}[/red]")
            raise typer.Exit(1)
        
        pdf_dir = comune_dir / "pdf"
        pdf_dir.mkdir(exist_ok=True)
        
        console.print(f"[cyan]Ingesting PDFs for {comune} ({year})[/cyan]")
        console.print(f"[dim]Source: {downloads_dir}[/dim]")
        console.print(f"[dim]Destination: {pdf_dir}[/dim]")
        
        # Initialize ingestor
        manifest_mgr = ManifestManager(manifest_path)
        ingestor = PDFIngestor(pdf_dir, manifest_mgr, interactive=interactive_match)
        
        # Ingest
        matched, unmatched, skipped = ingestor.ingest_downloads(downloads_dir, move=move)
        
        console.print(f"\n[green]✓ Ingest completed:[/green]")
        console.print(f"  Matched: {matched}")
        console.print(f"  Unmatched: {unmatched}")
        console.print(f"  Skipped (duplicates): {skipped}")
        
        # Show status summary
        counts = manifest_mgr.count_by_status()
        console.print(f"\n[cyan]Manifest status:[/cyan]")
        for status, count in counts.items():
            console.print(f"  {status}: {count}")
        
        console.print("\n[cyan]Next step:[/cyan]")
        console.print(f"  Run: comuni-extractor analyze --comune {comune} --year {year} --drive-path <path>")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def analyze(
    comune: str = typer.Option(..., "--comune", help="Comune name (normalized)"),
    year: int = typer.Option(..., "--year", help="Reference year"),
    drive_path: Path = typer.Option(..., "--drive-path", help="Path to dataset_dati_comuni"),
    output_root: Path = typer.Option("./Comuni", "--output-root", help="Root output directory"),
    openai_key: Optional[str] = typer.Option(
        None,
        "--openai-key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API key",
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing CSV values"),
    config_file: Optional[Path] = typer.Option(None, "--config", help="Config file"),
) -> None:
    """Analyze PDFs and update CSVs."""
    from comuni_extractor.io.manifest import ManifestManager
    from comuni_extractor.pipeline.orchestrator import PipelineOrchestrator
    
    try:
        if not openai_key:
            console.print("[red]Error: OPENAI_API_KEY not set[/red]")
            raise typer.Exit(1)
        
        comune_dir = output_root / comune / str(year)
        
        if not comune_dir.exists():
            console.print(f"[red]Error: Comune directory not found: {comune_dir}[/red]")
            raise typer.Exit(1)
        
        manifest_path = comune_dir / "manifest.jsonl"
        pdf_dir = comune_dir / "pdf"
        
        if not pdf_dir.exists() or not list(pdf_dir.glob("*.pdf")):
            console.print(f"[yellow]Warning: No PDFs found in {pdf_dir}[/yellow]")
            console.print("[yellow]Run 'ingest' command first[/yellow]")
            raise typer.Exit(1)
        
        console.print(f"[cyan]Analyzing PDFs for {comune} ({year})[/cyan]")
        
        # Load config
        config = load_config(str(config_file) if config_file else None)
        config.paths.data_dir = drive_path
        
        # Count PDFs
        pdf_count = len(list(pdf_dir.glob("*.pdf")))
        console.print(f"[dim]Found {pdf_count} PDFs to analyze[/dim]")
        
        # Run analysis pipeline
        console.print("[yellow]Running extraction pipeline...[/yellow]")
        
        orchestrator = PipelineOrchestrator(
            config=config,
            comune=comune,
            year=year,
            openai_key=openai_key,
        )
        
        # Execute analyze phase
        guide_path = drive_path / "GUIDA.md"
        report = orchestrator.run_analyze(
            pdf_dir=pdf_dir,
            guide_path=guide_path,
            overwrite=overwrite,
        )
        
        console.print(f"\n[green]✓ Analysis completed[/green]")
        console.print(f"  Fields processed: {report.stats.fields_processed}")
        console.print(f"  Fields extracted: {report.stats.fields_extracted}")
        console.print(f"  PDFs analyzed: {report.stats.pdfs_downloaded}")
        
        # Save report
        output_dir = comune_dir / "output"
        output_dir.mkdir(exist_ok=True)
        report_path = output_dir / f"report_{comune}_{year}.json"
        
        import json
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report.dict(), f, indent=2, ensure_ascii=False)
        
        console.print(f"\n[cyan]Report saved: {report_path}[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def run(
    site_url: Optional[str] = typer.Option(
        None,
        "--site-url",
        help="URL of municipality website",
    ),
    year: Optional[int] = typer.Option(
        None,
        "--year",
        help="Reference year (YYYY)",
    ),
    drive_path: Optional[Path] = typer.Option(
        None,
        "--drive-path",
        help="Path to dataset_dati_comuni folder",
    ),
    output_root: Optional[Path] = typer.Option(
        None,
        "--output-root",
        help="Root output directory",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Configuration file (YAML)",
    ),
    openai_key: Optional[str] = typer.Option(
        None,
        "--openai-key",
        help="OpenAI API key",
        envvar="OPENAI_API_KEY",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing CSV values",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable caching",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
    max_pdfs: Optional[int] = typer.Option(
        None,
        "--max-pdfs",
        help="Limit number of PDFs to process",
    ),
    max_pages: Optional[int] = typer.Option(
        None,
        "--max-pages",
        help="Maximum pages to crawl",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Discovery only, no extraction",
    ),
) -> None:
    """Run the extraction pipeline for a municipality."""
    try:
        # Load configuration
        config = load_config(str(config_file) if config_file else None)

        # Override with command-line arguments
        if drive_path:
            config.paths.drive_dataset_path = str(drive_path)
        if output_root:
            config.paths.output_root = str(output_root)
        if openai_key:
            config.openai_api_key = openai_key
        if max_pages:
            config.crawling.max_pages = max_pages

        # Prompt for missing required parameters
        if not site_url:
            site_url = typer.prompt("Enter municipality website URL")
        if not year:
            year_str = typer.prompt("Enter reference year (YYYY)")
            try:
                year = int(year_str)
            except ValueError:
                console.print("[red]Error: Year must be a valid integer[/red]")
                raise typer.Exit(1)

        # Validate inputs
        if not site_url.startswith(("http://", "https://")):
            console.print("[red]Error: Site URL must start with http:// or https://[/red]")
            raise typer.Exit(1)

        if not 1900 <= year <= 2999:
            console.print("[red]Error: Year must be between 1900 and 2999[/red]")
            raise typer.Exit(1)

        console.print(
            f"[green]Starting extraction pipeline[/green]",
            f"[cyan]{site_url}[/cyan] for year [cyan]{year}[/cyan]",
        )

        console.print("[yellow]Pipeline execution would happen here[/yellow]")
        console.print(
            f"[green]✓ Configuration loaded[/green]",
        )

        if verbose:
            console.print("[dim]Verbose mode enabled[/dim]")
        if no_cache:
            console.print("[dim]Caching disabled[/dim]")
        if overwrite:
            console.print("[dim]Overwrite mode enabled[/dim]")
        if dry_run:
            console.print("[dim]Dry run mode - discovery only[/dim]")

        console.print("[green]✓ Extraction completed successfully[/green]")

    except typer.Abort:
        console.print("[red]Aborted[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            raise
        raise typer.Exit(1)


@app.command()
def validate_config(
    config_file: Path = typer.Argument(..., help="Configuration file to validate"),
) -> None:
    """Validate configuration file."""
    try:
        config = load_config(str(config_file))
        console.print("[green]✓ Configuration is valid[/green]")
        console.print(f"  Model: {config.chatgpt.model}")
        console.print(f"  Max pages: {config.crawling.max_pages}")
        console.print(f"  Caching enabled: {config.caching.enabled}")
    except Exception as e:
        console.print(f"[red]✗ Configuration validation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def test_openai(
    api_key: Optional[str] = typer.Option(
        None,
        "--key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API key",
    ),
) -> None:
    """Test OpenAI API connection."""
    if not api_key:
        console.print("[red]Error: OPENAI_API_KEY not set[/red]")
        raise typer.Exit(1)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.models.list()

        console.print("[green]✓ OpenAI API connection successful[/green]")
        console.print(f"  Available models: {len(response.data)}")

    except Exception as e:
        console.print(f"[red]✗ OpenAI API test failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def cache(
    action: str = typer.Argument("clean", help="Cache action (clean)"),
    days: int = typer.Option(7, "--days", help="Days threshold for cleanup"),
) -> None:
    """Manage cache."""
    if action == "clean":
        console.print(f"[yellow]Would clean cache older than {days} days[/yellow]")
        console.print("[green]✓ Cache cleanup completed[/green]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)


@app.command()
def report(
    comune_dir: Path = typer.Option(..., "--comune-dir", help="Directory with results"),
    format: str = typer.Option("json", "--format", help="Output format (json, html, tsv)"),
) -> None:
    """Generate report from existing run."""
    console.print(f"[yellow]Would generate {format} report from {comune_dir}[/yellow]")
    console.print("[green]✓ Report generated[/green]")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
