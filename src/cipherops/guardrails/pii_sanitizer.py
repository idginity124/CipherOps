import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class PIIMatch:
    pii_type: str
    original_value: str
    redacted_value: str
    start: int
    end: int


class PIISanitizer:
    """Enterprise PII detection & masking engine for privacy & compliance (KVKK/GDPR)."""

    # Pre-compiled regex patterns
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    TR_IBAN_PATTERN = re.compile(r"\bTR[0-9]{2}\s?(?:[0-9]{4}\s?){5}[0-9]{2}\b", re.IGNORECASE)
    INTL_IBAN_PATTERN = re.compile(r"\b[A-Z]{2}[0-9]{2}(?:[0-9A-Z]{4}){3,7}[0-9A-Z]{1,4}\b")
    CREDIT_CARD_PATTERN = re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13})\b|"
        r"\b(?:[0-9]{4}[-\s]){3}[0-9]{4}\b"
    )
    TR_PHONE_PATTERN = re.compile(r"(?:\+90|0)?\s?5[0-9]{2}[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}\b")
    API_KEY_PATTERNS = [
        re.compile(r"\b(?:sk-[a-zA-Z0-9]{24,64})\b"),  # OpenAI-like keys
        re.compile(r"\b(?:ghp_[a-zA-Z0-9]{36})\b"),    # GitHub tokens
        re.compile(r"\b(?:AKIA[0-9A-Z]{16})\b"),        # AWS Access Key
        re.compile(r"(?i)\b(?:bearer\s+[a-zA-Z0-9_\-\.]{20,})\b"),
    ]
    TCKN_PATTERN = re.compile(r"\b[1-9][0-9]{10}\b")

    @staticmethod
    def is_valid_tckn(tckn: str) -> bool:
        """Validate Turkish Republic ID Number checksum algorithm."""
        if len(tckn) != 11 or not tckn.isdigit() or tckn[0] == "0":
            return False

        digits = [int(c) for c in tckn]
        d1_to_9_odds = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
        d2_to_8_evens = digits[1] + digits[3] + digits[5] + digits[7]

        tenth = ((d1_to_9_odds * 7) - d2_to_8_evens) % 10
        if tenth != digits[9]:
            return False

        eleventh = sum(digits[:10]) % 10
        return eleventh == digits[10]

    def sanitize(self, text: str) -> Tuple[str, List[PIIMatch]]:
        """Scan text and replace sensitive tokens with [REDACTED_*] tokens."""
        matches: List[PIIMatch] = []
        sanitized = text

        # 1. API Keys and Tokens
        for pattern in self.API_KEY_PATTERNS:
            for match in pattern.finditer(sanitized):
                val = match.group()
                sanitized = sanitized.replace(val, "[REDACTED_API_KEY]")
                matches.append(PIIMatch("API_KEY", val, "[REDACTED_API_KEY]", match.start(), match.end()))

        # 2. Credit Cards
        for match in self.CREDIT_CARD_PATTERN.finditer(sanitized):
            val = match.group()
            sanitized = sanitized.replace(val, "[REDACTED_CARD]")
            matches.append(PIIMatch("CREDIT_CARD", val, "[REDACTED_CARD]", match.start(), match.end()))

        # 3. Turkish & International IBAN
        for match in self.TR_IBAN_PATTERN.finditer(sanitized):
            val = match.group()
            sanitized = sanitized.replace(val, "[REDACTED_IBAN]")
            matches.append(PIIMatch("IBAN", val, "[REDACTED_IBAN]", match.start(), match.end()))

        # 4. TCKN (Verified Checksum)
        for match in self.TCKN_PATTERN.finditer(sanitized):
            val = match.group()
            if self.is_valid_tckn(val):
                sanitized = sanitized.replace(val, "[REDACTED_TCKN]")
                matches.append(PIIMatch("TCKN", val, "[REDACTED_TCKN]", match.start(), match.end()))

        # 5. Phone numbers
        for match in self.TR_PHONE_PATTERN.finditer(sanitized):
            val = match.group()
            sanitized = sanitized.replace(val, "[REDACTED_PHONE]")
            matches.append(PIIMatch("PHONE", val, "[REDACTED_PHONE]", match.start(), match.end()))

        # 6. Emails
        for match in self.EMAIL_PATTERN.finditer(sanitized):
            val = match.group()
            sanitized = sanitized.replace(val, "[REDACTED_EMAIL]")
            matches.append(PIIMatch("EMAIL", val, "[REDACTED_EMAIL]", match.start(), match.end()))

        return sanitized, matches
