"""Vendored AEGIS scanners (stdlib `re` only).

Source: /root/projects/protoGen/aegis-firewall/aegis/scanners/
protoGen commit: dbf1aae837e69bfd27d0c1954ec9afb253dff993
Files vendored verbatim: secret_scanner.py, pii_detector.py, extract.py
Vendored for PolicyGate's scan-artifacts (AC #21) and secret_in_args
predicate (AC #5). See THIRD_PARTY_NOTICES.md.
"""

from .secret_scanner import SecretScanner
from .pii_detector import PIIDetector
from .extract import extract_strings

__all__ = ["SecretScanner", "PIIDetector", "extract_strings"]
