"""
PRALAYX Seed Script -- Pre-populates data/pralayx.db with demonstration investigation (INV-DEMO-2026).
"""

import json
import sqlite3
from datetime import datetime, timezone
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pralayx.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "schema_sqlite.sql")

def seed():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_actors (actor_id, display_name, category, confidence, created_at, updated_at)
        VALUES ('ACT-VIPER-001', 'DarkViper_2024 / AetherSec_2026', 'hacking', 0.85, ?, ?)
        """,
        (now, now)
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_investigations
        (investigation_id, target, target_type, status, source, notes, actor_id, crawler_session_id, created_at, updated_at)
        VALUES ('INV-DEMO-2026', 'http://darkmarket-v2.onion', 'onion_service', 'completed', 'crawler',
                'SIH26151 Threat Actor De-anonymization Demonstration Case', 'ACT-VIPER-001', 'SES-DEMO-01', ?, ?)
        """,
        (now, now)
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_sessions (session_id, investigation_id, session_type, actor_id, status, created_at, updated_at)
        VALUES ('SES-DEMO-01', 'INV-DEMO-2026', 'crawl_and_osint', 'ACT-VIPER-001', 'completed', ?, ?)
        """,
        (now, now)
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_runs (run_id, investigation_id, session_id, actor_id, run_type, module_id, status, progress, created_at, updated_at)
        VALUES ('RUN-DEMO-CRAWL', 'INV-DEMO-2026', 'SES-DEMO-01', 'ACT-VIPER-001', 'crawl', 'DarkWeb-Deanonymization', 'COMPLETED', 1.0, ?, ?)
        """,
        (now, now)
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_sources (source_id, name, url, source_type, created_at)
        VALUES ('SRC-CRAWLER-01', 'DarkWeb-Deanonymization Crawler', 'http://darkmarket-v2.onion', 'tor_crawler', ?)
        """,
        (now,)
    )

    findings = [
        ("FIND-MISCFG-01", "server_status_exposed", "Exposed Apache Server-Status page at http://darkmarket-v2.onion/server-status", "DarkWeb-Deanonymization", "http://darkmarket-v2.onion/server-status", 0.95, json.dumps({"category": "exposed_server_status"})),
        ("FIND-MISCFG-02", "tls_cert_clearnet", "TLS Certificate CN leak: 'aether-sec.com'", "DarkWeb-Deanonymization", "https://darkmarket-v2.onion:443", 0.88, json.dumps({"category": "ssl_tls_clearnet", "domain": "aether-sec.com"})),
        ("FIND-MISCFG-03", "default_service_banner", "Default Service Banner: Apache/2.4.41 (Ubuntu) OpenSSH_7.9p1 Debian 10", "DarkWeb-Deanonymization", "http://darkmarket-v2.onion:22", 0.90, json.dumps({"category": "default_banner"})),
        ("FIND-MISCFG-04", "descriptor_inconsistency", "Descriptor Inconsistency: Clearnet contact email 'admin@aether-sec.com'", "DarkWeb-Deanonymization", "http://darkmarket-v2.onion/index.html", 0.85, json.dumps({"category": "descriptor_inconsistency"})),
        ("FIND-OSINT-01", "osint_match", "Shodan IP Match: 192.0.2.45 hosting OpenSSH_7.9p1", "OSINT Engine (Shodan)", "https://www.shodan.io/host/192.0.2.45", 0.85, json.dumps({"ip": "192.0.2.45"})),
        ("FIND-OSINT-02", "osint_match", "VirusTotal Domain Report: aether-sec.com registered via Namecheap", "OSINT Engine (VirusTotal)", "https://www.virustotal.com/gui/domain/aether-sec.com", 0.90, json.dumps({"domain": "aether-sec.com"})),
        ("FIND-OSINT-03", "crypto_wallet", "Observed Bitcoin Wallet: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "OSINT Engine (Crypto)", "http://darkmarket-v2.onion/vendor/darkviper", 0.95, json.dumps({"coin": "BTC"})),
        ("FIND-OSINT-04", "pgp_key", "PGP Key ID: 0x9E8F7A6B5C4D3E2F", "OSINT Engine (PGP)", "http://darkmarket-v2.onion/pgp.asc", 0.92, json.dumps({"key_id": "0x9E8F7A6B5C4D3E2F"})),
        ("FIND-STY-01", "stylometry_profile", "Stylometric Profile for DarkViper_2024 / AetherSec_2026", "Persona Engine", "http://127.0.0.1:8010/analyze", 0.82, json.dumps({"char_ngram_sim": 0.84})),
    ]

    for fid, ftype, val, src, surl, conf, meta in findings:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_findings
            (finding_id, investigation_id, actor_id, run_id, finding_type, value, source, source_url, confidence, metadata, first_seen, last_seen)
            VALUES (?, 'INV-DEMO-2026', 'ACT-VIPER-001', 'RUN-DEMO-CRAWL', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fid, ftype, val, src, surl, conf, meta, now, now)
        )

    relationships = [
        ("REL-01", "onion_service", "darkmarket-v2.onion", "hosts_misconfigured_status", "finding", "FIND-MISCFG-01", 0.95),
        ("REL-02", "onion_service", "darkmarket-v2.onion", "shares_tls_certificate", "domain", "aether-sec.com", 0.88),
        ("REL-03", "domain", "aether-sec.com", "resolves_to_ip", "ip", "192.0.2.45", 0.85),
        ("REL-04", "handle", "DarkViper_2024", "candidate_pseudonymous_continuity", "handle", "AetherSec_2026", 0.82),
        ("REL-05", "handle", "AetherSec_2026", "uses_contact_email", "email", "admin@aether-sec.com", 0.85),
        ("REL-06", "handle", "DarkViper_2024", "uses_crypto_wallet", "crypto_wallet", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 0.95),
    ]

    for rel_id, ftype, fval, rtype, ttype, tval, conf in relationships:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_relationships
            (relationship_id, investigation_id, run_id, from_type, from_value, relationship_type, to_type, to_value, confidence, observed_at)
            VALUES (?, 'INV-DEMO-2026', 'RUN-DEMO-CRAWL', ?, ?, ?, ?, ?, ?, ?)
            """,
            (rel_id, ftype, fval, rtype, ttype, tval, conf, now)
        )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    seed()
