"""SQLite storage for test results and caching."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .engine import ComparisonResult
from .recovery import RecoveryResult


class ResultStorage:
    """SQLite-based storage for test results."""

    def __init__(self, db_path: str = "constraintbreak.db"):
        """Initialize storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Comparison results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comparison_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                task_name TEXT NOT NULL,
                constraint_name TEXT NOT NULL,
                unconstrained_response TEXT,
                constrained_response TEXT,
                winner_ab TEXT,
                winner_ba TEXT,
                win_rate REAL,
                degradation_detected INTEGER,
                severity TEXT,
                provider TEXT,
                model_name TEXT
            )
        """)

        # Recovery results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recovery_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                task_name TEXT NOT NULL,
                constraint_name TEXT NOT NULL,
                single_pass_response TEXT,
                two_pass_response TEXT,
                two_pass_better INTEGER,
                recovery_rate REAL,
                recommendation TEXT,
                provider TEXT,
                model_name TEXT
            )
        """)

        # Run metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                test_type TEXT NOT NULL,
                config TEXT
            )
        """)

        # Cache table for baseline generations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(task_name, provider, model_name, prompt_hash)
            )
        """)

        conn.commit()
        conn.close()

    def save_comparison_results(
        self,
        results: List[ComparisonResult],
        run_id: str,
        provider: str,
        model_name: str,
    ):
        """Save comparison results to database.

        Args:
            results: List of comparison results
            run_id: Unique run identifier
            provider: Provider name
            model_name: Model name
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        for result in results:
            cursor.execute(
                """
                INSERT INTO comparison_results
                (run_id, timestamp, task_name, constraint_name,
                 unconstrained_response, constrained_response,
                 winner_ab, winner_ba, win_rate, degradation_detected,
                 severity, provider, model_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    timestamp,
                    result.task_name,
                    result.constraint_name,
                    result.unconstrained_response,
                    result.constrained_response,
                    result.winner_ab,
                    result.winner_ba,
                    result.win_rate,
                    1 if result.degradation_detected else 0,
                    result.get_severity(),
                    provider,
                    model_name,
                ),
            )

        conn.commit()
        conn.close()

    def save_recovery_results(
        self,
        results: List[RecoveryResult],
        run_id: str,
        provider: str,
        model_name: str,
    ):
        """Save recovery results to database.

        Args:
            results: List of recovery results
            run_id: Unique run identifier
            provider: Provider name
            model_name: Model name
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        for result in results:
            cursor.execute(
                """
                INSERT INTO recovery_results
                (run_id, timestamp, task_name, constraint_name,
                 single_pass_response, two_pass_response,
                 two_pass_better, recovery_rate, recommendation,
                 provider, model_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    timestamp,
                    result.task_name,
                    result.constraint_name,
                    result.single_pass_response,
                    result.two_pass_response,
                    1 if result.two_pass_better else 0,
                    result.recovery_rate,
                    result.get_recommendation(),
                    provider,
                    model_name,
                ),
            )

        conn.commit()
        conn.close()

    def save_run_metadata(
        self,
        run_id: str,
        provider: str,
        model_name: str,
        test_type: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Save run metadata.

        Args:
            run_id: Unique run identifier
            provider: Provider name
            model_name: Model name
            test_type: Type of test (scan/recover)
            config: Optional configuration dict
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()
        config_json = json.dumps(config) if config else None

        cursor.execute(
            """
            INSERT OR REPLACE INTO runs
            (run_id, timestamp, provider, model_name, test_type, config)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, timestamp, provider, model_name, test_type, config_json),
        )

        conn.commit()
        conn.close()

    def get_comparison_results(
        self,
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get comparison results from database.

        Args:
            run_id: Optional run ID to filter by

        Returns:
            List of result dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if run_id:
            cursor.execute(
                "SELECT * FROM comparison_results WHERE run_id = ? ORDER BY timestamp DESC",
                (run_id,),
            )
        else:
            cursor.execute("SELECT * FROM comparison_results ORDER BY timestamp DESC")

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_recovery_results(
        self,
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recovery results from database.

        Args:
            run_id: Optional run ID to filter by

        Returns:
            List of result dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if run_id:
            cursor.execute(
                "SELECT * FROM recovery_results WHERE run_id = ? ORDER BY timestamp DESC",
                (run_id,),
            )
        else:
            cursor.execute("SELECT * FROM recovery_results ORDER BY timestamp DESC")

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all runs.

        Returns:
            List of run metadata dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM runs ORDER BY timestamp DESC")
        runs = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return runs

    def cache_generation(
        self,
        task_name: str,
        provider: str,
        model_name: str,
        prompt_hash: str,
        response: str,
    ):
        """Cache a baseline generation.

        Args:
            task_name: Task name
            provider: Provider name
            model_name: Model name
            prompt_hash: Hash of prompt
            response: Generated response
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO generation_cache
            (task_name, provider, model_name, prompt_hash, response, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_name, provider, model_name, prompt_hash, response, timestamp),
        )

        conn.commit()
        conn.close()

    def get_cached_generation(
        self,
        task_name: str,
        provider: str,
        model_name: str,
        prompt_hash: str,
    ) -> Optional[str]:
        """Get cached baseline generation.

        Args:
            task_name: Task name
            provider: Provider name
            model_name: Model name
            prompt_hash: Hash of prompt

        Returns:
            Cached response or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT response FROM generation_cache
            WHERE task_name = ? AND provider = ? AND model_name = ? AND prompt_hash = ?
            """,
            (task_name, provider, model_name, prompt_hash),
        )

        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None
