"""Cryptographically signed audit logger with hash chain."""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional
import nacl.signing
import nacl.encoding


class AuditLogger:
    """
    Audit logger with Ed25519 signatures and SHA-256 hash chain.

    Each log entry includes:
    - Timestamp
    - Event data (decision, tool call, etc.)
    - SHA-256 hash of previous entry (hash chain)
    - Ed25519 signature of entire entry

    This creates a tamper-evident audit trail.
    """

    def __init__(self, log_path: str, signing_key: Optional[str] = None):
        """
        Initialize audit logger.

        Args:
            log_path: Path to JSONL audit log file
            signing_key: Optional hex-encoded Ed25519 signing key
                        If None, generates a new key
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize or load signing key
        if signing_key:
            self.signing_key = nacl.signing.SigningKey(
                bytes.fromhex(signing_key)
            )
        else:
            self.signing_key = nacl.signing.SigningKey.generate()

        self.verify_key = self.signing_key.verify_key

        # Track previous hash for chain
        self.previous_hash = self._get_last_hash()

    def _get_last_hash(self) -> str:
        """
        Get the hash of the last entry in the log.

        Returns:
            Hash of last entry, or genesis hash if log is empty
        """
        if not self.log_path.exists():
            return self._genesis_hash()

        try:
            with open(self.log_path, 'r') as f:
                # Read last line
                lines = f.readlines()
                if not lines:
                    return self._genesis_hash()

                last_line = lines[-1].strip()
                if last_line:
                    entry = json.loads(last_line)
                    return entry.get('entry_hash', self._genesis_hash())
        except Exception:
            pass

        return self._genesis_hash()

    def _genesis_hash(self) -> str:
        """Generate genesis hash for first entry."""
        return hashlib.sha256(b"AEGIS_GENESIS_BLOCK").hexdigest()

    def log_decision(
        self,
        decision: Dict[str, Any],
        request: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log a decision to the audit trail.

        Args:
            decision: Decision dict from DecisionEngine
            request: Optional original request data

        Returns:
            The logged entry with signature
        """
        timestamp = time.time()

        # Build entry data (what gets signed)
        entry_data = {
            'timestamp': timestamp,
            'event_type': 'decision',
            'decision': decision,
            'request': request,
            'previous_hash': self.previous_hash
        }

        # Calculate hash of this entry
        entry_json = json.dumps(entry_data, sort_keys=True)
        entry_hash = hashlib.sha256(entry_json.encode()).hexdigest()

        # Sign the entry
        signature = self._sign_entry(entry_json)

        # Build final log entry
        log_entry = {
            **entry_data,
            'entry_hash': entry_hash,
            'signature': signature,
            'verify_key': self.verify_key.encode(
                encoder=nacl.encoding.HexEncoder
            ).decode()
        }

        # Write to log file
        self._append_to_log(log_entry)

        # Update previous hash for next entry
        self.previous_hash = entry_hash

        return log_entry

    def log_event(
        self,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Log a generic event.

        Args:
            event_type: Type of event (e.g., 'startup', 'shutdown', 'error')
            event_data: Event data dict

        Returns:
            The logged entry with signature
        """
        timestamp = time.time()

        entry_data = {
            'timestamp': timestamp,
            'event_type': event_type,
            'event_data': event_data,
            'previous_hash': self.previous_hash
        }

        entry_json = json.dumps(entry_data, sort_keys=True)
        entry_hash = hashlib.sha256(entry_json.encode()).hexdigest()
        signature = self._sign_entry(entry_json)

        log_entry = {
            **entry_data,
            'entry_hash': entry_hash,
            'signature': signature,
            'verify_key': self.verify_key.encode(
                encoder=nacl.encoding.HexEncoder
            ).decode()
        }

        self._append_to_log(log_entry)
        self.previous_hash = entry_hash

        return log_entry

    def _sign_entry(self, entry_json: str) -> str:
        """
        Sign an entry with Ed25519.

        Args:
            entry_json: JSON string of entry data

        Returns:
            Hex-encoded signature
        """
        signed = self.signing_key.sign(entry_json.encode())
        return signed.signature.hex()

    def _append_to_log(self, entry: Dict[str, Any]):
        """
        Append entry to JSONL log file.

        Args:
            entry: Log entry dict
        """
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def export_verify_key(self) -> str:
        """
        Export the verification key for distribution.

        Returns:
            Hex-encoded Ed25519 verify key
        """
        return self.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode()

    def export_signing_key(self) -> str:
        """
        Export the signing key (keep secret!).

        Returns:
            Hex-encoded Ed25519 signing key
        """
        return self.signing_key.encode(encoder=nacl.encoding.HexEncoder).decode()[:64]
