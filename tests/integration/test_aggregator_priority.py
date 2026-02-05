"""Integration tests for result aggregation with definitivo priority."""

import pytest
from comuni_extractor.extraction.aggregator import ResultAggregator
from comuni_extractor.models import ExtractionResult


class TestAggregatorPriority:
    """Test that aggregator prioritizes definitivo over previsione."""

    def test_definitivo_wins_over_previsione_high_confidence(self):
        """Test definitivo is chosen even when previsione has higher confidence."""
        # Create results for same field
        results = [
            ExtractionResult(
                tipo_bilancio="previsione",
                extracted_fields={"entrate_totali": "1500000"},
                confidence_score=0.95,  # Higher confidence
                pdf_source="bilancio_previsione.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={"entrate_totali": "1450000"},
                confidence_score=0.75,  # Lower confidence
                pdf_source="bilancio_definitivo.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
        ]

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate(results)

        # Definitivo should win despite lower confidence
        assert aggregated["entrate_totali"]["value"] == "1450000"
        assert aggregated["entrate_totali"]["tipo_bilancio"] == "definitivo"
        assert aggregated["entrate_totali"]["pdf_source"] == "bilancio_definitivo.pdf"

    def test_previsione_used_when_no_definitivo(self):
        """Test previsione is used when definitivo is not available."""
        results = [
            ExtractionResult(
                tipo_bilancio="previsione",
                extracted_fields={"entrate_totali": "1500000", "spese_correnti": "1200000"},
                confidence_score=0.85,
                pdf_source="bilancio_previsione.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
        ]

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate(results)

        # Should use previsione when no definitivo exists
        assert aggregated["entrate_totali"]["value"] == "1500000"
        assert aggregated["entrate_totali"]["tipo_bilancio"] == "previsione"

    def test_candidates_list_preserved(self):
        """Test that all candidates are preserved in metadata."""
        results = [
            ExtractionResult(
                tipo_bilancio="previsione",
                extracted_fields={"entrate_totali": "1500000"},
                confidence_score=0.90,
                pdf_source="previsione.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={"entrate_totali": "1450000"},
                confidence_score=0.80,
                pdf_source="definitivo.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={"entrate_totali": "1455000"},
                confidence_score=0.70,
                pdf_source="definitivo_v2.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
        ]

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate(results)

        # Check candidates list
        candidates = aggregated["entrate_totali"]["candidates"]
        assert len(candidates) == 3
        
        # All candidates should be present
        values = [c["value"] for c in candidates]
        assert "1500000" in values
        assert "1450000" in values
        assert "1455000" in values

    def test_multiple_fields_independent_aggregation(self):
        """Test that different fields are aggregated independently."""
        results = [
            ExtractionResult(
                tipo_bilancio="previsione",
                extracted_fields={
                    "entrate_totali": "1500000",
                    "spese_correnti": "1200000",
                },
                confidence_score=0.90,
                pdf_source="previsione.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={
                    "entrate_totali": "1450000",
                    # spese_correnti not found in definitivo
                },
                confidence_score=0.85,
                pdf_source="definitivo.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
        ]

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate(results)

        # entrate_totali should come from definitivo
        assert aggregated["entrate_totali"]["value"] == "1450000"
        assert aggregated["entrate_totali"]["tipo_bilancio"] == "definitivo"

        # spese_correnti should come from previsione (only available there)
        assert aggregated["spese_correnti"]["value"] == "1200000"
        assert aggregated["spese_correnti"]["tipo_bilancio"] == "previsione"

    def test_highest_confidence_within_same_tipo(self):
        """Test that highest confidence wins among same tipo_bilancio."""
        results = [
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={"entrate_totali": "1450000"},
                confidence_score=0.70,
                pdf_source="definitivo_v1.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={"entrate_totali": "1455000"},
                confidence_score=0.90,  # Higher confidence
                pdf_source="definitivo_v2.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
        ]

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate(results)

        # Should pick higher confidence among definitivos
        assert aggregated["entrate_totali"]["value"] == "1455000"
        assert aggregated["entrate_totali"]["confidence_score"] == 0.90

    def test_empty_results_list(self):
        """Test that empty results list returns empty aggregation."""
        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate([])

        assert aggregated == {}

    def test_result_with_no_extracted_fields(self):
        """Test handling of result with empty extracted_fields."""
        results = [
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={},  # No fields extracted
                confidence_score=0.50,
                pdf_source="empty.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
            ExtractionResult(
                tipo_bilancio="previsione",
                extracted_fields={"entrate_totali": "1500000"},
                confidence_score=0.85,
                pdf_source="previsione.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
        ]

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate(results)

        # Should still get previsione value
        assert "entrate_totali" in aggregated
        assert aggregated["entrate_totali"]["value"] == "1500000"

    def test_deterministic_aggregation(self):
        """Test that aggregation is deterministic for same input."""
        results = [
            ExtractionResult(
                tipo_bilancio="previsione",
                extracted_fields={"entrate_totali": "1500000"},
                confidence_score=0.85,
                pdf_source="a.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
            ExtractionResult(
                tipo_bilancio="definitivo",
                extracted_fields={"entrate_totali": "1450000"},
                confidence_score=0.80,
                pdf_source="b.pdf",
                model_name="gpt-4",
                chunks_used=[],
            ),
        ]

        aggregator1 = ResultAggregator()
        aggregator2 = ResultAggregator()
        
        result1 = aggregator1.aggregate(results)
        result2 = aggregator2.aggregate(results)

        # Should get identical results
        assert result1["entrate_totali"]["value"] == result2["entrate_totali"]["value"]
        assert result1["entrate_totali"]["tipo_bilancio"] == result2["entrate_totali"]["tipo_bilancio"]
