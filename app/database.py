from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DB:
    """
    SIH26151 platform database adapter.

    The platform shares the same physical SQLite database as the crawler,
    but all platform-owned tables use the `sih_` prefix so that existing
    crawler tables remain untouched.
    """

    def __init__(self, path: str | None = None):
        self.path = path or os.getenv(
            "OSINT_DB_PATH",
            "data/sih.db",
        )

        Path(self.path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=30,
        )

        self.conn.row_factory = sqlite3.Row

        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def migrate(self, schema: str):
        schema_path = Path(schema)

        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}"
            )

        self.conn.executescript(
            schema_path.read_text(encoding="utf-8")
        )

        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def _id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    # ============================================================
    # INVESTIGATIONS
    # ============================================================

    def create_investigation(
        self,
        target: str,
        target_type: str = "other",
        source: str = "manual",
        notes: str | None = None,
    ):
        iid = str(uuid.uuid4())
        actor_id = self._id("ACT")
        timestamp = now()

        self.conn.execute(
            """
            INSERT INTO sih_actors
            (
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
                timestamp,
                timestamp,
            ),
        )

        self.conn.execute(
            """
            INSERT INTO sih_investigations
            (
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
                iid,
                target,
                target_type,
                "running",
                source,
                notes,
                actor_id,
                timestamp,
                timestamp,
            ),
        )

        self.conn.commit()

        return iid, actor_id

    def update_investigation(
        self,
        iid: str,
        **kwargs,
    ):
        allowed = {
            "target",
            "target_type",
            "status",
            "source",
            "notes",
            "actor_id",
            "crawler_session_id",
            "crawler_investigation_id",
        }

        parts = []
        values = []

        for key, value in kwargs.items():
            if key not in allowed:
                continue

            parts.append(f"{key} = ?")
            values.append(value)

        if not parts:
            return

        parts.append("updated_at = ?")
        values.append(now())
        values.append(iid)

        self.conn.execute(
            f"""
            UPDATE sih_investigations
            SET {", ".join(parts)}
            WHERE investigation_id = ?
            """,
            values,
        )

        self.conn.commit()

    # ============================================================
    # JOBS
    # ============================================================

    def create_job(
        self,
        job_type: str,
        investigation_id: str | None = None,
        payload: dict | None = None,
    ):
        jid = self._id("JOB")

        self.conn.execute(
            """
            INSERT INTO sih_jobs
            (
                job_id,
                investigation_id,
                job_type,
                status,
                progress,
                payload,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'queued', 0, ?, ?, ?)
            """,
            (
                jid,
                investigation_id,
                job_type,
                json.dumps(payload or {}),
                now(),
                now(),
            ),
        )

        self.conn.commit()

        return jid

    def update_job(self, jid: str, **kwargs):
        allowed = {
            "investigation_id",
            "job_type",
            "status",
            "progress",
            "payload",
            "result_ref",
            "error",
        }

        parts = []
        values = []

        for key, value in kwargs.items():
            if key not in allowed:
                continue

            parts.append(f"{key} = ?")
            values.append(
                json.dumps(value)
                if key == "payload"
                and isinstance(value, (dict, list))
                else value
            )

        if not parts:
            return

        parts.append("updated_at = ?")
        values.append(now())
        values.append(jid)

        self.conn.execute(
            f"""
            UPDATE sih_jobs
            SET {", ".join(parts)}
            WHERE job_id = ?
            """,
            values,
        )

        self.conn.commit()

    def event(
        self,
        jid: str,
        etype: str,
        message: str,
        progress: float | None = None,
        payload: dict | None = None,
    ):
        eid = self._id("EVT")

        self.conn.execute(
            """
            INSERT INTO sih_job_events
            (
                event_id,
                job_id,
                event_type,
                message,
                progress,
                payload,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eid,
                jid,
                etype,
                message,
                progress,
                json.dumps(payload or {}),
                now(),
            ),
        )

        self.conn.commit()

    def job(self, jid: str):
        row = self.conn.execute(
            """
            SELECT *
            FROM sih_jobs
            WHERE job_id = ?
            """,
            (jid,),
        ).fetchone()

        return dict(row) if row else None

    def events(self, jid: str):
        rows = self.conn.execute(
            """
            SELECT *
            FROM sih_job_events
            WHERE job_id = ?
            ORDER BY rowid
            """,
            (jid,),
        ).fetchall()

        return [dict(row) for row in rows]

    # ============================================================
    # FINDINGS
    # ============================================================

    def finding(
        self,
        iid: str,
        ftype: str,
        value: str,
        source: str,
        source_url: str | None = None,
        confidence: float = 0.5,
        metadata: dict | None = None,
        actor_id: str | None = None,
    ):
        fid = self._id("FND")
        timestamp = now()

        confidence = max(
            0.0,
            min(1.0, float(confidence)),
        )

        self.conn.execute(
            """
            INSERT INTO sih_findings
            (
                finding_id,
                investigation_id,
                actor_id,
                finding_type,
                value,
                source,
                source_url,
                confidence,
                metadata,
                first_seen,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fid,
                iid,
                actor_id,
                ftype,
                value,
                source,
                source_url,
                confidence,
                json.dumps(metadata or {}),
                timestamp,
                timestamp,
            ),
        )

        self.conn.commit()

        return fid

    # ============================================================
    # SOURCES / EVIDENCE
    # ============================================================

    def source(
        self,
        name: str,
        url: str | None = None,
    ):
        row = self.conn.execute(
            """
            SELECT source_id
            FROM sih_sources
            WHERE name = ?
              AND COALESCE(url, '') = COALESCE(?, '')
            """,
            (name or "unknown", url),
        ).fetchone()

        if row:
            return row["source_id"]

        sid = self._id("SRC")

        self.conn.execute(
            """
            INSERT INTO sih_sources
            (
                source_id,
                name,
                url,
                source_type,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                sid,
                name or "unknown",
                url,
                "external",
                now(),
            ),
        )

        self.conn.commit()

        return sid

    def evidence(
        self,
        fid: str,
        sid: str,
        etype: str,
        url: str | None = None,
        excerpt: str | None = None,
        metadata: dict | None = None,
    ):
        eid = self._id("EVD")

        self.conn.execute(
            """
            INSERT INTO sih_evidence
            (
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
                eid,
                fid,
                sid,
                etype,
                url,
                excerpt,
                json.dumps(metadata or {}),
                now(),
            ),
        )

        self.conn.commit()

        return eid

    # ============================================================
    # INVESTIGATION READ
    # ============================================================

    def investigation(self, iid: str):
        row = self.conn.execute(
            """
            SELECT *
            FROM sih_investigations
            WHERE investigation_id = ?
            """,
            (iid,),
        ).fetchone()

        if not row:
            return None

        out = dict(row)

        out["findings"] = [
            dict(x)
            for x in self.conn.execute(
                """
                SELECT *
                FROM sih_findings
                WHERE investigation_id = ?
                ORDER BY first_seen DESC
                """,
                (iid,),
            ).fetchall()
        ]

        out["observations"] = [
            dict(x)
            for x in self.conn.execute(
                """
                SELECT *
                FROM sih_observations
                WHERE investigation_id = ?
                ORDER BY observed_at DESC
                """,
                (iid,),
            ).fetchall()
        ]

        out["relationships"] = [
            dict(x)
            for x in self.conn.execute(
                """
                SELECT *
                FROM sih_relationships
                WHERE investigation_id = ?
                ORDER BY observed_at DESC
                """,
                (iid,),
            ).fetchall()
        ]

        return out

    def investigations(self, limit: int = 100):
        rows = self.conn.execute(
            """
            SELECT *
            FROM sih_investigations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]

    # ============================================================
    # ACTORS
    # ============================================================

    def actors(self):
        rows = self.conn.execute(
            """
            SELECT *
            FROM sih_actors
            ORDER BY updated_at DESC
            """
        ).fetchall()

        return [dict(row) for row in rows]

    # ============================================================
    # WATCHLIST
    # ============================================================

    def watch(
        self,
        actor_id: str,
        interval_minutes: int = 60,
    ):
        wid = self._id("WCH")
        timestamp = now()

        self.conn.execute(
            """
            INSERT INTO sih_watchlist
            (
                watch_id,
                actor_id,
                interval_minutes,
                enabled,
                last_scan_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 1, NULL, ?, ?)
            """,
            (
                wid,
                actor_id,
                interval_minutes,
                timestamp,
                timestamp,
            ),
        )

        self.conn.commit()

        return wid

    def watchlist(self):
        rows = self.conn.execute(
            """
            SELECT *
            FROM sih_watchlist
            ORDER BY created_at DESC
            """
        ).fetchall()

        return [dict(row) for row in rows]

    # ============================================================
    # ALERTS
    # ============================================================

    def alert(
        self,
        actor_id: str,
        fid: str | None,
        atype: str,
        message: str,
        confidence: float = 0.5,
    ):
        aid = self._id("ALT")

        self.conn.execute(
            """
            INSERT INTO sih_alerts
            (
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
                aid,
                actor_id,
                fid,
                atype,
                message,
                confidence,
                now(),
            ),
        )

        self.conn.commit()

        return aid

    def alerts(self, unread: bool = False):
        sql = """
            SELECT *
            FROM sih_alerts
        """

        params = []

        if unread:
            sql += " WHERE is_read = 0"

        sql += """
            ORDER BY created_at DESC
            LIMIT 200
        """

        rows = self.conn.execute(
            sql,
            params,
        ).fetchall()

        return [dict(row) for row in rows]

    def mark_alert(self, aid: str):
        self.conn.execute(
            """
            UPDATE sih_alerts
            SET is_read = 1
            WHERE alert_id = ?
            """,
            (aid,),
        )

        self.conn.commit()

    # ============================================================
    # FINDING SEARCH
    # ============================================================

    def filtered_findings(
        self,
        actor: str | None = None,
        ftype: str | None = None,
        confidence: float | None = None,
        q: str | None = None,
    ):
        sql = """
            SELECT *
            FROM sih_findings
            WHERE 1 = 1
        """

        params = []

        if actor:
            sql += " AND actor_id = ?"
            params.append(actor)

        if ftype:
            sql += " AND finding_type = ?"
            params.append(ftype)

        if confidence is not None:
            sql += " AND confidence >= ?"
            params.append(confidence)

        if q:
            sql += " AND lower(value) LIKE ?"
            params.append(f"%{q.lower()}%")

        sql += """
            ORDER BY last_seen DESC
        """

        rows = self.conn.execute(
            sql,
            params,
        ).fetchall()

        return [dict(row) for row in rows]
