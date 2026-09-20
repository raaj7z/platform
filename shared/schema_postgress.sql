-- ============================================================
-- PRALAYX PostgreSQL Schema
-- ============================================================
--
-- PRALAYX owns the platform database.
--
-- The crawler keeps its native crawler database separately.
-- Normalized crawler output is imported into these tables.
--
-- ID format:
--   INV-XXXXXXXX
--   SES-XXXXXXXX
--   RUN-XXXXXXXX
--   ACT-XXXXXXXX
--   FIND-XXXXXXXX
-- ============================================================


-- ============================================================
-- ACTORS
-- ============================================================

CREATE TABLE IF NOT EXISTS sih_actors (
    actor_id TEXT PRIMARY KEY,
    display_name TEXT,
    category TEXT DEFAULT 'unknown',
    confidence DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
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

    crawler_session_id TEXT,
    crawler_investigation_id BIGINT,

    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_investigation_actor
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

    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_session_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_session_actor
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
    progress DOUBLE PRECISION DEFAULT 0.0,

    payload JSONB,
    result_ref TEXT,
    error TEXT,

    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_run_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_run_session
        FOREIGN KEY (session_id)
        REFERENCES sih_sessions(session_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_run_actor
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

    confidence DOUBLE PRECISION DEFAULT 0.5,

    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,

    CONSTRAINT fk_identifier_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_identifier_actor
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

    created_at TIMESTAMPTZ NOT NULL
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

    confidence DOUBLE PRECISION DEFAULT 0.5,

    metadata JSONB,

    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_finding_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_finding_actor
        FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_finding_run
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

    metadata JSONB,

    collected_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_evidence_finding
        FOREIGN KEY (finding_id)
        REFERENCES sih_findings(finding_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_evidence_source
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

    observed_at TIMESTAMPTZ NOT NULL,

    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,

    confidence DOUBLE PRECISION,

    metadata JSONB,

    CONSTRAINT fk_observation_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_observation_actor
        FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_observation_run
        FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_observation_source
        FOREIGN KEY (source_id)
        REFERENCES sih_sources(source_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_observation_evidence
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

    confidence DOUBLE PRECISION,

    metadata JSONB,

    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_sighting_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_sighting_actor
        FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_sighting_run
        FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_sighting_source
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

    confidence DOUBLE PRECISION,

    observed_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_relationship_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_relationship_run
        FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_relationship_source
        FOREIGN KEY (source_id)
        REFERENCES sih_sources(source_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_relationship_evidence
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

CREATE TABLE IF NOT EXISTS sih_raw_snapshots (
    snapshot_id TEXT PRIMARY KEY,

    investigation_id TEXT NOT NULL,
    session_id TEXT,
    run_id TEXT,

    source TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,

    payload JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_raw_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_raw_session
        FOREIGN KEY (session_id)
        REFERENCES sih_sessions(session_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_raw_run
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

    payload JSONB,

    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_timeline_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_timeline_session
        FOREIGN KEY (session_id)
        REFERENCES sih_sessions(session_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_timeline_run
        FOREIGN KEY (run_id)
        REFERENCES sih_runs(run_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_timeline_actor
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

    progress DOUBLE PRECISION DEFAULT 0.0,

    payload JSONB,

    result_ref TEXT,
    error TEXT,

    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_job_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_job_run
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

    progress DOUBLE PRECISION,

    payload JSONB,

    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_event_job
        FOREIGN KEY (job_id)
        REFERENCES sih_jobs(job_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_event_run
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

    file_size BIGINT DEFAULT 0,

    mime_type TEXT,

    status TEXT NOT NULL DEFAULT 'completed',

    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_report_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES sih_investigations(investigation_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_report_run
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

    enabled BOOLEAN DEFAULT TRUE,

    last_scan_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_watch_actor
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

    confidence DOUBLE PRECISION,

    is_read BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_alert_actor
        FOREIGN KEY (actor_id)
        REFERENCES sih_actors(actor_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_alert_finding
        FOREIGN KEY (finding_id)
        REFERENCES sih_findings(finding_id)
        ON DELETE SET NUL
