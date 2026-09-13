PRAGMA foreign_keys=ON;

-- ============================================================
-- SIH26151 PLATFORM TABLES
-- Prefix: sih_
--
-- IMPORTANT:
-- The crawler already has tables such as:
-- investigations, sessions, pages, posts, etc.
-- Therefore these platform tables intentionally use sih_
-- prefixes to avoid collisions.
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_actors (
    actor_id TEXT PRIMARY KEY,
    display_name TEXT,
    category TEXT DEFAULT 'unknown',
    confidence REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_investigations (
    investigation_id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    target_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    source TEXT,
    notes TEXT,
    actor_id TEXT,
    crawler_session_id TEXT,
    crawler_investigation_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_identifiers (
    identifier_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    actor_id TEXT,
    identifier_type TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT,
    source TEXT,
    source_url TEXT,
    confidence REAL DEFAULT 0.5,
    first_seen TEXT,
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS sih_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT,
    source_type TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_evidence (
    evidence_id TEXT PRIMARY KEY,
    finding_id TEXT,
    source_id TEXT,
    evidence_type TEXT,
    source_url TEXT,
    excerpt TEXT,
    metadata TEXT,
    collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_findings (
    finding_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    actor_id TEXT,
    finding_type TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT,
    source_url TEXT,
    confidence REAL DEFAULT 0.5,
    metadata TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_observations (
    observation_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    actor_id TEXT,
    entity_type TEXT,
    entity_value TEXT,
    source_id TEXT,
    evidence_id TEXT,
    observed_at TEXT NOT NULL,
    first_seen TEXT,
    last_seen TEXT,
    confidence REAL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS sih_relationships (
    relationship_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    from_type TEXT,
    from_value TEXT,
    relationship_type TEXT,
    to_type TEXT,
    to_value TEXT,
    source_id TEXT,
    evidence_id TEXT,
    confidence REAL,
    observed_at TEXT
);

CREATE TABLE IF NOT EXISTS sih_jobs (
    job_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    job_type TEXT,
    status TEXT,
    progress REAL DEFAULT 0,
    payload TEXT,
    result_ref TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_job_events (
    event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    event_type TEXT,
    message TEXT,
    progress REAL,
    payload TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_watchlist (
    watch_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    interval_minutes INTEGER DEFAULT 60,
    enabled INTEGER DEFAULT 1,
    last_scan_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sih_alerts (
    alert_id TEXT PRIMARY KEY,
    actor_id TEXT,
    finding_id TEXT,
    alert_type TEXT,
    message TEXT,
    confidence REAL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sih_findings_inv
ON sih_findings(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_findings_value
ON sih_findings(value);

CREATE INDEX IF NOT EXISTS idx_sih_findings_type
ON sih_findings(finding_type);

CREATE INDEX IF NOT EXISTS idx_sih_events_job
ON sih_job_events(job_id);

CREATE INDEX IF NOT EXISTS idx_sih_identifiers_inv
ON sih_identifiers(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_relationships_inv
ON sih_relationships(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_watchlist_actor
ON sih_watchlist(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_alerts_actor
ON sih_alerts(actor_id);
