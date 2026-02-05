"""Aggregate extraction results from multiple PDFs."""

from typing import List, Optional

from comuni_extractor.models import ExtractionCandidate, ExtractionResult, ValueType


class ResultAggregator:
    """Aggregate extraction results across all PDFs."""

    @staticmethod
    def aggregate_candidates(candidates: List[ExtractionCandidate]) -> Optional[str]:
        """Select best candidate value from list.
        
        Priority: definitivo > previsione > other
        Within same type: highest confidence wins
        
        Args:
            candidates: List of candidate values
            
        Returns:
            Selected value or None
        """
        if not candidates:
            return None

        # Group by type
        by_type: dict[ValueType, List[ExtractionCandidate]] = {}
        for cand in candidates:
            if cand.value_type not in by_type:
                by_type[cand.value_type] = []
            by_type[cand.value_type].append(cand)

        # Priority order
        priority = [ValueType.DEFINITIVO, ValueType.CONSUNTIVO, ValueType.PREVISIONE, ValueType.PREVENTIVO]

        # Find best value
        for value_type in priority:
            if value_type in by_type:
                type_candidates = by_type[value_type]
                # Sort by confidence
                type_candidates.sort(key=lambda x: x.confidence, reverse=True)
                if type_candidates:
                    return type_candidates[0].value

        # Fallback: highest confidence overall
        if candidates:
            candidates_sorted = sorted(candidates, key=lambda x: x.confidence, reverse=True)
            return candidates_sorted[0].value

        return None

    @staticmethod
    def aggregate_result(result: ExtractionResult) -> ExtractionResult:
        """Aggregate an extraction result from its candidates.
        
        Updates result.value and result.value_type based on aggregation strategy.
        
        Args:
            result: ExtractionResult to aggregate
            
        Returns:
            Updated ExtractionResult
        """
        if not result.candidates:
            return result

        # Aggregate candidates
        best_value = ResultAggregator.aggregate_candidates(result.candidates)

        if best_value:
            # Find the candidate with this value
            best_candidate = None
            for cand in result.candidates:
                if cand.value == best_value:
                    best_candidate = cand
                    break

            if best_candidate:
                result.value = best_value
                result.value_type = best_candidate.value_type
                result.confidence = best_candidate.confidence
                result.source_pdf = best_candidate.source_pdf
                result.source_url = best_candidate.source_url
                result.evidence_snippet = best_candidate.evidence

        return result

    @staticmethod
    def aggregate_results(results: List[ExtractionResult]) -> List[ExtractionResult]:
        """Aggregate multiple extraction results.
        
        Args:
            results: List of ExtractionResult objects
            
        Returns:
            Aggregated results
        """
        aggregated = []
        for result in results:
            agg_result = ResultAggregator.aggregate_result(result)
            aggregated.append(agg_result)
        return aggregated
