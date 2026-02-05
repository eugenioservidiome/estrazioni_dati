"""Prompt builder for LLM extraction."""

from typing import List, Optional

from comuni_extractor.models import FieldSpec


class PromptBuilder:
    """Build prompts for field extraction."""

    @staticmethod
    def build_system_prompt() -> str:
        """Build system prompt.
        
        Returns:
            System prompt string
        """
        return (
            "You are a data extraction expert specializing in Italian municipal documents. "
            "Your task is to extract structured information with high accuracy. "
            "Always return valid JSON. When a field is not found, set the value to null. "
            "Ensure confidence scores are between 0 and 1."
        )

    @staticmethod
    def build_field_extraction_prompt(
        chunks: List[str],
        field: FieldSpec,
        examples: Optional[dict] = None,
    ) -> str:
        """Build prompt for field extraction.
        
        Args:
            chunks: Text chunks from document
            field: Field definition
            examples: Example extractions
            
        Returns:
            User prompt string
        """
        context = "\n\n".join(chunks[:5])

        prompt = (
            f"Extract the following field from the provided document excerpt:\n\n"
            f"FIELD NAME: {field.field_name}\n"
            f"DESCRIPTION: {field.description}\n"
            f"TYPE: {field.data_type.value}\n"
        )

        # Add field validators if present
        if field.regex:
            prompt += f"FORMAT: Must match regex: {field.regex}\n"

        if field.query_templates:
            prompt += f"SEARCH HINTS: {', '.join(field.query_templates)}\n"

        prompt += (
            f"\nDOCUMENT EXCERPT:\n{context}\n\n"
            f"Return ONLY a JSON object with these keys:\n"
            f'{{"value": <extracted_value_or_null>, "confidence": <0.0_to_1.0>}}\n'
        )

        if examples:
            prompt += f"\nEXAMPLE:\n{examples}\n"

        return prompt

    @staticmethod
    def build_batch_extraction_prompt(
        chunks: List[str],
        fields: List[FieldSpec],
    ) -> str:
        """Build prompt for batch field extraction.
        
        Args:
            chunks: Text chunks
            fields: List of fields to extract
            
        Returns:
            User prompt string
        """
        context = "\n\n".join(chunks[:5])

        fields_spec = "\n".join(
            f"  - {f.field_name} ({f.data_type.value}): {f.description}"
            for f in fields
        )

        return (
            f"Extract the following fields from the document:\n\n"
            f"{fields_spec}\n\n"
            f"DOCUMENT EXCERPT:\n{context}\n\n"
            f"Return a JSON object where keys are field names and values are objects "
            f'with "value" and "confidence" keys.\n'
            f'Example: {{"field1": {{"value": "...", "confidence": 0.9}}, "field2": {{"value": null, "confidence": 0.0}}}}'
        )
