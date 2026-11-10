from cipherops.guardrails.command_validator import CommandValidator, RiskLevel
from cipherops.guardrails.pii_sanitizer import PIISanitizer


def test_tckn_masking():
    sanitizer = PIISanitizer()
    # Test valid algorithm TCKN pattern
    # Valid TCKN sample: 10000000146
    valid_tckn = "10000000146"
    assert PIISanitizer.is_valid_tckn(valid_tckn) is True

    text = f"Müşteri TCKN bilgisi: {valid_tckn} şeklindedir."
    sanitized, matches = sanitizer.sanitize(text)
    assert "[REDACTED_TCKN]" in sanitized
    assert valid_tckn not in sanitized
    assert len(matches) == 1
    assert matches[0].pii_type == "TCKN"


def test_iban_masking():
    sanitizer = PIISanitizer()
    iban = "TR330006100511123456789012"
    text = f"Hesap IBAN numarası: {iban} olarak güncellendi."
    sanitized, matches = sanitizer.sanitize(text)
    assert "[REDACTED_IBAN]" in sanitized
    assert iban not in sanitized
    assert len(matches) == 1
    assert matches[0].pii_type == "IBAN"


def test_api_key_masking():
    sanitizer = PIISanitizer()
    secret = "sk-1234567890abcdef1234567890abcdef"
    text = f"Kullanıcı anahtarı: {secret}"
    sanitized, matches = sanitizer.sanitize(text)
    assert "[REDACTED_API_KEY]" in sanitized
    assert secret not in sanitized


def test_command_firewall_blocks_catastrophic():
    validator = CommandValidator()

    # Blocked root deletion
    res1 = validator.validate("rm -rf /")
    assert res1.risk_level == RiskLevel.BLOCKED

    # Blocked disk format
    res2 = validator.validate("mkfs.ext4 /dev/sda1")
    assert res2.risk_level == RiskLevel.BLOCKED

    # Blocked dd overwrite
    res3 = validator.validate("dd if=/dev/zero of=/dev/sda bs=1M")
    assert res3.risk_level == RiskLevel.BLOCKED

    # Blocked fork bomb
    res4 = validator.validate(":(){ :|:& };:")
    assert res4.risk_level == RiskLevel.BLOCKED


def test_command_firewall_classifies_safe_and_caution():
    validator = CommandValidator()

    # Safe read-only - git, ls are in SAFE_COMMANDS
    safe_res = validator.validate("ls -la && git status")
    assert safe_res.risk_level == RiskLevel.SAFE
    assert safe_res.requires_approval is False

    # Caution - package install, state-altering but not a wrapper or high-risk binary
    caution_res = validator.validate("pip install requests")
    assert caution_res.risk_level == RiskLevel.CAUTION
    assert caution_res.requires_approval is True

    # High risk - rm without catastrophic flag
    high_res = validator.validate("rm -f temp.txt")
    assert high_res.risk_level == RiskLevel.HIGH
    assert high_res.requires_approval is True

    # Execution wrappers are BLOCKED (new behaviour after security hardening)
    wrapper_res = validator.validate("python build.py")
    assert wrapper_res.risk_level == RiskLevel.BLOCKED
