"""LLM client for OpenAI API."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from comuni_extractor.models import (
    ExtractionCandidate,
    ExtractionResult,
    FieldSpec,
    ValueType,
)
from comuni_extractor.retrieval.chunker import TextChunk


class LLMClient:
    """OpenAI API client with structured output and caching."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.0,
        max_retries: int = 3,
        timeout: int = 60,
        cache_dir: Optional[str | Path] = None,
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
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.client = openai.OpenAI(api_key=api_key)

        # Circuit breaker
        self.failure_count = 0
        self.last_failure_time = 0
        self.circuit_open = False

    def extract_field_candidates(
        self,
        field: FieldSpec,
        chunks: List[TextChunk],
        year: int,
    ) -> ExtractionResult:
        """Extract field candidates from text chunks.
        
        Args:
            field: Field specification
            chunks: List of text chunks (already retrieved/relevant)
            year: Reference year for template substitution
            
        Returns:
            ExtractionResult with candidates
        """
        # Check circuit breaker
        if self.circuit_open:
            return ExtractionResult(
                field_name=field.name,
                csv_id=field.csv_id,
                column=field.column,
                data_type=field.data_type,
                extraction_errors=["Circuit breaker open"],
            )

        # Build cache key
        cache_key = self._get_cache_key(field, chunks)
        
        # Try cache
        cached = self._load_from_cache(cache_key)
        if cached:
            return cached

        # Build prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(field, chunks, year)

        # Call API
        try:
            response_json = self._call_api_structured(system_prompt, user_prompt)
            
            # Parse candidates
            candidates = self._parse_candidates(response_json, chunks)
            
            # Build result
            result = ExtractionResult(
                field_name=field.name,
                csv_id=field.csv_id,
                column=field.column,
                data_type=field.data_type,
                candidates=candidates,
            )
            
            # Cache result
            self._save_to_cache(cache_key, result)
            
            # Reset circuit breaker
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
                field_name=field.name,
                csv_id=field.csv_id,
                column=field.column,
                data_type=field.data_type,
                extraction_errors=[str(e)],
            )

    @retry(
        retry=retry_if_exception_type(openai.RateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=60, max=300),
    )
    def _call_api_structured(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call OpenAI API with structured output.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            
        Returns:
            Parsed JSON response
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            timeout=self.timeout,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return json.loads(content)

    def _build_system_prompt(self) -> str:
        """Build system prompt for structured extraction."""
        return (
            "You are a data extraction expert specializing in Italian municipal budget documents. "
            "Your task is to extract specific information and return it in valid JSON format. "
            "You must always return a JSON object with a 'candidates' array. "
            "Each candidate represents a potential value found in the documents. "
            "If you cannot find the requested information, return an empty candidates array. "
            "Never invent data - only extract what is explicitly stated in the text."
        )

    def _build_user_prompt(
        self,
        field: FieldSpec,
        chunks: List[TextChunk],
        year: int,
    ) -> str:
        """Build user prompt for field extraction."""
        # Build context with chunk IDs and source tracking
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            # Extract PDF filename from chunk_id (format: filename_chunk_N)
            pdf_name = chunk.chunk_id.split("_chunk_")[0]
            context_parts.append(
                f"--- CHUNK {i} | PDF: {pdf_name} ---\n{chunk.text}\n"
            )
        
        context = "\n".join(context_parts)
        
        # Substitute {year} in query templates
        query_examples = ""
        if field.query_templates:
            templates = [t.replace("{year}", str(year)) for t in field.query_templates]
            query_examples = f"\nSearch hints: {', '.join(templates)}"
        
        # Build regex hint
        regex_hint = ""
        if field.regex_pattern:
            regex_hint = f"\nFormat constraint: Must match regex pattern {field.regex_pattern}"
        
        prompt = (
            f"Extract the following field from the document chunks below:\n\n"
            f"FIELD: {field.name}\n"
            f"DESCRIPTION: {field.description}\n"
            f"DATA TYPE: {field.data_type.value}"
            f"{query_examples}"
            f"{regex_hint}\n\n"
            f"DOCUMENT CHUNKS:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"- Return a JSON object with a 'candidates' array\n"
            f"- Each candidate must have: value (string or null), confidence (0.0-1.0), "
            f"value_type ('definitivo'/'consuntivo'/'previsione'/'preventivo'/'unknown'), "
            f"source_pdf (filename), evidence (exact quote from text)\n"
            f"- Include multiple candidates if you find the field in multiple PDFs or with different types\n"
            f"- Set value_type based on document context (definitivo/consuntivo for final data, "
            f"previsione/preventivo for forecasts, unknown if unclear)\n"
            f"- Evidence must be a direct quote from the chunk text that supports the extracted value\n"
            f"- If field not found, return empty candidates array\n\n"
            f"RESPONSE FORMAT:\n"
            f'{{"candidates": [{{"value": "...", "confidence": 0.95, "value_type": "definitivo", '
            f'"source_pdf": "filename.pdf", "evidence": "exact quote from text"}}]}}'
        )
        
        return prompt

    def _parse_candidates(
        self,
        response_json: Dict[str, Any],
        chunks: List[TextChunk],
    ) -> List[ExtractionCandidate]:
        """Parse candidates from API response.
        
        Args:
            response_json: JSON response from API
            chunks: Source chunks (for validation)
            
        Returns:
            List of ExtractionCandidate objects
        """
        candidates = []
        
        raw_candidates = response_json.get("candidates", [])
        
        for raw_cand in raw_candidates:
            try:
                # Parse value_type
                value_type_str = raw_cand.get("value_type", "unknown").lower()
                try:
                    value_type = ValueType(value_type_str)
                except ValueError:
                    value_type = ValueType.UNKNOWN
                
                # Create candidate
                candidate = ExtractionCandidate(
                    value=raw_cand.get("value") or "",
                    value_type=value_type,
                    confidence=float(raw_cand.get("confidence", 0.0)),
                    source_pdf=raw_cand.get("source_pdf", ""),
                    evidence=raw_cand.get("evidence", ""),
                    model=self.model,
                    raw_response=raw_cand,
                )
                
                candidates.append(candidate)
                
            except Exception:
                # Skip invalid candidates
                continue
        
        return candidates

    def _get_cache_key(self, field: FieldSpec, chunks: List[TextChunk]) -> str:
        """Generate cache key based on field and chunks.
        
        Args:
            field: Field specification
            chunks: Text chunks
            
        Returns:
            Cache key (hash)
        """
        # Create deterministic key from field name, model, and chunk IDs
        chunk_ids = "_".join([c.chunk_id for c in chunks])
        combined = f"{field.name}_{self.model}_{chunk_ids}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[ExtractionResult]:
        """Load cached result.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached ExtractionResult or None
        """
        if not self.cache_dir:
            return None

        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ExtractionResult(**data)
        except Exception:
            return None

    def _save_to_cache(self, cache_key: str, result: ExtractionResult) -> None:
        """Save result to cache.
        
        Args:
            cache_key: Cache key
            result: Result to cache
        """
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        except Exception:
            pass
