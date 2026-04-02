"""Tests for audit logging and verification."""

import pytest
import tempfile
import os
import time
from aegis.audit import AuditLogger, AuditVerifier


class TestAuditLogger:
    """Test audit logger functionality."""

    @pytest.fixture
    def temp_log_file(self):
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            path = f.name
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_create_logger(self, temp_log_file):
        logger = AuditLogger(temp_log_file)
        assert logger is not None
        assert logger.verify_key is not None

    def test_log_decision(self, temp_log_file):
        logger = AuditLogger(temp_log_file)

        decision = {
            'action': 'deny',
            'reason': 'Test',
            'tool_name': 'test_tool'
        }

        entry = logger.log_decision(decision)

        assert 'entry_hash' in entry
        assert 'signature' in entry
        assert 'timestamp' in entry
        assert entry['decision'] == decision

    def test_log_multiple_entries(self, temp_log_file):
        logger = AuditLogger(temp_log_file)

        for i in range(5):
            decision = {'action': 'allow', 'tool_name': f'tool_{i}'}
            logger.log_decision(decision)

        # Verify file has 5 lines
        with open(temp_log_file, 'r') as f:
            lines = f.readlines()
        assert len(lines) == 5

    def test_hash_chain(self, temp_log_file):
        logger = AuditLogger(temp_log_file)

        entry1 = logger.log_decision({'action': 'allow'})
        entry2 = logger.log_decision({'action': 'deny'})

        # Second entry should link to first
        assert entry2['previous_hash'] == entry1['entry_hash']


class TestAuditVerifier:
    """Test audit log verification."""

    @pytest.fixture
    def valid_log_file(self):
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            path = f.name

        logger = AuditLogger(path)

        for i in range(3):
            logger.log_decision({'action': 'allow', 'tool': f'tool_{i}'})

        verify_key = logger.export_verify_key()

        yield path, verify_key

        os.unlink(path)

    def test_verify_valid_log(self, valid_log_file):
        log_path, verify_key = valid_log_file

        verifier = AuditVerifier(log_path)
        result = verifier.verify(verify_key)

        assert result['valid'] is True
        assert result['total_entries'] == 3
        assert result['verified_entries'] == 3
        assert len(result['errors']) == 0

    def test_detect_tampering(self, valid_log_file):
        log_path, verify_key = valid_log_file

        # Tamper with the log
        with open(log_path, 'r') as f:
            lines = f.readlines()

        # Modify the second entry
        import json
        entry = json.loads(lines[1])
        entry['decision']['action'] = 'TAMPERED'

        lines[1] = json.dumps(entry) + '\n'

        with open(log_path, 'w') as f:
            f.writelines(lines)

        # Verify should detect tampering
        verifier = AuditVerifier(log_path)
        result = verifier.verify(verify_key)

        assert result['valid'] is False
        assert len(result['errors']) > 0

    def test_get_statistics(self, valid_log_file):
        log_path, _ = valid_log_file

        verifier = AuditVerifier(log_path)
        stats = verifier.get_statistics()

        assert stats['total_entries'] == 3
        assert 'event_types' in stats
        assert stats['event_types']['decision'] == 3
