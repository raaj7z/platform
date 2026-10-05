"""
PRALAYX Seed Script -- Pre-populates canonical data/pralayx.db with a complete,
evidence-backed demonstration investigation (INV-DEMO-2026).
"""

import json
import sqlite3
from datetime import datetime, timezone
import os

from .config import SCHEMA_PATH


DB_PATH = os.getenv(
    "PRALAYX_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "pralayx.db"),
)


def seed():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # 1. Actor
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_actors
        (actor_id, display_name, category, confidence, created_at, updated_at)
        VALUES
        ('ACT-VIPER-001',
         'DarkViper_2024 / AetherSec_2026',
         'hacking',
         0.85,
         ?,
         ?)
        """,
        (now, now),
    )

    # 2. Investigation
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_investigations
        (
            investigation_id,
            target,
            target_type,
            status,
            source,
            notes,
            actor_id,
            crawler_session_id,
            created_at,
            updated_at
        )
        VALUES
        (
            'INV-DEMO-2026',
            'http://darkmarket-v2.onion',
            'onion_service',
            'completed',
            'crawler',
            'SIH26151 Threat Actor De-anonymization Demonstration Case',
            'ACT-VIPER-001',
            'SES-DEMO-01',
            ?,
            ?
        )
        """,
        (now, now),
    )

    # 3. Sessions & Runs
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_sessions
        (
            session_id,
            investigation_id,
            session_type,
            actor_id,
            status,
            created_at,
            updated_at
        )
        VALUES
        (
            'SES-DEMO-01',
            'INV-DEMO-2026',
            'crawl_and_osint',
            'ACT-VIPER-001',
            'completed',
            ?,
            ?
        )
        """,
        (now, now),
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_runs
        (
            run_id,
            investigation_id,
            session_id,
            actor_id,
            run_type,
            module_id,
            status,
            progress,
            created_at,
            updated_at
        )
        VALUES
        (
            'RUN-DEMO-CRAWL',
            'INV-DEMO-2026',
            'SES-DEMO-01',
            'ACT-VIPER-001',
            'crawl',
            'DarkWeb-Deanonymization',
            'COMPLETED',
            1.0,
            ?,
            ?
        )
        """,
        (now, now),
    )

    # 4. Sources
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_sources
        (
            source_id,
            name,
            url,
            source_type,
            created_at
        )
        VALUES
        (
            'SRC-CRAWLER-01',
            'DarkWeb-Deanonymization Crawler',
            'http://darkmarket-v2.onion',
            'tor_crawler',
            ?
        )
        """,
        (now,),
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_sources
        (
            source_id,
            name,
            url,
            source_type,
            created_at
        )
        VALUES
        (
            'SRC-OSINT-01',
            'OSINT Engine (Shodan / VT)',
            'https://shodan.io',
            'osint_provider',
            ?
        )
        """,
        (now,),
    )

    # 5. Technical Misconfigurations / OSINT / Persona Findings
    findings = [
        # Cat 1: Exposed Server Status
        (
            "FIND-MISCFG-01",
            "server_status_exposed",
            "Exposed Apache Server-Status page at http://darkmarket-v2.onion/server-status",
            "DarkWeb-Deanonymization",
            "http://darkmarket-v2.onion/server-status",
            0.95,
            json.dumps(
                {
                    "category": "exposed_server_status",
                    "http_status": 200,
                    "length": 4520,
                }
            ),
        ),

        # Cat 2: SSL/TLS certificate clearnet link
        (
            "FIND-MISCFG-02",
            "tls_cert_clearnet",
            "TLS Certificate CN leak: 'aether-sec.com' (SANs: *.aether-sec.com, darkmarket-v2.onion)",
            "DarkWeb-Deanonymization",
            "https://darkmarket-v2.onion:443",
            0.88,
            json.dumps(
                {
                    "category": "ssl_tls_clearnet",
                    "domain": "aether-sec.com",
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                }
            ),
        ),

        # Cat 3: Default Service Banner
        (
            "FIND-MISCFG-03",
            "default_service_banner",
            "Default Service Banner: Apache/2.4.41 (Ubuntu) OpenSSH_7.9p1 Debian 10",
            "DarkWeb-Deanonymization",
            "http://darkmarket-v2.onion:22",
            0.90,
            json.dumps(
                {
                    "category": "default_banner",
                    "banner": "SSH-2.0-OpenSSH_7.9p1 Debian-10+deb10u2",
                }
            ),
        ),

        # Cat 4: Descriptor / Metadata Inconsistency
        (
            "FIND-MISCFG-04",
            "descriptor_inconsistency",
            "Descriptor Inconsistency: Clearnet contact email 'admin@aether-sec.com' found in HTML meta tag",
            "DarkWeb-Deanonymization",
            "http://darkmarket-v2.onion/index.html",
            0.85,
            json.dumps(
                {
                    "category": "descriptor_inconsistency",
                    "leaked_email": "admin@aether-sec.com",
                }
            ),
        ),

        # OSINT Finding 1
        (
            "FIND-OSINT-01",
            "osint_match",
            "Shodan IP Match: 192.0.2.45 hosting OpenSSH_7.9p1 with matching TLS certificate fingerprint",
            "OSINT Engine (Shodan)",
            "https://www.shodan.io/host/192.0.2.45",
            0.85,
            json.dumps(
                {
                    "provider": "shodan",
                    "ip": "192.0.2.45",
                    "ports": [22, 80, 443],
                }
            ),
        ),

        # OSINT Finding 2
        (
            "FIND-OSINT-02",
            "osint_match",
            "VirusTotal Domain Report: aether-sec.com registered via Namecheap 2024-03-12",
            "OSINT Engine (VirusTotal)",
            "https://www.virustotal.com/gui/domain/aether-sec.com",
            0.90,
            json.dumps(
                {
                    "provider": "virustotal",
                    "domain": "aether-sec.com",
                }
            ),
        ),

        # OSINT Finding 3
        (
            "FIND-OSINT-03",
            "crypto_wallet",
            "Observed Bitcoin Wallet: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa in vendor signatures",
            "OSINT Engine (Crypto)",
            "http://darkmarket-v2.onion/vendor/darkviper",
            0.95,
            json.dumps(
                {
                    "coin": "BTC",
                    "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                }
            ),
        ),

        # OSINT Finding 4
        (
            "FIND-OSINT-04",
            "pgp_key",
            "PGP Key ID: 0x9E8F7A6B5C4D3E2F (User: DarkViper <darkviper@secmail.invalid>)",
            "OSINT Engine (PGP)",
            "http://darkmarket-v2.onion/pgp.asc",
            0.92,
            json.dumps(
                {
                    "key_id": "0x9E8F7A6B5C4D3E2F",
                    "fingerprint": "9E8F7A6B5C4D3E2F1234567890ABCDEF12345678",
                }
            ),
        ),

        # Persona Stylometry Finding
        (
            "FIND-STY-01",
            "stylometry_profile",
            "Stylometric Profile for DarkViper_2024 / AetherSec_2026: Char n-gram cosine sim = 0.84, TTR = 0.62",
            "Persona Engine",
            "http://127.0.0.1:8010/analyze",
            0.82,
            json.dumps(
                {
                    "usable": True,
                    "type_token_ratio": 0.62,
                    "char_ngram_sim": 0.84,
                    "function_word_overlap": 0.79,
                }
            ),
        ),
    ]

    for fid, ftype, val, src, surl, conf, meta in findings:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_findings
            (
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
            VALUES
            (
                ?,
                'INV-DEMO-2026',
                'ACT-VIPER-001',
                'RUN-DEMO-CRAWL',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                fid,
                ftype,
                val,
                src,
                surl,
                conf,
                meta,
                now,
                now,
            ),
        )

        # Attach evidence record
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_evidence
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
            VALUES
            (?, ?, 'SRC-CRAWLER-01', ?, ?, ?, ?, ?)
            """,
            (
                f"EVD-{fid}",
                fid,
                ftype,
                surl,
                f"Observed finding: {val}",
                meta,
                now,
            ),
        )

    # 6. Identifiers
    identifiers = [
        (
            "ID-01",
            "onion_service",
            "darkmarket-v2.onion",
            0.99,
        ),
        (
            "ID-02",
            "domain",
            "aether-sec.com",
            0.88,
        ),
        (
            "ID-03",
            "ip",
            "192.0.2.45",
            0.85,
        ),
        (
            "ID-04",
            "handle",
            "DarkViper_2024",
            0.90,
        ),
        (
            "ID-05",
            "handle",
            "AetherSec_2026",
            0.85,
        ),
        (
            "ID-06",
            "email",
            "admin@aether-sec.com",
            0.85,
        ),
        (
            "ID-07",
            "crypto_wallet",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            0.95,
        ),
        (
            "ID-08",
            "pgp_key",
            "0x9E8F7A6B5C4D3E2F",
            0.92,
        ),
    ]

    for id_val, itype, val, conf in identifiers:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_identifiers
            (
                identifier_id,
                investigation_id,
                actor_id,
                identifier_type,
                value,
                normalized_value,
                source,
                confidence,
                first_seen,
                last_seen
            )
            VALUES
            (
                ?,
                'INV-DEMO-2026',
                'ACT-VIPER-001',
                ?,
                ?,
                ?,
                'Platform Harvester',
                ?,
                ?,
                ?
            )
            """,
            (
                id_val,
                itype,
                val,
                val.lower(),
                conf,
                now,
                now,
            ),
        )

    # 7. Relationships (Relationship Graph)
    relationships = [
        (
            "REL-01",
            "onion_service",
            "darkmarket-v2.onion",
            "hosts_misconfigured_status",
            "finding",
            "FIND-MISCFG-01",
            0.95,
            "observed",
        ),
        (
            "REL-02",
            "onion_service",
            "darkmarket-v2.onion",
            "shares_tls_certificate",
            "domain",
            "aether-sec.com",
            0.88,
            "observed",
        ),
        (
            "REL-03",
            "domain",
            "aether-sec.com",
            "resolves_to_ip",
            "ip",
            "192.0.2.45",
            0.85,
            "observed",
        ),
        (
            "REL-04",
            "handle",
            "DarkViper_2024",
            "candidate_pseudonymous_continuity",
            "handle",
            "AetherSec_2026",
            0.82,
            "inferred",
        ),
        (
            "REL-05",
            "handle",
            "AetherSec_2026",
            "uses_contact_email",
            "email",
            "admin@aether-sec.com",
            0.85,
            "inferred",
        ),
        (
            "REL-06",
            "handle",
            "DarkViper_2024",
            "uses_crypto_wallet",
            "crypto_wallet",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            0.95,
            "observed",
        ),
    ]

    for (
        rel_id,
        ftype,
        fval,
        rtype,
        ttype,
        tval,
        conf,
        obs_inf,
    ) in relationships:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_relationships
            (
                relationship_id,
                investigation_id,
                run_id,
                from_type,
                from_value,
                relationship_type,
                to_type,
                to_value,
                confidence,
                observed_at
            )
            VALUES
            (
                ?,
                'INV-DEMO-2026',
                'RUN-DEMO-CRAWL',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                rel_id,
                ftype,
                fval,
                rtype,
                ttype,
                tval,
                conf,
                now,
            ),
        )

    # 8. Timeline Events
    timeline = [
        (
            "TIME-01",
            "investigation_created",
            "Investigation INV-DEMO-2026 created for target http://darkmarket-v2.onion",
        ),
        (
            "TIME-02",
            "crawl_completed",
            "Crawler collected 14 pages and extracted 4 technical misconfigurations",
        ),
        (
            "TIME-03",
            "osint_completed",
            "OSINT engine matched domain aether-sec.com and IP 192.0.2.45 via Shodan & VirusTotal",
        ),
        (
            "TIME-04",
            "persona_analyzed",
            "AI Stylometry detected candidate pseudonymous continuity (similarity 0.82) between DarkViper_2024 and AetherSec_2026",
        ),
        (
            "TIME-05",
            "correlation_updated",
            "Relationship correlation graph generated with 6 evidence-backed links",
        ),
        (
            "TIME-06",
            "report_generated",
            "Consolidated investigation reports generated in PDF, HTML, JSON, and CSV formats",
        ),
    ]

    for tid, etype, msg in timeline:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_investigation_timeline
            (
                timeline_id,
                investigation_id,
                session_id,
                run_id,
                actor_id,
                event_type,
                message,
                created_at
            )
            VALUES
            (
                ?,
                'INV-DEMO-2026',
                'SES-DEMO-01',
                'RUN-DEMO-CRAWL',
                'ACT-VIPER-001',
                ?,
                ?,
                ?
            )
            """,
            (
                tid,
                etype,
                msg,
                now,
            ),
        )

    # 9. Watchlist Entry & Alert
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_watchlist
        (
            watch_id,
            actor_id,
            target,
            investigation_id,
            interval_minutes,
            enabled,
            last_scan_at,
            created_at,
            updated_at
        )
        VALUES
        (
            'WATCH-VIPER-01',
            'ACT-VIPER-001',
            'DarkViper_2024',
            'INV-DEMO-2026',
            60,
            1,
            ?,
            ?,
            ?
        )
        """,
        (now, now, now),
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sih_alerts
        (
            alert_id,
            investigation_id,
            actor_id,
            finding_id,
            alert_type,
            message,
            confidence,
            is_read,
            created_at
        )
        VALUES
        (
            'ALT-DEMO-01',
            'INV-DEMO-2026',
            'ACT-VIPER-001',
            'FIND-MISCFG-02',
            'high_exposure_alert',
            'HIGH OPSEC EXPOSURE (85/100): TLS certificate leak associated with clearnet domain aether-sec.com',
            0.88,
            0,
            ?
        )
        """,
        (now,),
    )

    conn.commit()
    conn.close()

    print("Successfully seeded INV-DEMO-2026 in data/pralayx.db!")


if __name__ == "__main__":
    seed()
