"""Tests for audit logging and chain verification."""

import pytest
import json
from pathlib import Path
from aegis.audit import AuditLogger


class TestAuditLogger:
    """Test Ed25519-signed, hash-chained audit logging."""

    def test_creates_audit_file(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        tool_call = {'name': 'test_tool', 'arguments': {}}
        logger.log_decision(tool_call, 'allow', [])

        assert audit_file.exists()

    def test_logs_decision(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        tool_call = {'name': 'test_tool', 'arguments': {'key': 'value'}}
        scan_results = [{'type': 'shell_injection', 'severity': 'high'}]

        entry = logger.log_decision(tool_call, 'deny', scan_results)

        assert entry['tool_name'] == 'test_tool'
        assert entry['decision'] == 'deny'
        assert len(entry['scan_results']) == 1
        assert 'timestamp' in entry
        assert 'entry_hash' in entry
        assert 'signature' in entry
        assert 'verify_key' in entry

    def test_hash_chain_links(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        # Log first entry
        tool_call1 = {'name': 'tool1', 'arguments': {}}
        entry1 = logger.log_decision(tool_call1, 'allow', [])

        assert entry1['prev_hash'] is None  # First entry

        # Log second entry
        tool_call2 = {'name': 'tool2', 'arguments': {}}
        entry2 = logger.log_decision(tool_call2, 'deny', [])

        assert entry2['prev_hash'] == entry1['entry_hash']  # Chained

        # Log third entry
        tool_call3 = {'name': 'tool3', 'arguments': {}}
        entry3 = logger.log_decision(tool_call3, 'escalate', [])

        assert entry3['prev_hash'] == entry2['entry_hash']  # Chained

    def test_verifies_valid_chain(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        # Log multiple entries
        for i in range(10):
            tool_call = {'name': f'tool{i}', 'arguments': {}}
            logger.log_decision(tool_call, 'allow', [])

        # Verify chain
        assert logger.verify_chain() is True

    def test_detects_tampered_entry(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        # Log entries
        for i in range(5):
            tool_call = {'name': f'tool{i}', 'arguments': {}}
            logger.log_decision(tool_call, 'allow', [])

        # Tamper with middle entry
        with open(audit_file, 'r') as f:
            lines = f.readlines()

        # Modify the decision in the middle entry
        middle_entry = json.loads(lines[2])
        middle_entry['decision'] = 'TAMPERED'
        lines[2] = json.dumps(middle_entry) + '\n'

        with open(audit_file, 'w') as f:
            f.writelines(lines)

        # Verification should fail
        new_logger = AuditLogger(audit_file)
        assert new_logger.verify_chain() is False

    def test_detects_broken_chain(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        # Log entries
        for i in range(5):
            tool_call = {'name': f'tool{i}', 'arguments': {}}
            logger.log_decision(tool_call, 'allow', [])

        # Break the chain by modifying prev_hash
        with open(audit_file, 'r') as f:
            lines = f.readlines()

        entry = json.loads(lines[3])
        entry['prev_hash'] = 'broken_hash_value'
        lines[3] = json.dumps(entry) + '\n'

        with open(audit_file, 'w') as f:
            f.writelines(lines)

        # Verification should fail
        new_logger = AuditLogger(audit_file)
        assert new_logger.verify_chain() is False

    def test_long_chain_verification(self, tmp_path):
        """Test 100 sequential calls as per acceptance criteria."""
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        # Log 100 entries
        for i in range(100):
            tool_call = {'name': f'tool{i}', 'arguments': {'index': i}}
            logger.log_decision(tool_call, 'allow' if i % 2 == 0 else 'deny', [])

        # Verify entire chain
        assert logger.verify_chain() is True

        # Check that all entries are present
        with open(audit_file, 'r') as f:
            lines = f.readlines()
        assert len(lines) == 100

    def test_signing_key_persistence(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        logger1 = AuditLogger(audit_file)

        # Get signing key
        signing_key_hex = logger1.get_signing_key_hex()

        # Log entry
        tool_call = {'name': 'test', 'arguments': {}}
        logger1.log_decision(tool_call, 'allow', [])

        # Create new logger with same key
        logger2 = AuditLogger.from_signing_key_hex(audit_file, signing_key_hex)

        # Log another entry
        logger2.log_decision(tool_call, 'deny', [])

        # Verify chain
        assert logger2.verify_chain() is True

    def test_loads_last_hash_on_init(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"

        # First logger writes entries
        logger1 = AuditLogger(audit_file)
        for i in range(3):
            tool_call = {'name': f'tool{i}', 'arguments': {}}
            entry = logger1.log_decision(tool_call, 'allow', [])
            last_hash = entry['entry_hash']

        # Second logger should load last hash
        logger2 = AuditLogger(audit_file)
        assert logger2.last_hash == last_hash

        # Continue chain
        tool_call = {'name': 'tool4', 'arguments': {}}
        entry = logger2.log_decision(tool_call, 'allow', [])
        assert entry['prev_hash'] == last_hash

        # Verify entire chain
        assert logger2.verify_chain() is True
