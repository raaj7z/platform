PRAGMA foreign_keys = ON;

-- ============================================================
-- PRALAYX SQLite Schema
-- ============================================================
--
-- Database ownership:
--     PRALAYX platform
--
-- The crawler maintains its native crawler database separately.
-- The crawler adapter imports normalized data into these tables.
--
-- ID conventions:
--     INV-XXXXXXXX
--     SES-XXXXXXXX
--     RUN-XXXXXXXX
--     ACT-XXXXXXXX
--     FIND-XXXXXXXX
-- ============================================================


-- ============================================================
-- ACTORS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_actors (
    actor_id TEXT PRIMARY KEY,
    display_name TEXT,
    category TEXT DEFAULT 'unknown',
    confidence REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


-- ============================================================
-- INVESTIGATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_investigations (
    investigation_id TEXT PRIMARY KEY,

    target TEXT NOT NULL,
    target_type TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'running',

    source TEXT,
    notes TEXT,

    actor_id TEXT,

    -- Compatibility fields for the existing crawler.
    crawler_session_id TEXT,
    crawler_investigation_id INTEGER,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_investigations_status
    ON sih_investigations(status);

CREATE INDEX IF NOT EXISTS idx_sih_investigations_actor
    ON sih_investigations(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_investigations_updated
    ON sih_investigations(updated_at);


-- ============================================================
-- SESSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_sessions (
    session_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,
    session_type TEXT NOT NULL,

    actor_id TEXT,

    status TEXT NOT NULL DEFAULT 'running',

    metadata TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_sessions_investigation
    ON sih_sessions(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_sessions_type
    ON sih_sessions(session_type);

CREATE INDEX IF NOT EXISTS idx_sih_sessions_status
    ON sih_sessions(status);


-- ============================================================
-- RUNS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_runs (
    run_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,
    session_id TEXT,

    actor_id TEXT,

    run_type TEXT NOT NULL,
    module_id TEXT,

    status TEXT NOT NULL DEFAULT 'RUNNING',
    progress REAL DEFAULT 0.0,

    payload TEXT,
    result_ref TEXT,
    error TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (session_id)
        REFERENCES sih_sessions(session_id)
        ON DELETE SET NULL,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_runs_investigation
    ON sih_runs(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_runs_session
    ON sih_runs(session_id);

CREATE INDEX IF NOT EXISTS idx_sih_runs_type
    ON sih_runs(run_type);

CREATE INDEX IF NOT EXISTS idx_sih_runs_status
    ON sih_runs(status);


-- ============================================================
-- IDENTIFIERS
-- ============================================================

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
    last_seen TEXT,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_identifiers_inv
    ON sih_identifiers(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_identifiers_actor
    ON sih_identifiers(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_identifiers_type
    ON sih_identifiers(identifier_type);

CREATE INDEX IF NOT EXISTS idx_sih_identifiers_normalized
    ON sih_identifiers(normalized_value);


-- ============================================================
-- SOURCES
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_sources (
    source_id TEXT PRIMARY KEY,

    name TEXT NOT NULL,
    url TEXT,
    source_type TEXT,

    created_at TEXT NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_sources_name
    ON sih_sources(name);

CREATE INDEX IF NOT EXISTS idx_sih_sources_type
    ON sih_sources(source_type);


-- ============================================================
-- FINDINGS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_findings (
    finding_id TEXT PRIMARY KEY,

    investigation_id TEXT,
    actor_id TEXT,
    run_id TEXT,

    finding_type TEXT NOT NULL,
    value TEXT NOT NULL,

    source TEXT,
    source_url TEXT,

    confidence REAL DEFAULT 0.5,

    metadata TEXT,

    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_findings_inv
    ON sih_findings(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_findings_actor
    ON sih_findings(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_findings_run
    ON sih_findings(run_id);

CREATE INDEX IF NOT EXISTS idx_sih_findings_value
    ON sih_findings(value);

CREATE INDEX IF NOT EXISTS idx_sih_findings_type
    ON sih_findings(finding_type);

CREATE INDEX IF NOT EXISTS idx_sih_findings_confidence
    ON sih_findings(confidence);


-- ============================================================
-- EVIDENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_evidence (
    evidence_id TEXT PRIMARY KEY,

    finding_id TEXT,

    source_id TEXT,

    evidence_type TEXT,

    source_url TEXT,

    excerpt TEXT,

    metadata TEXT,

    collected_at TEXT NOT NULL,

    FOREIGN KEY (finding_id)
        REFERENCES sih_findings(finding_id)
        ON DELETE CASCADE,

    FOREIGN KEY (source_id)
        REFERENCES sih_sources(source_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_evidence_finding
    ON sih_evidence(finding_id);

CREATE INDEX IF NOT EXISTS idx_sih_evidence_source
    ON sih_evidence(source_id);

CREATE INDEX IF NOT EXISTS idx_sih_evidence_type
    ON sih_evidence(evidence_type);


-- ============================================================
-- OBSERVATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_observations (
    observation_id TEXT PRIMARY KEY,

    investigation_id TEXT,
    actor_id TEXT,
    run_id TEXT,

    entity_type TEXT,
    entity_value TEXT,

    source_id TEXT,
    evidence_id TEXT,

    observed_at TEXT NOT NULL,

    first_seen TEXT,
    last_seen TEXT,

    confidence REAL,

    metadata TEXT,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    FOREIGN KEY (source_id)
        REFERENCES sih_sources(source_id)
        ON DELETE SET NULL,

    FOREIGN KEY (evidence_id)
        REFERENCES sih_evidence(evidence_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_observations_inv
    ON sih_observations(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_observations_actor
    ON sih_observations(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_observations_entity
    ON sih_observations(entity_type, entity_value);

CREATE INDEX IF NOT EXISTS idx_sih_observations_run
    ON sih_observations(run_id);


-- ============================================================
-- ENTITY SIGHTINGS
-- ============================================================
--
-- Same entity can appear across different investigations/sessions.
-- This table preserves those sightings instead of creating duplicate
-- conceptual entities.
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_entity_sightings (
    sighting_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,
    actor_id TEXT,
    run_id TEXT,

    entity_type TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    raw_value TEXT,

    source_id TEXT,
    source_url TEXT,

    confidence REAL,

    metadata TEXT,

    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    FOREIGN KEY (source_id)
        REFERENCES sih_sources(source_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_sightings_inv
    ON sih_entity_sightings(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_sightings_actor
    ON sih_entity_sightings(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_sightings_entity
    ON sih_entity_sightings(entity_type, normalized_value);

CREATE INDEX IF NOT EXISTS idx_sih_sightings_source
    ON sih_entity_sightings(source_id);


-- ============================================================
-- RELATIONSHIPS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_relationships (
    relationship_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,
    run_id TEXT,

    from_type TEXT NOT NULL,
    from_value TEXT NOT NULL,

    relationship_type TEXT NOT NULL,

    to_type TEXT NOT NULL,
    to_value TEXT NOT NULL,

    source_id TEXT,
    evidence_id TEXT,

    confidence REAL,

    observed_at TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    FOREIGN KEY (source_id)
        REFERENCES sih_sources(source_id)
        ON DELETE SET NULL,

    FOREIGN KEY (evidence_id)
        REFERENCES sih_evidence(evidence_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_relationships_inv
    ON sih_relationships(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_relationships_from
    ON sih_relationships(from_type, from_value);

CREATE INDEX IF NOT EXISTS idx_sih_relationships_to
    ON sih_relationships(to_type, to_value);

CREATE INDEX IF NOT EXISTS idx_sih_relationships_type
    ON sih_relationships(relationship_type);


-- ============================================================
-- RAW SNAPSHOTS
-- ============================================================
--
-- Raw crawler / OSINT output is preserved before normalization or
-- AI processing.
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_raw_snapshots (
    snapshot_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,
    session_id TEXT,
    run_id TEXT,

    source TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,

    payload TEXT NOT NULL,

    created_at TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (session_id)
        REFERENCES sih_sessions(session_id)
        ON DELETE SET NULL,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_raw_inv
    ON sih_raw_snapshots(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_raw_session
    ON sih_raw_snapshots(session_id);

CREATE INDEX IF NOT EXISTS idx_sih_raw_run
    ON sih_raw_snapshots(run_id);

CREATE INDEX IF NOT EXISTS idx_sih_raw_source
    ON sih_raw_snapshots(source);


-- ============================================================
-- INVESTIGATION TIMELINE
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_investigation_timeline (
    timeline_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,

    session_id TEXT,
    run_id TEXT,
    actor_id TEXT,

    event_type TEXT NOT NULL,
    message TEXT NOT NULL,

    payload TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (session_id)
        REFERENCES sih_sessions(session_id)
        ON DELETE SET NULL,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_timeline_inv
    ON sih_investigation_timeline(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_timeline_session
    ON sih_investigation_timeline(session_id);

CREATE INDEX IF NOT EXISTS idx_sih_timeline_run
    ON sih_investigation_timeline(run_id);

CREATE INDEX IF NOT EXISTS idx_sih_timeline_created
    ON sih_investigation_timeline(created_at);


-- ============================================================
-- JOBS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_jobs (
    job_id TEXT PRIMARY KEY,

    investigation_id TEXT,

    run_id TEXT,

    job_type TEXT,

    status TEXT,

    progress REAL DEFAULT 0.0,

    payload TEXT,

    result_ref TEXT,

    error TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_jobs_inv
    ON sih_jobs(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_jobs_run
    ON sih_jobs(run_id);

CREATE INDEX IF NOT EXISTS idx_sih_jobs_status
    ON sih_jobs(status);


-- ============================================================
-- JOB / TERMINAL EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_job_events (
    event_id TEXT PRIMARY KEY,

    job_id TEXT NOT NULL,
    run_id TEXT,

    event_type TEXT,

    message TEXT,

    progress REAL,

    payload TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (job_id)
        REFERENCES sih_jobs(job_id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_events_job
    ON sih_job_events(job_id);

CREATE INDEX IF NOT EXISTS idx_sih_events_run
    ON sih_job_events(run_id);

CREATE INDEX IF NOT EXISTS idx_sih_events_created
    ON sih_job_events(created_at);


-- ============================================================
-- REPORT REGISTRY
-- ============================================================
--
-- Every generated report gets its own row.
-- Existing reports are never overwritten by this registry.
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_reports (
    report_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,

    run_id TEXT,
    module_id TEXT,

    stage TEXT NOT NULL,
    report_type TEXT NOT NULL,
    format TEXT NOT NULL,

    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,

    file_size INTEGER DEFAULT 0,

    mime_type TEXT,

    status TEXT NOT NULL DEFAULT 'completed',

    created_at TEXT NOT NULL,

    FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_reports_inv
    ON sih_reports(investigation_id);

CREATE INDEX IF NOT EXISTS idx_sih_reports_run
    ON sih_reports(run_id);

CREATE INDEX IF NOT EXISTS idx_sih_reports_stage
    ON sih_reports(stage);

CREATE INDEX IF NOT EXISTS idx_sih_reports_type
    ON sih_reports(report_type);

CREATE INDEX IF NOT EXISTS idx_sih_reports_created
    ON sih_reports(created_at);


-- ============================================================
-- WATCHLIST
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_watchlist (
    watch_id TEXT PRIMARY KEY,

    actor_id TEXT NOT NULL,

    interval_minutes INTEGER DEFAULT 60,

    enabled INTEGER DEFAULT 1,

    last_scan_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_sih_watchlist_actor
    ON sih_watchlist(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_watchlist_enabled
    ON sih_watchlist(enabled);


-- ============================================================
-- ALERTS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_alerts (
    alert_id TEXT PRIMARY KEY,

    actor_id TEXT,
    finding_id TEXT,

    alert_type TEXT,

    message TEXT,

    confidence REAL,

    is_read INTEGER DEFAULT 0,

    created_at TEXT NOT NULL,

    FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    FOREIGN KEY (finding_id)
        REFERENCES sih_findings(finding_id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_sih_alerts_actor
    ON sih_alerts(actor_id);

CREATE INDEX IF NOT EXISTS idx_sih_alerts_finding
    ON sih_alerts(finding_id);

CREATE INDEX IF NOT EXISTS idx_sih_alerts_read
    ON sih_alerts(is_read);

CREATE INDEX IF NOT EXISTS idx_sih_alerts_created
    ON sih_alerts(created_at);


-- ============================================================
-- MIGRATION MARKERS
-- ============================================================
--
-- Used by future schema migrations without requiring the existing
-- database to be deleted.
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL
);


INSERT OR IGNORE INTO sih_schema_meta (
    key,
    value,
    updated_at
)
VALUES (
    'schema_version',
    '2',
    datetime('now')
);
