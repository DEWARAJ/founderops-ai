from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from founderops.models import AuditEvent, CandidateRecord


class Repository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    document TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_candidate(self, candidate: CandidateRecord) -> None:
        document = candidate.model_dump_json()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO candidates (id, document, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    document=excluded.document,
                    updated_at=excluded.updated_at""",
                (candidate.id, document, candidate.updated_at.isoformat()),
            )

    def get_candidate(self, candidate_id: str) -> CandidateRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT document FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        return CandidateRecord.model_validate_json(row["document"]) if row else None

    def list_candidates(self) -> list[CandidateRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT document FROM candidates ORDER BY updated_at DESC"
            ).fetchall()
        return [CandidateRecord.model_validate_json(row["document"]) for row in rows]

    def add_audit(
        self, candidate_id: str, action: str, actor: str, payload: dict[str, Any]
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO audit_events
                (candidate_id, action, actor, payload, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    candidate_id,
                    action,
                    actor,
                    json.dumps(payload),
                    datetime.now().astimezone().isoformat(),
                ),
            )

    def list_audit(self, candidate_id: str) -> list[AuditEvent]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE candidate_id = ? ORDER BY id", (candidate_id,)
            ).fetchall()
        return [
            AuditEvent(
                id=row["id"],
                candidate_id=row["candidate_id"],
                action=row["action"],
                actor=row["actor"],
                payload=json.loads(row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def lookup_idempotency_key(self, key: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT candidate_id FROM idempotency_keys WHERE key = ?", (key,)
            ).fetchone()
        return row["candidate_id"] if row else None

    def save_idempotency_key(self, key: str, candidate_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO idempotency_keys (key, candidate_id, created_at) VALUES (?, ?, ?)",
                (key, candidate_id, datetime.now().astimezone().isoformat()),
            )
