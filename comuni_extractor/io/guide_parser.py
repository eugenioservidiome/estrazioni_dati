"""Parse GUIDA.md field mapping guide."""

import re
from pathlib import Path
from typing import Dict, List, Optional

from comuni_extractor.models import FieldDataType, FieldSpec


class GuideParser:
    """Parse GUIDA.md to extract field specifications."""

    def __init__(self, guide_path: str | Path):
        """Initialize guide parser.
        
        Args:
            guide_path: Path to GUIDA.md file
        """
        self.guide_path = Path(guide_path)
        if not self.guide_path.exists():
            raise FileNotFoundError(f"GUIDA.md not found at {guide_path}")

        with open(self.guide_path, "r", encoding="utf-8") as f:
            self.content = f.read()

    def parse(self) -> List[FieldSpec]:
        """Parse GUIDA.md and return list of FieldSpec objects.
        
        Returns:
            List of FieldSpec objects
        """
        fields = []
        
        # Split by field sections (## Campo: fieldname)
        field_pattern = r"## Campo:\s*(.+?)(?=## Campo:|$)"
        matches = re.finditer(field_pattern, self.content, re.DOTALL)

        for match in matches:
            field_name = match.group(1).strip()
            section = match.group(0)
            
            try:
                field_spec = self._parse_field_section(field_name, section)
                if field_spec:
                    fields.append(field_spec)
            except Exception as e:
                print(f"Warning: Failed to parse field {field_name}: {e}")
                continue

        return fields

    def _parse_field_section(self, field_name: str, section: str) -> Optional[FieldSpec]:
        """Parse a single field section.
        
        Args:
            field_name: Field name
            section: Section text
            
        Returns:
            FieldSpec or None
        """
        data = {"name": field_name.strip()}

        # Extract CSV ID
        csv_match = re.search(r"CSV[\"']?\s*:\s*(\d+)", section, re.IGNORECASE)
        if csv_match:
            data["csv_id"] = int(csv_match.group(1))
        else:
            return None

        # Extract column
        col_match = re.search(
            r"Colonna[\"']?\s*:\s*([^\n]+)", section, re.IGNORECASE
        )
        if col_match:
            data["column"] = col_match.group(1).strip()
        else:
            return None

        # Extract description
        desc_match = re.search(
            r"Descrizione[\"']?\s*:\s*([^\n]+)", section, re.IGNORECASE
        )
        if desc_match:
            data["description"] = desc_match.group(1).strip()

        # Extract data type
        type_match = re.search(
            r"Tipo[\"']?\s*:\s*([^\n]+)", section, re.IGNORECASE
        )
        if type_match:
            type_str = type_match.group(1).strip().lower()
            try:
                data["data_type"] = FieldDataType(type_str)
            except ValueError:
                data["data_type"] = FieldDataType.TEXT

        # Extract regex pattern
        regex_match = re.search(r"Regex[\"']?\s*:\s*`([^`]+)`", section, re.IGNORECASE)
        if regex_match:
            data["regex_pattern"] = regex_match.group(1)

        # Extract query templates
        queries_match = re.search(
            r"Query Templates?[\"']?\s*:\s*\n((?:\s*-\s+\"[^\n]+\"\n?)+)",
            section,
            re.IGNORECASE,
        )
        if queries_match:
            query_section = queries_match.group(1)
            queries = re.findall(r'-\s+"([^"]+)"', query_section)
            data["query_templates"] = queries

        # Extract validators
        validators_match = re.search(
            r"Validators?[\"']?\s*:\s*([^\n]+)", section, re.IGNORECASE
        )
        if validators_match:
            validators_str = validators_match.group(1).strip()
            data["validators"] = [v.strip() for v in validators_str.split(",")]

        # Extract priority keywords
        def_match = re.search(
            r"Priorità Definitivo[\"']?\s*:\s*([^\n]+)", section, re.IGNORECASE
        )
        if def_match:
            keywords_str = def_match.group(1).strip()
            data["priority_definitivo"] = [k.strip() for k in keywords_str.split(",")]

        prev_match = re.search(
            r"Priorità Previsione[\"']?\s*:\s*([^\n]+)", section, re.IGNORECASE
        )
        if prev_match:
            keywords_str = prev_match.group(1).strip()
            data["priority_previsione"] = [k.strip() for k in keywords_str.split(",")]

        # Extract required flag
        required_match = re.search(
            r"(Required|Obbligatorio)[\"']?\s*:\s*(true|yes|1)",
            section,
            re.IGNORECASE,
        )
        if required_match:
            data["required"] = True

        return FieldSpec(**data)

    def find_guide_file(self, dataset_path: Path) -> Optional[Path]:
        """Find GUIDA.md in dataset path.
        
        Args:
            dataset_path: Dataset path to search
            
        Returns:
            Path to GUIDA.md or None
        """
        candidates = list(dataset_path.glob("*GUIDA*")) + list(
            dataset_path.glob("*guida*")
        )
        return candidates[0] if candidates else None
