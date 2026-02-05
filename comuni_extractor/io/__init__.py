"""I/O module for Comuni Extractor."""

from comuni_extractor.io.checkpoint import CheckpointManager
from comuni_extractor.io.csv_handler import CSVHandler
from comuni_extractor.io.guide_parser import GuideParser
from comuni_extractor.io.report import ReportGenerator
from comuni_extractor.io.manifest import ManifestManager, ManifestEntry
from comuni_extractor.io.kit_writer import DownloadKitWriter

__all__ = [
    "CheckpointManager",
    "CSVHandler",
    "GuideParser",
    "ReportGenerator",
    "ManifestManager",
    "ManifestEntry",
    "DownloadKitWriter",
]
