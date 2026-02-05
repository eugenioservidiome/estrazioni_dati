"""Validators for field values."""

import re
from typing import Any, Optional


class FieldValidator:
    """Validate field values against constraints."""

    # Regex patterns
    EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    PEC_PATTERN = r"^[a-zA-Z0-9._%+-]+@pec\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    PHONE_IT_PATTERN = r"^(\+39|0)?[0-9]{6,14}$"
    IBAN_PATTERN = r"^IT[0-9]{2}[A-Z0-9]{23}$"
    CURRENCY_PATTERN = r"^[\d,.\s]+$"
    PERCENTAGE_PATTERN = r"^[\d.,]+\s*%?$"
    URL_PATTERN = r"^https?://[^\s]+$"

    @staticmethod
    def validate_email(value: str) -> bool:
        """Validate email address.
        
        Args:
            value: Email to validate
            
        Returns:
            True if valid email
        """
        if not isinstance(value, str):
            return False
        return bool(re.match(FieldValidator.EMAIL_PATTERN, value.strip()))

    @staticmethod
    def validate_pec(value: str) -> bool:
        """Validate PEC (certified email) address.
        
        Args:
            value: PEC to validate
            
        Returns:
            True if valid PEC
        """
        if not isinstance(value, str):
            return False
        return bool(re.match(FieldValidator.PEC_PATTERN, value.strip()))

    @staticmethod
    def validate_phone(value: str) -> bool:
        """Validate Italian phone number.
        
        Args:
            value: Phone number to validate
            
        Returns:
            True if valid Italian phone
        """
        if not isinstance(value, str):
            return False
        # Remove common separators
        cleaned = re.sub(r'[\s\-().]', '', value.strip())
        return bool(re.match(FieldValidator.PHONE_IT_PATTERN, cleaned))

    @staticmethod
    def validate_iban(value: str) -> bool:
        """Validate Italian IBAN.
        
        Args:
            value: IBAN to validate
            
        Returns:
            True if valid IBAN
        """
        if not isinstance(value, str):
            return False
        cleaned = re.sub(r'\s', '', value.strip()).upper()
        return bool(re.match(FieldValidator.IBAN_PATTERN, cleaned))

    @staticmethod
    def validate_currency(value: str) -> bool:
        """Validate currency value.
        
        Args:
            value: Currency value to validate
            
        Returns:
            True if valid currency format
        """
        if not isinstance(value, str):
            return False
        # Remove currency symbols
        cleaned = re.sub(r'[€$£¥]', '', value.strip())
        return bool(re.match(FieldValidator.CURRENCY_PATTERN, cleaned))

    @staticmethod
    def validate_percentage(value: str) -> bool:
        """Validate percentage value.
        
        Args:
            value: Percentage to validate
            
        Returns:
            True if valid percentage
        """
        if not isinstance(value, str):
            return False
        cleaned = value.strip()
        return bool(re.match(FieldValidator.PERCENTAGE_PATTERN, cleaned))

    @staticmethod
    def validate_url(value: str) -> bool:
        """Validate URL.
        
        Args:
            value: URL to validate
            
        Returns:
            True if valid URL
        """
        if not isinstance(value, str):
            return False
        return bool(re.match(FieldValidator.URL_PATTERN, value.strip()))

    @staticmethod
    def validate_range(
        value: Any, min_val: Optional[float] = None, max_val: Optional[float] = None
    ) -> bool:
        """Validate numeric range.
        
        Args:
            value: Value to validate
            min_val: Minimum value (inclusive)
            max_val: Maximum value (inclusive)
            
        Returns:
            True if value is in range
        """
        try:
            num = float(value)
            if min_val is not None and num < min_val:
                return False
            if max_val is not None and num > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_required(value: Optional[Any]) -> bool:
        """Validate that value is not empty.
        
        Args:
            value: Value to validate
            
        Returns:
            True if value is not None/empty
        """
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    @staticmethod
    def validate_regex(value: str, pattern: str) -> bool:
        """Validate value against regex pattern.
        
        Args:
            value: Value to validate
            pattern: Regex pattern
            
        Returns:
            True if value matches pattern
        """
        if not isinstance(value, str):
            return False
        try:
            return bool(re.search(pattern, value))
        except re.error:
            return False
