"""Database operations for karpathy-wiki."""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import contextmanager


class Database:
    """SQLite database for knowledge base metadata."""

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def init_schema(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()

        # Sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                source_type TEXT NOT NULL,
                original_url TEXT,
                ingested_at TEXT NOT NULL,
                compiled_at TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
            )
        """)

        # Articles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                word_count INTEGER DEFAULT 0
            )
        """)

        # Source-article mapping
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_article_map (
                source_id INTEGER NOT NULL,
                article_id INTEGER NOT NULL,
                FOREIGN KEY (source_id) REFERENCES sources(id),
                FOREIGN KEY (article_id) REFERENCES articles(id),
                PRIMARY KEY (source_id, article_id)
            )
        """)

        # Health reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                report_path TEXT NOT NULL,
                issues_found INTEGER DEFAULT 0
            )
        """)

        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()

    # Source operations
    def add_source(
        self,
        path: str,
        source_type: str,
        original_url: Optional[str] = None,
        status: str = "pending",
    ) -> int:
        """Add a new source to the database.

        Args:
            path: Relative path to the source file
            source_type: Type of source (pdf, markdown, url, github, text)
            original_url: Original URL if applicable
            status: Source status (pending, compiled, failed)

        Returns:
            ID of the inserted source
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO sources (path, source_type, original_url, ingested_at, status)
            VALUES (?, ?, ?, ?, ?)
        """,
            (path, source_type, original_url, datetime.utcnow().isoformat(), status),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_source(self, source_id: int) -> Optional[Dict[str, Any]]:
        """Get source by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_pending_sources(self) -> List[Dict[str, Any]]:
        """Get all sources pending compilation."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM sources WHERE status = 'pending' ORDER BY ingested_at"
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_source_status(
        self, source_id: int, status: str, compiled_at: Optional[str] = None
    ):
        """Update source compilation status.

        Args:
            source_id: Source ID
            status: New status (compiled, failed)
            compiled_at: Compilation timestamp
        """
        cursor = self.conn.cursor()
        if compiled_at:
            cursor.execute(
                "UPDATE sources SET status = ?, compiled_at = ? WHERE id = ?",
                (status, compiled_at, source_id),
            )
        else:
            cursor.execute(
                "UPDATE sources SET status = ? WHERE id = ?", (status, source_id)
            )
        self.conn.commit()

    # Article operations
    def add_article(
        self,
        path: str,
        title: str,
        summary: Optional[str] = None,
        tags: Optional[List[str]] = None,
        word_count: int = 0,
    ) -> int:
        """Add a new article to the database.

        Args:
            path: Relative path to the article
            title: Article title
            summary: Brief summary
            tags: List of tags
            word_count: Number of words in article

        Returns:
            ID of the inserted article
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        tags_str = ",".join(tags) if tags else None

        cursor.execute(
            """
            INSERT INTO articles (path, title, summary, tags, created_at, updated_at, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (path, title, summary, tags_str, now, now, word_count),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_article(
        self,
        article_id: int,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        tags: Optional[List[str]] = None,
        word_count: Optional[int] = None,
    ):
        """Update an existing article."""
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)
        if tags is not None:
            updates.append("tags = ?")
            params.append(",".join(tags))
        if word_count is not None:
            updates.append("word_count = ?")
            params.append(word_count)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(article_id)

            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params
            )
            self.conn.commit()

    def get_article_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get article by path."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE path = ?", (path,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_articles(self) -> List[Dict[str, Any]]:
        """Get all articles."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def link_source_to_article(self, source_id: int, article_id: int):
        """Create a link between source and article."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO source_article_map (source_id, article_id) VALUES (?, ?)",
            (source_id, article_id),
        )
        self.conn.commit()

    def get_articles_for_source(self, source_id: int) -> List[Dict[str, Any]]:
        """Get all articles created from a source."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT a.* FROM articles a
            JOIN source_article_map m ON a.id = m.article_id
            WHERE m.source_id = ?
        """,
            (source_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # Health report operations
    def add_health_report(self, report_path: str, issues_found: int) -> int:
        """Add a health report record.

        Args:
            report_path: Path to the health report file
            issues_found: Number of issues found

        Returns:
            ID of the inserted report
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO health_reports (created_at, report_path, issues_found)
            VALUES (?, ?, ?)
        """,
            (datetime.utcnow().isoformat(), report_path, issues_found),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_latest_health_report(self) -> Optional[Dict[str, Any]]:
        """Get the most recent health report."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM health_reports ORDER BY created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # Statistics
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM articles")
        article_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM sources WHERE status = 'pending'")
        pending_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM sources")
        total_sources = cursor.fetchone()["count"]

        cursor.execute("SELECT MAX(compiled_at) as last_compile FROM sources")
        last_compile = cursor.fetchone()["last_compile"]

        cursor.execute("SELECT SUM(word_count) as total_words FROM articles")
        total_words = cursor.fetchone()["total_words"] or 0

        return {
            "articles": article_count,
            "sources_total": total_sources,
            "sources_pending": pending_count,
            "last_compile": last_compile,
            "total_words": total_words,
        }
