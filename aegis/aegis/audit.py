"""Ed25519-signed, SHA-256 hash-chained audit logger."""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import nacl.signing
import nacl.encoding


class AuditLogger:
    """Tamper-evident audit logger with Ed25519 signatures and hash chaining."""

    def __init__(self, audit_file: Path, signing_key: Optional[nacl.signing.SigningKey] = None):
        """
        Initialize audit logger.

        Args:
            audit_file: Path to JSON Lines audit log file
            signing_key: Ed25519 signing key (generates new if None)
        """
        self.audit_file = audit_file
        self.signing_key = signing_key or nacl.signing.SigningKey.generate()
        self.verify_key = self.signing_key.verify_key
        self.last_hash: Optional[str] = None

        # Create audit file parent directory if needed
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

        # Load last hash if file exists
        if self.audit_file.exists():
            self._load_last_hash()

    def _load_last_hash(self) -> None:
        """Load the hash of the last entry in the audit log."""
        try:
            with open(self.audit_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    self.last_hash = last_entry.get('entry_hash')
        except (IOError, json.JSONDecodeError):
            self.last_hash = None

    def log_decision(
        self,
        tool_call: Dict[str, Any],
        decision: str,
        scan_results: list,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log a firewall decision to the audit trail.

        Args:
            tool_call: The MCP tool call that was evaluated
            decision: 'allow', 'deny', or 'escalate'
            scan_results: List of scanner detection results
            metadata: Optional additional metadata

        Returns:
            The audit entry that was logged
        """
        # Build audit entry
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'tool_name': tool_call.get('name', 'unknown'),
            'decision': decision,
            'scan_results': scan_results,
            'prev_hash': self.last_hash,
        }

        if metadata:
            entry['metadata'] = metadata

        # Calculate hash of entry content (excluding signature)
        entry_json = json.dumps(entry, sort_keys=True)
        entry_hash = hashlib.sha256(entry_json.encode()).hexdigest()
        entry['entry_hash'] = entry_hash

        # Sign the entry hash with Ed25519
        signature = self.signing_key.sign(entry_hash.encode())
        entry['signature'] = signature.signature.hex()
        entry['verify_key'] = self.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode()

        # Write to audit log (append mode, JSON Lines format)
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        # Update last hash for next entry
        self.last_hash = entry_hash

        return entry

    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire audit chain.

        Returns:
            True if chain is valid, False otherwise
        """
        if not self.audit_file.exists():
            return True

        try:
            with open(self.audit_file, 'r') as f:
                lines = f.readlines()

            prev_hash = None
            for line_num, line in enumerate(lines, 1):
                entry = json.loads(line)

                # Check hash chain
                if entry.get('prev_hash') != prev_hash:
                    print(f"Chain break at entry {line_num}: expected prev_hash={prev_hash}, got {entry.get('prev_hash')}")
                    return False

                # Verify signature
                entry_copy = {k: v for k, v in entry.items() if k not in ['signature', 'verify_key', 'entry_hash']}
                entry_json = json.dumps(entry_copy, sort_keys=True)
                computed_hash = hashlib.sha256(entry_json.encode()).hexdigest()

                if computed_hash != entry.get('entry_hash'):
                    print(f"Hash mismatch at entry {line_num}")
                    return False

                # Verify Ed25519 signature
                try:
                    verify_key_hex = entry.get('verify_key', '')
                    verify_key = nacl.signing.VerifyKey(verify_key_hex, encoder=nacl.encoding.HexEncoder)
                    signature_bytes = bytes.fromhex(entry.get('signature', ''))
                    verify_key.verify(computed_hash.encode(), signature_bytes)
                except Exception as e:
                    print(f"Signature verification failed at entry {line_num}: {e}")
                    return False

                prev_hash = entry.get('entry_hash')

            return True

        except Exception as e:
            print(f"Error verifying chain: {e}")
            return False

    def get_signing_key_hex(self) -> str:
        """Get the signing key in hex format for persistence."""
        return self.signing_key.encode(encoder=nacl.encoding.HexEncoder).decode()

    @classmethod
    def from_signing_key_hex(cls, audit_file: Path, signing_key_hex: str) -> 'AuditLogger':
        """Create AuditLogger from hex-encoded signing key."""
        signing_key = nacl.signing.SigningKey(signing_key_hex, encoder=nacl.encoding.HexEncoder)
        return cls(audit_file, signing_key)
