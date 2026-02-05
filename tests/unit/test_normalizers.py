"""Tests for field normalization."""

import pytest

from comuni_extractor.normalization.normalizers import FieldNormalizer
from comuni_extractor.normalization.validators import FieldValidator


class TestFieldValidator:
    """Test FieldValidator class."""

    def test_validate_email_valid(self):
        """Test valid email validation."""
        assert FieldValidator.validate_email("test@example.com") is True

    def test_validate_email_invalid(self):
        """Test invalid email validation."""
        assert FieldValidator.validate_email("not_an_email") is False
        assert FieldValidator.validate_email("") is False
        assert FieldValidator.validate_email(None) is False

    def test_validate_phone_italian(self):
        """Test Italian phone validation."""
        assert FieldValidator.validate_phone("0612345678") is True
        assert FieldValidator.validate_phone("+39 06 1234 5678") is True
        assert FieldValidator.validate_phone("invalid") is False

    def test_validate_currency(self):
        """Test currency validation."""
        assert FieldValidator.validate_currency("1234.56") is True
        assert FieldValidator.validate_currency("€ 1.234,56") is True
        assert FieldValidator.validate_currency("abc") is False

    def test_validate_percentage(self):
        """Test percentage validation."""
        assert FieldValidator.validate_percentage("12.5") is True
        assert FieldValidator.validate_percentage("12,5%") is True
        assert FieldValidator.validate_percentage("invalid") is False

    def test_validate_range(self):
        """Test range validation."""
        assert FieldValidator.validate_range(50, min_val=0, max_val=100) is True
        assert FieldValidator.validate_range(-1, min_val=0, max_val=100) is False
        assert FieldValidator.validate_range(150, min_val=0, max_val=100) is False

    def test_validate_required(self):
        """Test required validation."""
        assert FieldValidator.validate_required("value") is True
        assert FieldValidator.validate_required("") is False
        assert FieldValidator.validate_required(None) is False
        assert FieldValidator.validate_required(1) is True  # Non-zero is truthy


class TestFieldNormalizer:
    """Test FieldNormalizer class."""

    def test_normalize_currency_euro(self):
        """Test currency normalization with euro symbol."""
        result = FieldNormalizer.normalize_currency("€ 1.234,56")
        assert result == 1234.56

    def test_normalize_currency_no_symbol(self):
        """Test currency normalization without symbol."""
        result = FieldNormalizer.normalize_currency("1.234,56")
        assert result == 1234.56

    def test_normalize_currency_english_format(self):
        """Test currency normalization with English format."""
        result = FieldNormalizer.normalize_currency("1234.56")
        assert result == 1234.56

    def test_normalize_currency_invalid(self):
        """Test invalid currency."""
        result = FieldNormalizer.normalize_currency("not_a_number")
        assert result is None

    def test_normalize_phone_italian(self):
        """Test Italian phone normalization."""
        result = FieldNormalizer.normalize_phone("+39 06 1234 5678")
        assert result is not None
        assert result.startswith("06")

    def test_normalize_phone_with_prefix(self):
        """Test phone with +39 prefix."""
        result = FieldNormalizer.normalize_phone("+39 3 12345678")
        assert result is not None

    def test_normalize_email(self):
        """Test email normalization."""
        result = FieldNormalizer.normalize_email("Test@Example.COM")
        assert result == "test@example.com"

    def test_normalize_date_italian_format(self):
        """Test date normalization with Italian format."""
        result = FieldNormalizer.normalize_date("05/02/2024")
        assert result == "2024-02-05"

    def test_normalize_date_iso_format(self):
        """Test date normalization with ISO format."""
        result = FieldNormalizer.normalize_date("2024-02-05")
        assert result == "2024-02-05"

    def test_normalize_date_invalid(self):
        """Test invalid date."""
        result = FieldNormalizer.normalize_date("not_a_date")
        assert result is None

    def test_normalize_percentage(self):
        """Test percentage normalization."""
        result = FieldNormalizer.normalize_percentage("12,5%")
        assert result == 12.5

    def test_normalize_percentage_no_symbol(self):
        """Test percentage without symbol."""
        result = FieldNormalizer.normalize_percentage("12.5")
        assert result == 12.5

    def test_normalize_text(self):
        """Test text normalization."""
        result = FieldNormalizer.normalize_text("  Test  Text  ", lowercase=True)
        assert result == "test text"

    def test_normalize_integer(self):
        """Test integer normalization."""
        result = FieldNormalizer.normalize_integer("1.234")
        assert result == 1234

    def test_normalize_integer_string(self):
        """Test integer from string."""
        result = FieldNormalizer.normalize_integer("1234")
        assert result == 1234

    def test_normalize_integer_invalid(self):
        """Test invalid integer."""
        result = FieldNormalizer.normalize_integer("not_a_number")
        assert result is None
