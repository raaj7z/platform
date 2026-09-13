
-- ADDITIVE: safe to apply to the existing crawler database.
-- Existing crawler tables are intentionally preserved.

CREATE TABLE IF NOT EXISTS actors (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    display_name TEXT,
    category TEXT,
    attribution_confidence REAL,
    confidence_level TEXT,
    first_seen TEXT,
    last_seen TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL,
    actor_id TEXT,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT,
    source TEXT DEFAULT 'manual',
    source_url TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_id) REFERENCES actors(id)
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    name TEXT,
    url TEXT,
    platform TEXT,
    reliability REAL,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL,
    finding_id INTEGER,
    source_id INTEGER,
    source_url TEXT,
    title TEXT,
    excerpt TEXT,
    content_hash TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    FOREIGN KEY (finding_id) REFERENCES findings(id),
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL,
    actor_id TEXT,
    finding_type TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT,
    source TEXT,
    source_url TEXT,
    confidence REAL DEFAULT 0.5,
    first_seen TEXT,
    last_seen TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_id) REFERENCES actors(id)
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL,
    actor_id TEXT,
    entity_type TEXT,
    value TEXT,
    source TEXT,
    source_url TEXT,
    observed_at TEXT,
    first_seen TEXT,
    last_seen TEXT,
    confidence REAL DEFAULT 0.5,
    evidence_id INTEGER,
    metadata TEXT,
    FOREIGN KEY (actor_id) REFERENCES actors(id),
    FOREIGN KEY (evidence_id) REFERENCES evidence(id)
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL,
    from_entity_type TEXT NOT NULL,
    from_entity_id TEXT NOT NULL,
    to_entity_type TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    source TEXT,
    source_url TEXT,
    confidence REAL DEFAULT 0.5,
    evidence_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    FOREIGN KEY (evidence_id) REFERENCES evidence(id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL DEFAULT 0,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    level TEXT DEFAULT 'info',
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    label TEXT,
    enabled INTEGER DEFAULT 1,
    interval_minutes INTEGER DEFAULT 360,
    last_scanned_at TEXT,
    next_scan_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(actor_id),
    FOREIGN KEY (actor_id) REFERENCES actors(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT,
    investigation_id TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    title TEXT NOT NULL,
    message TEXT,
    finding_id INTEGER,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_id) REFERENCES actors(id),
    FOREIGN KEY (finding_id) REFERENCES findings(id)
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

