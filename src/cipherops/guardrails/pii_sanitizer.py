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
    """Enterprise PII detection & masking engine for privacy & compliance (KVKK/GDPR).

    Uses re.sub() for single-pass replacements so that character positions stay
    accurate even when multiple PII tokens appear in the same input string.
    """

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

    def _apply_pattern(
        self,
        text: str,
        pattern: re.Pattern,
        placeholder: str,
        pii_type: str,
        matches: List[PIIMatch],
        *,
        validator=None,
    ) -> str:
        """Replace all occurrences of *pattern* in *text* with *placeholder*.

        Uses re.sub() so a single pass replaces all matches and positions are
        computed on the **current** (already-partially-redacted) string to avoid
        offset drift between successive replacements.
        """
        def replace_match(m: re.Match) -> str:
            original = m.group()
            if validator and not validator(original):
                return original  # skip invalid (e.g. TCKN checksum fails)
            matches.append(PIIMatch(pii_type, original, placeholder, m.start(), m.end()))
            return placeholder

        return pattern.sub(replace_match, text)

    def sanitize(self, text: str) -> Tuple[str, List[PIIMatch]]:
        """Scan text and replace sensitive tokens with [REDACTED_*] tokens.

        Replacement order matters: longer / more-specific patterns run first so
        that partial sub-matches don't interfere with subsequent patterns.
        """
        matches: List[PIIMatch] = []

        # 1. API Keys and Tokens (before anything else — most specific)
        for pattern in self.API_KEY_PATTERNS:
            text = self._apply_pattern(text, pattern, "[REDACTED_API_KEY]", "API_KEY", matches)

        # 2. Credit Cards
        text = self._apply_pattern(text, self.CREDIT_CARD_PATTERN, "[REDACTED_CARD]", "CREDIT_CARD", matches)

        # 3. Turkish & International IBAN
        text = self._apply_pattern(text, self.TR_IBAN_PATTERN, "[REDACTED_IBAN]", "IBAN", matches)
        text = self._apply_pattern(text, self.INTL_IBAN_PATTERN, "[REDACTED_IBAN]", "IBAN", matches)

        # 4. TCKN (Verified Checksum)
        text = self._apply_pattern(
            text, self.TCKN_PATTERN, "[REDACTED_TCKN]", "TCKN", matches,
            validator=self.is_valid_tckn,
        )

        # 5. Phone numbers
        text = self._apply_pattern(text, self.TR_PHONE_PATTERN, "[REDACTED_PHONE]", "PHONE", matches)

        # 6. Emails (last — broad pattern)
        text = self._apply_pattern(text, self.EMAIL_PATTERN, "[REDACTED_EMAIL]", "EMAIL", matches)

        return text, matches
