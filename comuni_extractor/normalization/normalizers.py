"""Normalizers for field values."""

import re
from datetime import datetime
from typing import Any, Optional


class FieldNormalizer:
    """Normalize and transform field values."""

    @staticmethod
    def normalize_currency(value: str) -> Optional[float]:
        """Normalize currency value to float.
        
        Handles formats: "€ 1.234,56", "1.234,56", "1234.56"
        
        Args:
            value: Currency string
            
        Returns:
            Float value or None if invalid
        """
        if not isinstance(value, str):
            return None

        try:
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[€$£¥\s]', '', value.strip())

            # Handle Italian format (comma as decimal separator)
            # If string contains comma, it's likely Italian format
            if ',' in cleaned:
                # Remove thousands separator (period) and replace decimal separator (comma) with period
                cleaned = cleaned.replace('.', '').replace(',', '.')

            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def normalize_phone(value: str) -> Optional[str]:
        """Normalize Italian phone number.
        
        Args:
            value: Phone number string
            
        Returns:
            Normalized phone number or None if invalid
        """
        if not isinstance(value, str):
            return None

        try:
            # Remove common separators
            cleaned = re.sub(r'[\s\-().]', '', value.strip())

            # Handle +39 prefix
            if cleaned.startswith('+39'):
                cleaned = '0' + cleaned[3:]
            elif cleaned.startswith('39'):
                cleaned = '0' + cleaned[2:]

            # Ensure it starts with 0
            if not cleaned.startswith('0'):
                cleaned = '0' + cleaned

            return cleaned
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def normalize_email(value: str) -> Optional[str]:
        """Normalize email address.
        
        Args:
            value: Email string
            
        Returns:
            Normalized email or None if invalid
        """
        if not isinstance(value, str):
            return None

        try:
            return value.strip().lower()
        except AttributeError:
            return None

    @staticmethod
    def normalize_pec(value: str) -> Optional[str]:
        """Normalize PEC (certified email) address.
        
        Args:
            value: PEC string
            
        Returns:
            Normalized PEC or None if invalid
        """
        if not isinstance(value, str):
            return None

        try:
            return value.strip().lower()
        except AttributeError:
            return None

    @staticmethod
    def normalize_date(value: str) -> Optional[str]:
        """Normalize date to ISO format (YYYY-MM-DD).
        
        Handles formats: "DD/MM/YYYY", "DD-MM-YYYY", "YYYY-MM-DD"
        
        Args:
            value: Date string
            
        Returns:
            ISO format date string or None if invalid
        """
        if not isinstance(value, str):
            return None

        value = value.strip()

        # Try various date formats
        formats = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%d/%m/%y",
            "%d-%m-%y",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None

    @staticmethod
    def normalize_percentage(value: str) -> Optional[float]:
        """Normalize percentage to float (0-100).
        
        Handles formats: "12,5%", "12.5%", "12,5", "12.5"
        
        Args:
            value: Percentage string
            
        Returns:
            Float value 0-100 or None if invalid
        """
        if not isinstance(value, str):
            return None

        try:
            # Remove percentage sign and whitespace
            cleaned = re.sub(r'[\s%]', '', value.strip())

            # Handle Italian format (comma as decimal separator)
            if ',' in cleaned:
                cleaned = cleaned.replace(',', '.')

            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def normalize_iban(value: str) -> Optional[str]:
        """Normalize IBAN.
        
        Args:
            value: IBAN string
            
        Returns:
            Normalized IBAN (uppercase, no spaces) or None if invalid
        """
        if not isinstance(value, str):
            return None

        try:
            cleaned = re.sub(r'\s', '', value.strip()).upper()
            return cleaned
        except AttributeError:
            return None

    @staticmethod
    def normalize_country_code(value: str) -> Optional[str]:
        """Normalize country code.
        
        Args:
            value: Country code string
            
        Returns:
            Uppercase country code or None
        """
        if not isinstance(value, str):
            return None

        try:
            return value.strip().upper()
        except AttributeError:
            return None

    @staticmethod
    def normalize_text(value: str, lowercase: bool = False, strip: bool = True) -> Optional[str]:
        """Normalize generic text.
        
        Args:
            value: Text to normalize
            lowercase: Whether to convert to lowercase
            strip: Whether to strip whitespace
            
        Returns:
            Normalized text or None if invalid
        """
        if not isinstance(value, str):
            return None

        try:
            result = value
            if strip:
                result = result.strip()
            if lowercase:
                result = result.lower()
            # Normalize whitespace
            result = re.sub(r'\s+', ' ', result)
            return result
        except AttributeError:
            return None

    @staticmethod
    def normalize_integer(value: Any) -> Optional[int]:
        """Normalize to integer.
        
        Args:
            value: Value to convert
            
        Returns:
            Integer or None if invalid
        """
        try:
            if isinstance(value, str):
                # Remove thousands separators
                cleaned = value.replace('.', '').replace(',', '')
                return int(cleaned)
            return int(value)
        except (ValueError, TypeError, AttributeError):
            return None
