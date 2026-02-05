"""LLM client for OpenAI API."""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from comuni_extractor.models import ExtractionResult, FieldSpec


class LLMClient:
    """OpenAI API client with caching, retry, and circuit breaking."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.0,
        max_retries: int = 3,
        timeout: int = 60,
        cache_dir: Optional[str] = None,
    ):
        """Initialize LLM client.
        
        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Sampling temperature
            max_retries: Max API retries
            timeout: Request timeout in seconds
            cache_dir: Cache directory for responses
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        self.cache_dir = cache_dir

        openai.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)

        # Circuit breaker
        self.failure_count = 0
        self.last_failure_time = 0
        self.circuit_open = False

    def extract_fields(
        self,
        chunks: List[str],
        fields: List[FieldSpec],
        document_hash: str,
    ) -> List[ExtractionResult]:
        """Extract fields from chunks.
        
        Args:
            chunks: Text chunks
            fields: Field definitions
            document_hash: Document hash for caching
            
        Returns:
            List of extraction results
        """
        results = []

        for field in fields:
            # Check circuit breaker
            if self.circuit_open:
                result = ExtractionResult(
                    field_name=field.field_name,
                    csv_id=field.csv_id,
                    value=None,
                    confidence=0.0,
                    extraction_type="skipped_circuit_open",
                )
                results.append(result)
                continue

            # Try extraction
            result = self._extract_field(chunks, field, document_hash)
            results.append(result)

        return results

    def _extract_field(
        self,
        chunks: List[str],
        field: FieldSpec,
        document_hash: str,
    ) -> ExtractionResult:
        """Extract single field.
        
        Args:
            chunks: Text chunks
            field: Field definition
            document_hash: Document hash
            
        Returns:
            Extraction result
        """
        # Check cache
        cache_key = self._get_cache_key(document_hash, field.field_name)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Build prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(chunks, field)

        # Call API with retry
        try:
            response = self._call_api(system_prompt, user_prompt)

            # Parse response
            result = self._parse_response(response, field)

            # Cache result
            self._save_to_cache(cache_key, result)

            # Reset circuit breaker on success
            self.failure_count = 0
            self.circuit_open = False

            return result

        except Exception as e:
            # Update circuit breaker
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= 5:
                self.circuit_open = True

            # Return error result
            return ExtractionResult(
                field_name=field.field_name,
                csv_id=field.csv_id,
                value=None,
                confidence=0.0,
                extraction_type="error",
                error=str(e),
            )

    @retry(
        retry=retry_if_exception_type(openai.RateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=60, max=300),
    )
    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI API with retry.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            
        Returns:
            API response text
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            timeout=self.timeout,
        )

        return response.choices[0].message.content

    def _build_system_prompt(self) -> str:
        """Build system prompt."""
        return (
            "You are a data extraction expert for Italian municipality documents. "
            "Extract the requested fields accurately and return valid JSON. "
            "Always return a valid JSON object even if extraction fails."
        )

    def _build_user_prompt(self, chunks: List[str], field: FieldSpec) -> str:
        """Build user prompt."""
        context = "\n\n".join(chunks[:5])  # Use top 5 chunks

        return (
            f"Extract the following field from the document:\n\n"
            f"Field: {field.field_name}\n"
            f"Description: {field.description}\n"
            f"Data Type: {field.data_type.value}\n\n"
            f"Document excerpt:\n{context}\n\n"
            f"Return a JSON object with 'value' and 'confidence' (0-1) keys."
        )

    def _parse_response(self, response: str, field: FieldSpec) -> ExtractionResult:
        """Parse API response.
        
        Args:
            response: API response
            field: Field definition
            
        Returns:
            Extraction result
        """
        try:
            # Try to parse JSON
            data = json.loads(response)
            value = data.get("value")
            confidence = data.get("confidence", 0.5)

            return ExtractionResult(
                field_name=field.field_name,
                csv_id=field.csv_id,
                value=value,
                confidence=confidence,
                extraction_type="llm",
            )

        except json.JSONDecodeError:
            # Try to repair JSON
            repaired = self._repair_json(response)
            if repaired:
                return self._parse_response(repaired, field)

            # Return error
            return ExtractionResult(
                field_name=field.field_name,
                csv_id=field.csv_id,
                value=None,
                confidence=0.0,
                extraction_type="parse_error",
                error="Failed to parse JSON response",
            )

    def _repair_json(self, response: str) -> Optional[str]:
        """Try to repair malformed JSON.
        
        Args:
            response: Malformed JSON
            
        Returns:
            Repaired JSON or None
        """
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1

            if start >= 0 and end > start:
                return response[start:end]

        except Exception:
            pass

        return None

    def _get_cache_key(self, document_hash: str, field_name: str) -> str:
        """Generate cache key.
        
        Args:
            document_hash: Document hash
            field_name: Field name
            
        Returns:
            Cache key
        """
        combined = f"{document_hash}_{field_name}_{self.model}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[ExtractionResult]:
        """Get cached result.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None
        """
        if not self.cache_dir:
            return None

        try:
            cache_file = f"{self.cache_dir}/{cache_key}.json"
            with open(cache_file, "r") as f:
                data = json.load(f)
                # Reconstruct ExtractionResult from cached data
                return ExtractionResult(**data)

        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_to_cache(self, cache_key: str, result: ExtractionResult) -> None:
        """Save result to cache.
        
        Args:
            cache_key: Cache key
            result: Result to cache
        """
        if not self.cache_dir:
            return

        try:
            cache_file = f"{self.cache_dir}/{cache_key}.json"
            with open(cache_file, "w") as f:
                json.dump(result.dict(), f)

        except Exception:
            pass
