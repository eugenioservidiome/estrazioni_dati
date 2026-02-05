"""Integration tests for result aggregation with definitivo priority."""

import pytest
from comuni_extractor.extraction.aggregator import ResultAggregator
from comuni_extractor.models import (
    ExtractionCandidate,
    ExtractionResult,
    FieldDataType,
    ValueType,
)


class TestAggregatorPriority:
    """Test that aggregator prioritizes definitivo > consuntivo > previsione > preventivo."""

    def test_definitivo_wins_over_previsione_high_confidence(self):
        """Test definitivo is chosen even when previsione has higher confidence."""
        # Create result with multiple candidates
        result = ExtractionResult(
            field_name="entrate_totali",
            csv_id=1,
            column="entrate_totali",
            data_type=FieldDataType.CURRENCY,
            candidates=[
                ExtractionCandidate(
                    value="1500000",
                    value_type=ValueType.PREVISIONE,
                    confidence=0.95,  # Higher confidence
                    source_pdf="bilancio_previsione.pdf",
                    evidence="Le entrate previste sono 1.500.000 euro",
                ),
                ExtractionCandidate(
                    value="1450000",
                    value_type=ValueType.DEFINITIVO,
                    confidence=0.75,  # Lower confidence
                    source_pdf="bilancio_definitivo.pdf",
                    evidence="Le entrate definitive ammontano a 1.450.000 euro",
                ),
            ],
        )

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate_result(result)

        # Definitivo should win despite lower confidence
        assert aggregated.value == "1450000"
        assert aggregated.value_type == ValueType.DEFINITIVO
        assert aggregated.source_pdf == "bilancio_definitivo.pdf"
        assert aggregated.confidence == 0.75

    def test_consuntivo_wins_over_previsione(self):
        """Test consuntivo beats previsione."""
        result = ExtractionResult(
            field_name="spese_totali",
            csv_id=1,
            column="spese_totali",
            data_type=FieldDataType.CURRENCY,
            candidates=[
                ExtractionCandidate(
                    value="1200000",
                    value_type=ValueType.PREVISIONE,
                    confidence=0.90,
                    source_pdf="previsione.pdf",
                    evidence="Spese previste",
                ),
                ExtractionCandidate(
                    value="1180000",
                    value_type=ValueType.CONSUNTIVO,
                    confidence=0.80,
                    source_pdf="consuntivo.pdf",
                    evidence="Spese a consuntivo",
                ),
            ],
        )

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate_result(result)

        assert aggregated.value == "1180000"
        assert aggregated.value_type == ValueType.CONSUNTIVO

    def test_previsione_used_when_no_higher_priority(self):
        """Test previsione is used when definitivo/consuntivo not available."""
        result = ExtractionResult(
            field_name="entrate_totali",
            csv_id=1,
            column="entrate_totali",
            data_type=FieldDataType.CURRENCY,
            candidates=[
                ExtractionCandidate(
                    value="1500000",
                    value_type=ValueType.PREVISIONE,
                    confidence=0.85,
                    source_pdf="bilancio_previsione.pdf",
                    evidence="Entrate previste",
                ),
            ],
        )

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate_result(result)

        assert aggregated.value == "1500000"
        assert aggregated.value_type == ValueType.PREVISIONE

    def test_highest_confidence_within_same_tipo(self):
        """Test that highest confidence wins among same value_type."""
        result = ExtractionResult(
            field_name="entrate_totali",
            csv_id=1,
            column="entrate_totali",
            data_type=FieldDataType.CURRENCY,
            candidates=[
                ExtractionCandidate(
                    value="1450000",
                    value_type=ValueType.DEFINITIVO,
                    confidence=0.70,
                    source_pdf="definitivo_v1.pdf",
                    evidence="Entrate definitive v1",
                ),
                ExtractionCandidate(
                    value="1455000",
                    value_type=ValueType.DEFINITIVO,
                    confidence=0.90,  # Higher confidence
                    source_pdf="definitivo_v2.pdf",
                    evidence="Entrate definitive v2",
                ),
            ],
        )

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate_result(result)

        # Should pick higher confidence among definitivos
        assert aggregated.value == "1455000"
        assert aggregated.confidence == 0.90
        assert aggregated.source_pdf == "definitivo_v2.pdf"

    def test_empty_candidates_list(self):
        """Test that empty candidates list leaves value as None."""
        result = ExtractionResult(
            field_name="test_field",
            csv_id=1,
            column="test_col",
            data_type=FieldDataType.TEXT,
            candidates=[],
        )

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate_result(result)

        assert aggregated.value is None
        assert aggregated.value_type is None
        assert aggregated.confidence is None

    def test_unknown_value_type_lowest_priority(self):
        """Test that UNKNOWN value_type is used only as last resort."""
        result = ExtractionResult(
            field_name="test_field",
            csv_id=1,
            column="test_col",
            data_type=FieldDataType.TEXT,
            candidates=[
                ExtractionCandidate(
                    value="unknown_value",
                    value_type=ValueType.UNKNOWN,
                    confidence=0.99,  # High confidence
                    source_pdf="unknown.pdf",
                    evidence="Context unclear",
                ),
                ExtractionCandidate(
                    value="preventivo_value",
                    value_type=ValueType.PREVENTIVO,
                    confidence=0.60,  # Lower confidence
                    source_pdf="preventivo.pdf",
                    evidence="Valore preventivato",
                ),
            ],
        )

        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate_result(result)

        # PREVENTIVO should win over UNKNOWN despite lower confidence
        assert aggregated.value == "preventivo_value"
        assert aggregated.value_type == ValueType.PREVENTIVO
