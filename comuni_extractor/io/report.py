"""Generate and manage run reports."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from comuni_extractor.models import RunReport


class ReportGenerator:
    """Generate and save run reports."""

    def __init__(self, output_dir: Path):
        """Initialize report generator.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_report_path(self, comune: str, year: int) -> Path:
        """Get report file path.
        
        Args:
            comune: Comune name (normalized)
            year: Year
            
        Returns:
            Path to report file
        """
        filename = f"report_{comune}_{year}.json"
        return self.output_dir / filename

    def save_report(self, report: RunReport) -> Path:
        """Save report to JSON file.
        
        Args:
            report: RunReport object
            
        Returns:
            Path to saved report file
        """
        path = self.get_report_path(report.comune_name_normalized, report.year)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        return path

    def load_report(self, report_path: Path) -> Optional[RunReport]:
        """Load report from file.
        
        Args:
            report_path: Path to report file
            
        Returns:
            RunReport or None if not found
        """
        if not report_path.exists():
            return None

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return RunReport(**data)
        except Exception as e:
            raise RuntimeError(f"Failed to load report from {report_path}: {e}")

    def generate_summary(self, report: RunReport) -> str:
        """Generate human-readable summary of report.
        
        Args:
            report: RunReport object
            
        Returns:
            Summary string
        """
        lines = [
            f"Run Report: {report.comune_name} ({report.year})",
            f"Website: {report.site_url}",
            f"Timestamp: {report.run_timestamp.isoformat()}",
            "",
            "Statistics:",
            f"  Pages crawled: {report.stats.crawl_stats.pages_visited}",
            f"  PDFs discovered: {report.stats.download_stats.pdfs_attempted}",
            f"  PDFs downloaded: {report.stats.download_stats.pdfs_successful}",
            f"  PDFs skipped/failed: {report.stats.download_stats.pdfs_skipped + report.stats.download_stats.pdfs_failed}",
            f"  Fields processed: {report.stats.extraction_stats.fields_processed}",
            f"  Fields extracted: {report.stats.extraction_stats.fields_extracted}",
            f"  LLM API calls: {report.stats.extraction_stats.llm_api_calls}",
            f"  Duration: {report.stats.duration_seconds:.1f}s",
            "",
            "Extraction Results:",
        ]

        for field in report.fields:
            status = "✓" if field.value else "✗"
            confidence = f"{field.confidence:.1%}" if field.confidence else "N/A"
            lines.append(
                f"  {status} {field.field_name}: {field.value} (confidence: {confidence})"
            )

        if report.errors:
            lines.extend(["", "Errors:"])
            for error in report.errors[:5]:  # Show first 5 errors
                lines.append(f"  - {error.error_type}: {error.message}")

            if len(report.errors) > 5:
                lines.append(f"  ... and {len(report.errors) - 5} more errors")

        if report.warnings:
            lines.extend(["", "Warnings:"])
            for warning in report.warnings[:5]:
                lines.append(f"  - {warning}")

            if len(report.warnings) > 5:
                lines.append(f"  ... and {len(report.warnings) - 5} more warnings")

        return "\n".join(lines)

    def export_tsv(self, report: RunReport, output_path: Path) -> None:
        """Export extraction results as TSV.
        
        Args:
            report: RunReport object
            output_path: Path to save TSV file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            # Header
            f.write(
                "Field\tCSV ID\tColumn\tValue\tType\tConfidence\tSource PDF\tSource URL\tValidation\n"
            )

            # Rows
            for field in report.fields:
                row = [
                    field.field_name,
                    str(field.csv_id),
                    field.column,
                    field.value or "",
                    field.value_type or "",
                    f"{field.confidence:.2f}" if field.confidence else "",
                    field.source_pdf or "",
                    field.source_url or "",
                    "Pass" if field.validation_passed else "Fail",
                ]
                f.write("\t".join(row) + "\n")

    def export_html(self, report: RunReport, output_path: Path) -> None:
        """Export report as HTML.
        
        Args:
            report: RunReport object
            output_path: Path to save HTML file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Extraction Report: {report.comune_name} ({report.year})</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .metadata {{ background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }}
        .stats {{ display: grid; grid-cols: auto auto; gap: 10px; margin: 20px 0; }}
        .stat-item {{ border: 1px solid #ddd; padding: 10px; }}
        .stat-label {{ font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th {{ background: #4CAF50; color: white; padding: 10px; text-align: left; }}
        td {{ border: 1px solid #ddd; padding: 8px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        .error {{ background: #ffe6e6; padding: 10px; margin: 5px 0; border-left: 4px solid red; }}
        .warning {{ background: #fffacd; padding: 10px; margin: 5px 0; border-left: 4px solid orange; }}
    </style>
</head>
<body>
    <h1>Extraction Report: {report.comune_name} ({report.year})</h1>
    
    <div class="metadata">
        <p><strong>Website:</strong> {report.site_url}</p>
        <p><strong>Run Time:</strong> {report.run_timestamp.isoformat()}</p>
        <p><strong>Duration:</strong> {report.stats.duration_seconds:.1f}s</p>
    </div>

    <h2>Statistics</h2>
    <div class="stats">
        <div class="stat-item">
            <div class="stat-label">Pages Crawled</div>
            <div>{report.stats.crawl_stats.pages_visited}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">PDFs Downloaded</div>
            <div>{report.stats.download_stats.pdfs_successful}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Fields Extracted</div>
            <div>{report.stats.extraction_stats.fields_extracted}/{report.stats.extraction_stats.fields_processed}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">API Calls</div>
            <div>{report.stats.extraction_stats.llm_api_calls}</div>
        </div>
    </div>

    <h2>Extraction Results</h2>
    <table>
        <tr>
            <th>Field</th>
            <th>Column</th>
            <th>Value</th>
            <th>Type</th>
            <th>Confidence</th>
            <th>Source</th>
            <th>Status</th>
        </tr>
"""

        for field in report.fields:
            status_class = "pass" if field.validation_passed else "fail"
            status_text = "✓" if field.validation_passed else "✗"
            confidence = (
                f"{field.confidence:.1%}"
                if field.confidence
                else "N/A"
            )

            html += f"""        <tr>
            <td>{field.field_name}</td>
            <td>{field.column}</td>
            <td>{field.value or "-"}</td>
            <td>{field.value_type or "-"}</td>
            <td>{confidence}</td>
            <td>{field.source_pdf or "-"}</td>
            <td class="{status_class}">{status_text}</td>
        </tr>
"""

        html += """    </table>
"""

        if report.errors:
            html += "    <h2>Errors</h2>\n"
            for error in report.errors[:10]:
                html += f'    <div class="error"><strong>{error.error_type}:</strong> {error.message}</div>\n'

        if report.warnings:
            html += "    <h2>Warnings</h2>\n"
            for warning in report.warnings[:10]:
                html += f'    <div class="warning">{warning}</div>\n'

        html += """</body>
</html>
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
