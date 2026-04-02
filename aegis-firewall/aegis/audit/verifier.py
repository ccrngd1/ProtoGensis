"""Audit log verifier for checking integrity and detecting tampering."""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
import nacl.signing
import nacl.encoding


class AuditVerifier:
    """
    Verifies the integrity of audit logs.

    Checks:
    1. Hash chain integrity (each entry links to previous)
    2. Ed25519 signature validity
    3. No gaps or missing entries
    """

    def __init__(self, log_path: str):
        """
        Initialize verifier.

        Args:
            log_path: Path to JSONL audit log file
        """
        self.log_path = Path(log_path)

    def verify(self, verify_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify the entire audit log.

        Args:
            verify_key: Optional hex-encoded Ed25519 verify key
                       If None, uses key from first entry

        Returns:
            Verification result dict with:
            - valid: bool
            - total_entries: int
            - verified_entries: int
            - errors: list of error dicts
        """
        if not self.log_path.exists():
            return {
                'valid': False,
                'total_entries': 0,
                'verified_entries': 0,
                'errors': [{'type': 'file_not_found', 'message': 'Log file does not exist'}]
            }

        entries = self._load_entries()

        if not entries:
            return {
                'valid': True,
                'total_entries': 0,
                'verified_entries': 0,
                'errors': [],
                'message': 'Empty log (valid)'
            }

        # Use verify key from first entry if not provided
        if verify_key is None:
            verify_key = entries[0].get('verify_key')
            if not verify_key:
                return {
                    'valid': False,
                    'total_entries': len(entries),
                    'verified_entries': 0,
                    'errors': [{'type': 'missing_verify_key', 'message': 'No verify key found'}]
                }

        # Parse verify key
        try:
            vk = nacl.signing.VerifyKey(verify_key, encoder=nacl.encoding.HexEncoder)
        except Exception as e:
            return {
                'valid': False,
                'total_entries': len(entries),
                'verified_entries': 0,
                'errors': [{'type': 'invalid_verify_key', 'message': str(e)}]
            }

        # Verify each entry
        errors = []
        verified_count = 0
        previous_hash = self._genesis_hash()

        for i, entry in enumerate(entries):
            # Check hash chain
            expected_prev = previous_hash
            actual_prev = entry.get('previous_hash', '')

            if actual_prev != expected_prev:
                errors.append({
                    'type': 'hash_chain_broken',
                    'entry_index': i,
                    'expected_previous': expected_prev,
                    'actual_previous': actual_prev,
                    'message': f'Hash chain broken at entry {i}'
                })

            # Verify signature
            signature_valid = self._verify_signature(entry, vk)
            if not signature_valid:
                errors.append({
                    'type': 'invalid_signature',
                    'entry_index': i,
                    'message': f'Invalid signature at entry {i}'
                })

            # Verify entry hash
            hash_valid = self._verify_entry_hash(entry)
            if not hash_valid:
                errors.append({
                    'type': 'invalid_hash',
                    'entry_index': i,
                    'message': f'Entry hash mismatch at entry {i}'
                })

            if signature_valid and hash_valid and actual_prev == expected_prev:
                verified_count += 1

            previous_hash = entry.get('entry_hash', '')

        # Overall result
        valid = len(errors) == 0

        return {
            'valid': valid,
            'total_entries': len(entries),
            'verified_entries': verified_count,
            'errors': errors,
            'message': 'All entries verified' if valid else f'Found {len(errors)} errors'
        }

    def _load_entries(self) -> List[Dict[str, Any]]:
        """Load all entries from log file."""
        entries = []
        with open(self.log_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Invalid JSON, will be caught as error
                        pass
        return entries

    def _verify_signature(self, entry: Dict[str, Any], verify_key: nacl.signing.VerifyKey) -> bool:
        """
        Verify Ed25519 signature of an entry.

        Args:
            entry: Log entry dict
            verify_key: Ed25519 verify key

        Returns:
            True if signature is valid
        """
        try:
            # Reconstruct the signed data
            entry_data = {k: v for k, v in entry.items()
                         if k not in ['entry_hash', 'signature', 'verify_key']}
            entry_json = json.dumps(entry_data, sort_keys=True)

            # Get signature
            signature_hex = entry.get('signature', '')
            signature = bytes.fromhex(signature_hex)

            # Verify
            verify_key.verify(entry_json.encode(), signature)
            return True
        except Exception:
            return False

    def _verify_entry_hash(self, entry: Dict[str, Any]) -> bool:
        """
        Verify the hash of an entry matches.

        Args:
            entry: Log entry dict

        Returns:
            True if hash is correct
        """
        try:
            # Reconstruct data that was hashed
            entry_data = {k: v for k, v in entry.items()
                         if k not in ['entry_hash', 'signature', 'verify_key']}
            entry_json = json.dumps(entry_data, sort_keys=True)

            # Calculate hash
            calculated_hash = hashlib.sha256(entry_json.encode()).hexdigest()
            stored_hash = entry.get('entry_hash', '')

            return calculated_hash == stored_hash
        except Exception:
            return False

    def _genesis_hash(self) -> str:
        """Generate genesis hash."""
        return hashlib.sha256(b"AEGIS_GENESIS_BLOCK").hexdigest()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the log.

        Returns:
            Statistics dict
        """
        if not self.log_path.exists():
            return {'error': 'Log file not found'}

        entries = self._load_entries()

        if not entries:
            return {'total_entries': 0, 'event_types': {}}

        # Count event types
        event_types = {}
        for entry in entries:
            event_type = entry.get('event_type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1

        # Get time range
        timestamps = [e.get('timestamp', 0) for e in entries]
        first_timestamp = min(timestamps) if timestamps else 0
        last_timestamp = max(timestamps) if timestamps else 0

        return {
            'total_entries': len(entries),
            'event_types': event_types,
            'first_timestamp': first_timestamp,
            'last_timestamp': last_timestamp,
            'time_span_seconds': last_timestamp - first_timestamp if timestamps else 0
        }
