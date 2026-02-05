"""Generate download kit for browser extension."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from comuni_extractor.io.manifest import ManifestEntry


class DownloadKitWriter:
    """Generate HTML and CSV download kits."""
    
    def __init__(self, output_dir: Path):
        """Initialize kit writer.
        
        Args:
            output_dir: Output directory for kit files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_kit(
        self,
        entries: List[ManifestEntry],
        comune: str,
        year: int,
    ) -> tuple[Path, Path]:
        """Generate download kit files.
        
        Args:
            entries: List of manifest entries
            comune: Municipality name
            year: Year
            
        Returns:
            Tuple of (html_path, csv_path)
        """
        html_path = self.output_dir / f"links_{comune}_{year}.html"
        csv_path = self.output_dir / f"links_{comune}_{year}.csv"
        
        self._write_html(entries, html_path, comune, year)
        self._write_csv(entries, csv_path)
        
        return html_path, csv_path
    
    def _write_html(
        self,
        entries: List[ManifestEntry],
        path: Path,
        comune: str,
        year: int,
    ) -> None:
        """Write HTML download list.
        
        Args:
            entries: Manifest entries
            path: Output path
            comune: Municipality name
            year: Year
        """
        html_template = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Kit - {comune} {year}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            margin: 0 0 10px 0;
            color: #333;
        }}
        .stats {{
            color: #666;
            font-size: 14px;
        }}
        .instructions {{
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }}
        .pdf-list {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .pdf-item {{
            padding: 15px;
            border-bottom: 1px solid #eee;
        }}
        .pdf-item:last-child {{
            border-bottom: none;
        }}
        .pdf-link {{
            font-size: 16px;
            color: #1976d2;
            text-decoration: none;
            font-weight: 500;
            display: block;
            margin-bottom: 8px;
        }}
        .pdf-link:hover {{
            text-decoration: underline;
        }}
        .meta {{
            font-size: 13px;
            color: #666;
            margin: 5px 0;
        }}
        .anchor-text {{
            font-style: italic;
            color: #888;
        }}
        .source-page {{
            color: #999;
            font-size: 12px;
        }}
        .download-btn {{
            display: inline-block;
            padding: 8px 16px;
            background: #4caf50;
            color: white;
            border-radius: 4px;
            text-decoration: none;
            font-size: 14px;
            margin-top: 8px;
        }}
        .download-btn:hover {{
            background: #45a049;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📥 Download Kit - {comune} {year}</h1>
        <div class="stats">
            <strong>{count} PDF</strong> trovati su servizipubblicaamministrazione.it<br>
            Generato il {timestamp}
        </div>
    </div>
    
    <div class="instructions">
        <h3>📋 Istruzioni</h3>
        <ol>
            <li>Usa l'estensione browser per scaricare i PDF da questa lista</li>
            <li>Salva i PDF in una cartella locale (es. <code>downloads_pdf/</code>)</li>
            <li>Esegui il comando <code>comuni-extractor ingest</code> per importare i PDF</li>
            <li>Esegui il comando <code>comuni-extractor analyze</code> per l'analisi</li>
        </ol>
    </div>
    
    <div class="pdf-list">
        <h2>PDF da scaricare ({count})</h2>
        {items}
    </div>
</body>
</html>
"""
        
        items_html = ""
        for i, entry in enumerate(entries, 1):
            suggested_name = entry.suggested_filename or self._suggest_filename(entry.pdf_url)
            
            items_html += f"""
        <div class="pdf-item">
            <a href="{entry.pdf_url}" class="pdf-link" download="{suggested_name}">
                {i}. {suggested_name}
            </a>
            <div class="meta">
                <span class="anchor-text">"{entry.anchor_text}"</span>
            </div>
            <div class="source-page">
                Trovato in: <a href="{entry.source_page_url}" target="_blank">{entry.source_page_url[:80]}...</a>
            </div>
            <a href="{entry.pdf_url}" class="download-btn" download="{suggested_name}">⬇ Scarica</a>
        </div>
"""
        
        html_content = html_template.format(
            comune=comune.title(),
            year=year,
            count=len(entries),
            timestamp=datetime.now().strftime("%d/%m/%Y %H:%M"),
            items=items_html,
        )
        
        path.write_text(html_content, encoding='utf-8')
    
    def _write_csv(self, entries: List[ManifestEntry], path: Path) -> None:
        """Write CSV download list.
        
        Args:
            entries: Manifest entries
            path: Output path
        """
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'url',
                'suggested_filename',
                'source_page_url',
                'anchor_text',
                'discovered_at',
            ])
            
            for entry in entries:
                suggested_name = entry.suggested_filename or self._suggest_filename(entry.pdf_url)
                writer.writerow([
                    entry.pdf_url,
                    suggested_name,
                    entry.source_page_url,
                    entry.anchor_text,
                    entry.discovered_at,
                ])
    
    def _suggest_filename(self, url: str) -> str:
        """Suggest filename from URL.
        
        Args:
            url: PDF URL
            
        Returns:
            Suggested filename
        """
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        
        # Find last part that looks like a filename
        for part in reversed(path_parts):
            if part and '.' in part:
                return part
        
        # Fallback: use last non-empty part + .pdf
        for part in reversed(path_parts):
            if part:
                return f"{part}.pdf"
        
        return "documento.pdf"
