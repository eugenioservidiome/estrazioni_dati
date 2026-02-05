"""JSON response parser."""

import json
import re
from typing import Any, Dict, Optional

from comuni_extractor.models import ExtractionResult, FieldSpec


class ResponseParser:
    """Parse LLM extraction responses."""

    @staticmethod
    def parse_field_response(
        response: str,
        field: FieldSpec,
    ) -> ExtractionResult:
        """Parse single field response.
        
        Args:
            response: LLM response text
            field: Field definition
            
        Returns:
            Extraction result
        """
        try:
            # Try to parse JSON
            data = ResponseParser._extract_json(response)

            if data is None:
                return ExtractionResult(
                    field_name=field.name,
                    csv_id=field.csv_id,
                    column=field.column,
                    data_type=field.data_type,
                    value=None,
                    confidence=0.0,
                    extraction_errors=["No JSON found in response"],
                )

            value = data.get("value")
            confidence = float(data.get("confidence", 0.0))

            # Ensure confidence is between 0 and 1
            confidence = max(0.0, min(1.0, confidence))

            return ExtractionResult(
                field_name=field.name,
                csv_id=field.csv_id,
                column=field.column,
                data_type=field.data_type,
                value=value,
                confidence=confidence,
            )

        except Exception as e:
            return ExtractionResult(
                field_name=field.name,
                csv_id=field.csv_id,
                column=field.column,
                data_type=field.data_type,
                value=None,
                confidence=0.0,
                extraction_errors=[str(e)],
            )

    @staticmethod
    def parse_batch_response(
        response: str,
        fields: Dict[str, FieldSpec],
    ) -> Dict[str, ExtractionResult]:
        """Parse batch extraction response.
        
        Args:
            response: LLM response text
            fields: Field definitions keyed by name
            
        Returns:
            Dict of extraction results keyed by field name
        """
        results = {}

        try:
            data = ResponseParser._extract_json(response)

            if data is None:
                # Return empty results
                return {
                    name: ExtractionResult(
                        field_name=name,
                        csv_id=field.csv_id,
                        column=field.column,
                        data_type=field.data_type,
                        value=None,
                        confidence=0.0,
                        extraction_errors=["No JSON found in response"],
                    )
                    for name, field in fields.items()
                }

            # Parse each field result
            for field_name, field in fields.items():
                if field_name in data:
                    field_data = data[field_name]

                    if isinstance(field_data, dict):
                        value = field_data.get("value")
                        confidence = float(field_data.get("confidence", 0.5))
                    else:
                        value = field_data
                        confidence = 0.5

                    confidence = max(0.0, min(1.0, confidence))

                    results[field_name] = ExtractionResult(
                        field_name=field_name,
                        csv_id=field.csv_id,
                        column=field.column,
                        data_type=field.data_type,
                        value=value,
                        confidence=confidence,
                    )
                else:
                    results[field_name] = ExtractionResult(
                        field_name=field_name,
                        csv_id=field.csv_id,
                        column=field.column,
                        data_type=field.data_type,
                        value=None,
                        confidence=0.0,
                    )

        except Exception as e:
            # Return error results for all fields
            results = {
                name: ExtractionResult(
                    field_name=name,
                    csv_id=field.csv_id,
                    column=field.column,
                    data_type=field.data_type,
                    value=None,
                    confidence=0.0,
                    extraction_errors=[str(e)],
                )
                for name, field in fields.items()
            }

        return results

    @staticmethod
    def _extract_json(response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from response.
        
        Args:
            response: LLM response text
            
        Returns:
            Parsed JSON dict or None
        """
        try:
            # Try direct parse first
            return json.loads(response)

        except json.JSONDecodeError:
            pass

        # Try to find JSON in response
        start = response.find("{")
        if start == -1:
            return None

        # Find matching closing brace
        brace_count = 0
        end = -1

        for i in range(start, len(response)):
            if response[i] == "{":
                brace_count += 1
            elif response[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        if end == -1:
            return None

        json_str = response[start:end]

        try:
            return json.loads(json_str)

        except json.JSONDecodeError:
            # Try to fix common JSON errors
            return ResponseParser._repair_json(json_str)

    @staticmethod
    def _repair_json(json_str: str) -> Optional[Dict[str, Any]]:
        """Try to repair malformed JSON.
        
        Args:
            json_str: Malformed JSON string
            
        Returns:
            Parsed JSON dict or None
        """
        try:
            # Fix common issues
            # Remove trailing commas
            json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)

            # Add missing quotes to keys
            json_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)

            # Try parsing again
            return json.loads(json_str)

        except json.JSONDecodeError:
            return None
