"""
PRALAYX database layer.

PRALAYX owns its platform database.

The crawler and OSINT engine may maintain their own native data stores,
but normalized investigation data, evidence, findings, runs, terminal
events, reports, watchlist data, and alerts are persisted here.

ID format:
    INV-XXXXXXXX
    SES-XXXXXXXX
    RUN-XXXXXXXX
    ACT-XXXXXXXX
    FIND-XXXXXXXX
    EVD-XXXXXXXX
    SRC-XXXXXXXX
    JOB-XXXXXXXX
    EVT-XXXXXXXX
    RPT-XXXXXXXX
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


class DB:
    def __init__(self, path: str):
        self.path = str(path)

        Path(self.path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    # ------------------------------------------------------------------
    # Connection / initialization
    # ------------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.path,
            timeout=30,
            check_same_thread=False,
        )

        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")

        return conn

    def _initialize(self) -> None:
        """
        The actual schema is supplied by shared/schema_sqlite.sql.

        This method only prepares the database connection. The platform
        startup code calls migrate() with the configured schema.
        """
        with self.connect() as conn:
            conn.execute("SELECT 1")
            conn.commit()

    def migrate(self, schema_path: str) -> None:
        """
        Apply the PRALAYX SQLite schema.

        The schema is expected to contain CREATE TABLE IF NOT EXISTS /
        CREATE INDEX IF NOT EXISTS statements so startup remains safe.
        """
        schema = Path(schema_path).read_text(
            encoding="utf-8",
        )

        with self.connect() as conn:
            conn.executescript(schema)
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def now() -> str:
        return datetime.now(
            timezone.utc,
        ).isoformat()

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def _json(value: Any) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, str):
            return value

        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    @staticmethod
    def _row(row: Optional[sqlite3.Row]) -> Optional[dict]:
        if row is None:
            return None

        return dict(row)

    @staticmethod
    def _rows(rows: Iterable[sqlite3.Row]) -> list[dict]:
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Investigation
    # ------------------------------------------------------------------

    def create_investigation(
        self,
        target: str,
        target_type: str = "url",
        source: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        investigation_id = self._id("INV")
        actor_id = self._id("ACT")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_actors (
                    actor_id,
                    display_name,
                    category,
                    confidence,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    target,
                    "unknown",
                    0.0,
                    now,
                    now,
                ),
            )

            conn.execute(
                """
                INSERT INTO sih_investigations (
                    investigation_id,
                    target,
                    target_type,
                    status,
                    source,
                    notes,
                    actor_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    investigation_id,
                    target,
                    target_type,
                    "running",
                    source,
                    notes,
                    actor_id,
                    now,
                    now,
                ),
            )

            conn.commit()

        return investigation_id

    def get_investigation(
        self,
        investigation_id: str,
    ) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM sih_investigations
                WHERE investigation_id = ?
                """,
                (investigation_id,),
            ).fetchone()

            if row is None:
                return None

            investigation = dict(row)

            investigation["actor"] = self._row(
                conn.execute(
                    """
                    SELECT *
                    FROM sih_actors
                    WHERE actor_id = ?
                    """,
                    (row["actor_id"],),
                ).fetchone()
            )

            investigation["sessions"] = self._rows(
                conn.execute(
                    """
                    SELECT *
                    FROM sih_sessions
                    WHERE investigation_id = ?
                    ORDER BY created_at ASC
                    """,
                    (investigation_id,),
                ).fetchall()
            )

            investigation["runs"] = self._rows(
                conn.execute(
                    """
                    SELECT *
                    FROM sih_runs
                    WHERE investigation_id = ?
                    ORDER BY created_at ASC
                    """,
                    (investigation_id,),
                ).fetchall()
            )

            investigation["findings"] = self._rows(
                conn.execute(
                    """
                    SELECT *
                    FROM sih_findings
                    WHERE investigation_id = ?
                    ORDER BY first_seen DESC
                    """,
                    (investigation_id,),
                ).fetchall()
            )

            investigation["observations"] = self._rows(
                conn.execute(
                    """
                    SELECT *
                    FROM sih_observations
                    WHERE investigation_id = ?
                    ORDER BY observed_at DESC
                    """,
                    (investigation_id,),
                ).fetchall()
            )

            investigation["relationships"] = self._rows(
                conn.execute(
                    """
                    SELECT *
                    FROM sih_relationships
                    WHERE investigation_id = ?
                    ORDER BY observed_at DESC
                    """,
                    (investigation_id,),
                ).fetchall()
            )

            investigation["reports"] = self._rows(
                conn.execute(
                    """
                    SELECT *
                    FROM sih_reports
                    WHERE investigation_id = ?
                    ORDER BY created_at DESC
                    """,
                    (investigation_id,),
                ).fetchall()
            )

            return investigation

    def list_investigations(
        self,
        limit: int = 100,
    ) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM sih_investigations
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            return self._rows(rows)

    def update_investigation(
        self,
        investigation_id: str,
        status: Optional[str] = None,
        actor_id: Optional[str] = None,
        crawler_session_id: Optional[str] = None,
        crawler_investigation_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> None:
        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status)

        if actor_id is not None:
            updates.append("actor_id = ?")
            values.append(actor_id)

        if crawler_session_id is not None:
            updates.append("crawler_session_id = ?")
            values.append(crawler_session_id)

        if crawler_investigation_id is not None:
            updates.append("crawler_investigation_id = ?")
            values.append(crawler_investigation_id)

        if notes is not None:
            updates.append("notes = ?")
            values.append(notes)

        updates.append("updated_at = ?")
        values.append(self.now())

        values.append(investigation_id)

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE sih_investigations
                SET {", ".join(updates)}
                WHERE investigation_id = ?
                """,
                values,
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Actors
    # ------------------------------------------------------------------

    def create_actor(
        self,
        display_name: str,
        category: str = "unknown",
        confidence: float = 0.0,
    ) -> str:
        actor_id = self._id("ACT")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_actors (
                    actor_id,
                    display_name,
                    category,
                    confidence,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    display_name,
                    category,
                    float(confidence),
                    now,
                    now,
                ),
            )
            conn.commit()

        return actor_id

    def update_actor(
        self,
        actor_id: str,
        display_name: Optional[str] = None,
        category: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> None:
        updates = []
        values = []

        if display_name is not None:
            updates.append("display_name = ?")
            values.append(display_name)

        if category is not None:
            updates.append("category = ?")
            values.append(category)

        if confidence is not None:
            updates.append("confidence = ?")
            values.append(float(confidence))

        if not updates:
            return

        updates.append("updated_at = ?")
        values.append(self.now())
        values.append(actor_id)

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE sih_actors
                SET {", ".join(updates)}
                WHERE actor_id = ?
                """,
                values,
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def create_session(
        self,
        investigation_id: str,
        session_type: str,
        actor_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        session_id = self._id("SES")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_sessions (
                    session_id,
                    investigation_id,
                    session_type,
                    actor_id,
                    status,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    investigation_id,
                    session_type,
                    actor_id,
                    "running",
                    self._json(metadata),
                    now,
                    now,
                ),
            )
            conn.commit()

        return session_id

    def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status)

        if metadata is not None:
            updates.append("metadata = ?")
            values.append(self._json(metadata))

        updates.append("updated_at = ?")
        values.append(self.now())
        values.append(session_id)

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE sih_sessions
                SET {", ".join(updates)}
                WHERE session_id = ?
                """,
                values,
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(
        self,
        investigation_id: str,
        run_type: str,
        session_id: Optional[str] = None,
        module_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> str:
        run_id = self._id("RUN")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_runs (
                    run_id,
                    investigation_id,
                    session_id,
                    actor_id,
                    run_type,
                    module_id,
                    status,
                    progress,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    investigation_id,
                    session_id,
                    actor_id,
                    run_type,
                    module_id,
                    "RUNNING",
                    0.0,
                    self._json(payload),
                    now,
                    now,
                ),
            )
            conn.commit()

        return run_id

    def update_run(
        self,
        run_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result_ref: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status)

        if progress is not None:
            updates.append("progress = ?")
            values.append(float(progress))

        if result_ref is not None:
            updates.append("result_ref = ?")
            values.append(result_ref)

        if error is not None:
            updates.append("error = ?")
            values.append(error)

        updates.append("updated_at = ?")
        values.append(self.now())
        values.append(run_id)

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE sih_runs
                SET {", ".join(updates)}
                WHERE run_id = ?
                """,
                values,
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def create_job(
        self,
        investigation_id: str,
        job_type: str,
        payload: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> str:
        job_id = self._id("JOB")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_jobs (
                    job_id,
                    investigation_id,
                    run_id,
                    job_type,
                    status,
                    progress,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    investigation_id,
                    run_id,
                    job_type,
                    "running",
                    0.0,
                    self._json(payload),
                    now,
                    now,
                ),
            )
            conn.commit()

        return job_id

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result_ref: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status)

        if progress is not None:
            updates.append("progress = ?")
            values.append(float(progress))

        if result_ref is not None:
            updates.append("result_ref = ?")
            values.append(result_ref)

        if error is not None:
            updates.append("error = ?")
            values.append(error)

        updates.append("updated_at = ?")
        values.append(self.now())
        values.append(job_id)

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE sih_jobs
                SET {", ".join(updates)}
                WHERE job_id = ?
                """,
                values,
            )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM sih_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

            return self._row(row)

    # ------------------------------------------------------------------
    # Terminal / job events
    # ------------------------------------------------------------------

    def event(
        self,
        job_id: str,
        event_type: str,
        message: str,
        progress: Optional[float] = None,
        payload: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> str:
        event_id = self._id("EVT")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_job_events (
                    event_id,
                    job_id,
                    run_id,
                    event_type,
                    message,
                    progress,
                    payload,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    job_id,
                    run_id,
                    event_type,
                    message,
                    progress,
                    self._json(payload),
                    now,
                ),
            )
            conn.commit()

        return event_id

    def get_job_events(
        self,
        job_id: str,
        after: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict]:
        with self.connect() as conn:
            if after:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sih_job_events
                    WHERE job_id = ?
                      AND created_at > ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (
                        job_id,
                        after,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sih_job_events
                    WHERE job_id = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (
                        job_id,
                        limit,
                    ),
                ).fetchall()

            return self._rows(rows)

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    def add_identifier(
        self,
        investigation_id: str,
        identifier_type: str,
        value: str,
        actor_id: Optional[str] = None,
        normalized_value: Optional[str] = None,
        source: Optional[str] = None,
        source_url: Optional[str] = None,
        confidence: float = 0.5,
    ) -> str:
        identifier_id = self._id("ID")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_identifiers (
                    identifier_id,
                    investigation_id,
                    actor_id,
                    identifier_type,
                    value,
                    normalized_value,
                    source,
                    source_url,
                    confidence,
                    first_seen,
                    last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier_id,
                    investigation_id,
                    actor_id,
                    identifier_type,
                    value,
                    normalized_value,
                    source,
                    source_url,
                    float(confidence),
                    now,
                    now,
                ),
            )
            conn.commit()

        return identifier_id

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def get_or_create_source(
        self,
        name: str,
        url: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> str:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT source_id
                FROM sih_sources
                WHERE name = ?
                  AND COALESCE(url, '') = COALESCE(?, '')
                LIMIT 1
                """,
                (
                    name,
                    url,
                ),
            ).fetchone()

            if row:
                return row["source_id"]

            source_id = self._id("SRC")

            conn.execute(
                """
                INSERT INTO sih_sources (
                    source_id,
                    name,
                    url,
                    source_type,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    name,
                    url,
                    source_type,
                    self.now(),
                ),
            )

            conn.commit()

            return source_id

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def add_finding(
        self,
        investigation_id: str,
        finding_type: str,
        value: str,
        source: Optional[str] = None,
        source_url: Optional[str] = None,
        confidence: float = 0.5,
        metadata: Optional[dict] = None,
        actor_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> str:
        finding_id = self._id("FIND")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_findings (
                    finding_id,
                    investigation_id,
                    actor_id,
                    run_id,
                    finding_type,
                    value,
                    source,
                    source_url,
                    confidence,
                    metadata,
                    first_seen,
                    last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    investigation_id,
                    actor_id,
                    run_id,
                    finding_type,
                    value,
                    source,
                    source_url,
                    float(confidence),
                    self._json(metadata),
                    now,
                    now,
                ),
            )
            conn.commit()

        return finding_id

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        finding_id: str,
        evidence_type: str,
        source_url: Optional[str] = None,
        excerpt: Optional[str] = None,
        metadata: Optional[dict] = None,
        source_id: Optional[str] = None,
    ) -> str:
        evidence_id = self._id("EVD")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_evidence (
                    evidence_id,
                    finding_id,
                    source_id,
                    evidence_type,
                    source_url,
                    excerpt,
                    metadata,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    finding_id,
                    source_id,
                    evidence_type,
                    source_url,
                    excerpt,
                    self._json(metadata),
                    self.now(),
                ),
            )
            conn.commit()

        return evidence_id

    # ------------------------------------------------------------------
    # Observations
    # ------------------------------------------------------------------

    def add_observation(
        self,
        investigation_id: str,
        entity_type: str,
        entity_value: str,
        actor_id: Optional[str] = None,
        source_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> str:
        observation_id = self._id("OBS")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_observations (
                    observation_id,
                    investigation_id,
                    actor_id,
                    run_id,
                    entity_type,
                    entity_value,
                    source_id,
                    evidence_id,
                    observed_at,
                    first_seen,
                    last_seen,
                    confidence,
                    metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    investigation_id,
                    actor_id,
                    run_id,
                    entity_type,
                    entity_value,
                    source_id,
                    evidence_id,
                    now,
                    now,
                    now,
                    confidence,
                    self._json(metadata),
                ),
            )
            conn.commit()

        return observation_id

    # ------------------------------------------------------------------
    # Entity sightings
    # ------------------------------------------------------------------

    def add_entity_sighting(
        self,
        investigation_id: str,
        entity_type: str,
        normalized_value: str,
        raw_value: Optional[str] = None,
        source_id: Optional[str] = None,
        source_url: Optional[str] = None,
        actor_id: Optional[str] = None,
        run_id: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        sighting_id = self._id("SIGHT")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_entity_sightings (
                    sighting_id,
                    investigation_id,
                    actor_id,
                    run_id,
                    entity_type,
                    normalized_value,
                    raw_value,
                    source_id,
                    source_url,
                    confidence,
                    metadata,
                    first_seen,
                    last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sighting_id,
                    investigation_id,
                    actor_id,
                    run_id,
                    entity_type,
                    normalized_value,
                    raw_value,
                    source_id,
                    source_url,
                    confidence,
                    self._json(metadata),
                    now,
                    now,
                ),
            )
            conn.commit()

        return sighting_id

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def add_relationship(
        self,
        investigation_id: str,
        from_type: str,
        from_value: str,
        relationship_type: str,
        to_type: str,
        to_value: str,
        source_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        confidence: Optional[float] = None,
        observed_at: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> str:
        relationship_id = self._id("REL")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_relationships (
                    relationship_id,
                    investigation_id,
                    run_id,
                    from_type,
                    from_value,
                    relationship_type,
                    to_type,
                    to_value,
                    source_id,
                    evidence_id,
                    confidence,
                    observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship_id,
                    investigation_id,
                    run_id,
                    from_type,
                    from_value,
                    relationship_type,
                    to_type,
                    to_value,
                    source_id,
                    evidence_id,
                    confidence,
                    observed_at or self.now(),
                ),
            )
            conn.commit()

        return relationship_id

    # ------------------------------------------------------------------
    # Raw snapshots
    # ------------------------------------------------------------------

    def add_raw_snapshot(
        self,
        investigation_id: str,
        source: str,
        payload: Any,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        snapshot_type: str = "raw",
    ) -> str:
        snapshot_id = self._id("RAW")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_raw_snapshots (
                    snapshot_id,
                    investigation_id,
                    session_id,
                    run_id,
                    source,
                    snapshot_type,
                    payload,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    investigation_id,
                    session_id,
                    run_id,
                    source,
                    snapshot_type,
                    self._json(payload),
                    self.now(),
                ),
            )
            conn.commit()

        return snapshot_id

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def add_timeline_event(
        self,
        investigation_id: str,
        event_type: str,
        message: str,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> str:
        timeline_id = self._id("TIME")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_investigation_timeline (
                    timeline_id,
                    investigation_id,
                    session_id,
                    run_id,
                    actor_id,
                    event_type,
                    message,
                    payload,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timeline_id,
                    investigation_id,
                    session_id,
                    run_id,
                    actor_id,
                    event_type,
                    message,
                    self._json(payload),
                    self.now(),
                ),
            )
            conn.commit()

        return timeline_id

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def register_report(
        self,
        investigation_id: str,
        stage: str,
        report_type: str,
        report_format: str,
        file_name: str,
        file_path: str,
        file_size: int = 0,
        mime_type: Optional[str] = None,
        run_id: Optional[str] = None,
        module_id: Optional[str] = None,
        status: str = "completed",
    ) -> str:
        report_id = self._id("RPT")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_reports (
                    report_id,
                    investigation_id,
                    run_id,
                    module_id,
                    stage,
                    report_type,
                    format,
                    file_name,
                    file_path,
                    file_size,
                    mime_type,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    investigation_id,
                    run_id,
                    module_id,
                    stage,
                    report_type,
                    report_format,
                    file_name,
                    file_path,
                    int(file_size),
                    mime_type,
                    status,
                    self.now(),
                ),
            )
            conn.commit()

        return report_id

    def list_reports(
        self,
        investigation_id: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict]:
        with self.connect() as conn:
            if investigation_id:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sih_reports
                    WHERE investigation_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (
                        investigation_id,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sih_reports
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return self._rows(rows)

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------

    def add_watchlist(
        self,
        actor_id: str,
        interval_minutes: int = 60,
    ) -> str:
        watch_id = self._id("WATCH")
        now = self.now()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_watchlist (
                    watch_id,
                    actor_id,
                    interval_minutes,
                    enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (
                    watch_id,
                    actor_id,
                    int(interval_minutes),
                    now,
                    now,
                ),
            )
            conn.commit()

        return watch_id

    def remove_watchlist(
        self,
        watch_id: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                DELETE FROM sih_watchlist
                WHERE watch_id = ?
                """,
                (watch_id,),
            )
            conn.commit()

    def list_watchlist(self) -> list[dict]:
        with self.connect() as conn:
            return self._rows(
                conn.execute(
                    """
                    SELECT
                        w.*,
                        a.display_name,
                        a.category,
                        a.confidence
                    FROM sih_watchlist w
                    LEFT JOIN sih_actors a
                        ON a.actor_id = w.actor_id
                    ORDER BY w.created_at DESC
                    """
                ).fetchall()
            )

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def add_alert(
        self,
        actor_id: Optional[str],
        finding_id: Optional[str],
        alert_type: str,
        message: str,
        confidence: Optional[float] = None,
    ) -> str:
        alert_id = self._id("ALERT")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sih_alerts (
                    alert_id,
                    actor_id,
                    finding_id,
                    alert_type,
                    message,
                    confidence,
                    is_read,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    alert_id,
                    actor_id,
                    finding_id,
                    alert_type,
                    message,
                    confidence,
                    self.now(),
                ),
            )
            conn.commit()

        return alert_id

    def list_alerts(
        self,
        unread_only: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        with self.connect() as conn:
            if unread_only:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sih_alerts
                    WHERE is_read = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sih_alerts
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return self._rows(rows)

    def mark_alert_read(
        self,
        alert_id: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE sih_alerts
                SET is_read = 1
                WHERE alert_id = ?
                """,
                (alert_id,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 100,
    ) -> list[dict]:
        pattern = f"%{query}%"

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    finding_id,
                    investigation_id,
                    actor_id,
                    finding_type,
                    value,
                    source,
                    source_url,
                    confidence,
                    first_seen,
                    last_seen
                FROM sih_findings
                WHERE value LIKE ?
                   OR finding_type LIKE ?
                   OR source LIKE ?
                   OR source_url LIKE ?
                ORDER BY confidence DESC, last_seen DESC
                LIMIT ?
                """,
                (
                    pattern,
                    pattern,
                    pattern,
                    pattern,
                    limit,
                ),
            ).fetchall()

            return self._rows(rows)

    # ------------------------------------------------------------------
    # Generic compatibility helpers
    # ------------------------------------------------------------------

    def execute(
        self,
        query: str,
        params: tuple = (),
    ) -> list[dict]:
        """
        Read-only/general SQL helper.

        Higher-level application code should prefer the explicit methods
        above. This helper exists for compatibility with existing platform
        modules.
        """
        with self.connect() as conn:
            cursor = conn.execute(
                query,
                params,
            )

            if cursor.description is None:
                conn.commit()
                return []

            return self._rows(
                cursor.fetchall()
            )

    def close(self) -> None:
        """
        Connections are opened per operation, so there is no persistent
        connection to close.
        """
        return None
