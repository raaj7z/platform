-- SIH26151 canonical integration schema (PostgreSQL)
-- Logical schema matches schema_sqlite.sql.
-- Existing crawler tables can remain alongside these tables during migration.

CREATE TABLE IF NOT EXISTS actors (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    display_name TEXT,
    category TEXT,
    attribution_confidence DOUBLE PRECISION,
    confidence_level TEXT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS identifiers (
    id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    actor_id TEXT,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT,
    source TEXT DEFAULT 'manual',
    source_url TEXT,
    confidence DOUBLE PRECISION DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    name TEXT,
    url TEXT,
    platform TEXT,
    reliability DOUBLE PRECISION,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS findings (
    id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    actor_id TEXT,
    finding_type TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT,
    source TEXT,
    source_url TEXT,
    confidence DOUBLE PRECISION DEFAULT 0.5,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence (
    id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    finding_id BIGINT,
    source_id BIGINT,
    source_url TEXT,
    title TEXT,
    excerpt TEXT,
    content_hash TEXT,
    collected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS observations (
    id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    actor_id TEXT,
    entity_type TEXT,
    value TEXT,
    source TEXT,
    source_url TEXT,
    observed_at TIMESTAMPTZ,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    confidence DOUBLE PRECISION DEFAULT 0.5,
    evidence_id BIGINT,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS relationships (
    id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    from_entity_type TEXT NOT NULL,
    from_entity_id TEXT NOT NULL,
    to_entity_type TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    source TEXT,
    source_url TEXT,
    confidence DOUBLE PRECISION DEFAULT 0.5,
    evidence_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress DOUBLE PRECISION DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS job_events (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    level TEXT DEFAULT 'info',
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    id BIGSERIAL PRIMARY KEY,
    actor_id TEXT NOT NULL UNIQUE,
    label TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    interval_minutes INTEGER DEFAULT 360,
    last_scanned_at TIMESTAMPTZ,
    next_scan_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    actor_id TEXT,
    investigation_id TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    title TEXT NOT NULL,
    message TEXT,
    finding_id BIGINT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_actors_investigation ON actors(investigation_id);
CREATE INDEX IF NOT EXISTS idx_identifiers_investigation ON identifiers(investigation_id);
CREATE INDEX IF NOT EXISTS idx_findings_investigation ON findings(investigation_id);
CREATE INDEX IF NOT EXISTS idx_findings_actor ON findings(actor_id);
CREATE INDEX IF NOT EXISTS idx_observations_investigation ON observations(investigation_id);
CREATE INDEX IF NOT EXISTS idx_relationships_investigation ON relationships(investigation_id);
CREATE INDEX IF NOT EXISTS idx_jobs_investigation ON jobs(investigation_id);
CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_alerts_actor ON alerts(actor_id);

