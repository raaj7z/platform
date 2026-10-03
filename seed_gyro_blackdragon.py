import sqlite3
import json
from datetime import datetime, timezone, timedelta

DB_PATH = "/home/raaj/sih/platform/data/pralayx.db"

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat().replace("+00:00", "Z")

    def t_offset(minutes_ago):
        return (now_dt - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")

    print("[*] Seeding Threat Actor 1: gyroghost (INV-GYRO-GHOST)...")

    # 1. Actor
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_actors (actor_id, display_name, category, confidence, created_at, updated_at)
        VALUES ('ACT-GYRO-GHOST', 'GyroGhost (gyroghost / ghost_vortex / gyro_cyber)', 'hacking', 0.94, ?, ?)
        """,
        (t_offset(1440), now)
    )

    # 2. Investigation
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_investigations
        (investigation_id, target, target_type, status, source, notes, actor_id, created_at, updated_at)
        VALUES ('INV-GYRO-GHOST', 'http://gyro-blackmarket.onion', 'onion_service', 'completed', 'osint_engine',
                'GyroGhost Alias Mutation & Cross-Market Data Broker Tracking', 'ACT-GYRO-GHOST', ?, ?)
        """,
        (t_offset(1440), now)
    )

    # 3. Findings & Evidence for gyroghost
    gyro_findings = [
        ("FIND-GYRO-01", "handle", "gyroghost", "BreachForums v4", "http://breachforums-v4.onion/u/gyroghost", 0.96, "Primary handle selling 12GB breach database dumps"),
        ("FIND-GYRO-02", "handle", "ghost_vortex", "DarkFox Market", "http://darkfox-market.onion/vendor/ghost_vortex", 0.92, "Mutated handle offering stolen corporate access"),
        ("FIND-GYRO-03", "handle", "gyro_cyber", "Telegram Channel", "https://t.me/gyro_cyber_channel", 0.90, "Rebranded Telegram handle selling zero-day exploits"),
        ("FIND-GYRO-04", "crypto", "bc1qgyroghostwallet88888888888888888888", "Blockchain Ledger", "https://mempool.space/address/bc1qgyroghostwallet88888888888888888888", 0.98, "Shared BTC wallet reused across BreachForums and DarkFox"),
        ("FIND-GYRO-05", "pgp", "0xGYRO8888GHOST", "PGP Key Server", "hkp://keys.openpgp.org", 0.99, "Cryptographic subkey collision between gyroghost and ghost_vortex"),
        ("FIND-GYRO-06", "stylometry", "Punctuation & Syntax Match (91%)", "Persona Profiler", "NLP Engine", 0.91, "91% Cosine Similarity: Russian-English transliteration & triple exclamation syntax"),
        ("FIND-GYRO-07", "ip", "185.220.101.99", "Tor Relay Monitor", "http://185.220.101.99:9001", 0.89, "Tor guard relay IP observed during authentication sessions")
    ]

    for fid, ftype, val, src, surl, conf, desc in gyro_findings:
        meta = json.dumps({"description": desc})
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_findings
            (finding_id, investigation_id, actor_id, finding_type, value, source, source_url, confidence, metadata, first_seen, last_seen)
            VALUES (?, 'INV-GYRO-GHOST', 'ACT-GYRO-GHOST', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fid, ftype, val, src, surl, conf, meta, t_offset(1200), now)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_evidence
            (evidence_id, finding_id, evidence_type, source_url, excerpt, metadata, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (f"EVD-{fid}", fid, ftype, surl, desc, meta, t_offset(1200))
        )

    # 4. Relationships for gyroghost
    gyro_rels = [
        ("REL-GYRO-01", "handle", "gyroghost", "mutated_to", "handle", "ghost_vortex", 0.92),
        ("REL-GYRO-02", "handle", "ghost_vortex", "rebranded_as", "handle", "gyro_cyber", 0.90),
        ("REL-GYRO-03", "handle", "gyroghost", "uses_crypto_wallet", "crypto", "bc1qgyroghostwallet88888888888888888888", 0.98),
        ("REL-GYRO-04", "handle", "ghost_vortex", "uses_crypto_wallet", "crypto", "bc1qgyroghostwallet88888888888888888888", 0.98),
        ("REL-GYRO-05", "handle", "gyroghost", "uses_pgp_key", "pgp", "0xGYRO8888GHOST", 0.99),
        ("REL-GYRO-06", "handle", "gyro_cyber", "authenticated_from_ip", "ip", "185.220.101.99", 0.89)
    ]
    for rid, ft, fv, rt, tt, tv, conf in gyro_rels:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_relationships
            (relationship_id, investigation_id, from_type, from_value, relationship_type, to_type, to_value, confidence, observed_at)
            VALUES (?, 'INV-GYRO-GHOST', ?, ?, ?, ?, ?, ?, ?)
            """,
            (rid, ft, fv, rt, tt, tv, conf, t_offset(1000))
        )

    # 5. Timeline for gyroghost
    gyro_timeline = [
        ("TL-GYRO-01", "CASE_INITIALIZED", "Investigation initialized for target http://gyro-blackmarket.onion", t_offset(1440)),
        ("TL-GYRO-02", "ALIAS_DISCOVERED", "Handle gyroghost identified on BreachForums selling 12GB database dump.", t_offset(1200)),
        ("TL-GYRO-03", "CRYPTO_LINKED", "Bitcoin wallet bc1qgyroghostwallet88888888888888888888 extracted from signature.", t_offset(1000)),
        ("TL-GYRO-04", "MUTATION_DETECTED", "Handle ghost_vortex registered on DarkFox Market. PGP subkey 0xGYRO8888GHOST collision confirmed.", t_offset(800)),
        ("TL-GYRO-05", "STYLOMETRY_MATCH", "Persona Profiler calculated 91% linguistic match between gyroghost and ghost_vortex.", t_offset(600)),
        ("TL-GYRO-06", "INFRASTRUCTURE_LINKED", "Authentication logs linked ghost_vortex to Tor relay IP 185.220.101.99.", t_offset(400)),
        ("TL-GYRO-07", "REBRAND_EVENT", "Target rebranded to Telegram handle @gyro_cyber selling zero-day exploit payloads.", t_offset(200)),
        ("TL-GYRO-08", "ATTRIBUTION_CONFIRMED", "High-confidence persona migration chain established (gyroghost -> ghost_vortex -> gyro_cyber).", t_offset(50))
    ]
    for tid, etype, msg, cat in gyro_timeline:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_investigation_timeline
            (timeline_id, investigation_id, actor_id, event_type, message, created_at)
            VALUES (?, 'INV-GYRO-GHOST', 'ACT-GYRO-GHOST', ?, ?, ?)
            """,
            (tid, etype, msg, cat)
        )

    print("[*] Seeding Threat Actor 2: blackdragon (INV-BLACK-DRAGON)...")

    # 6. Actor 2
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_actors (actor_id, display_name, category, confidence, created_at, updated_at)
        VALUES ('ACT-BLACK-DRAGON', 'BlackDragon (blackdragon / dark_dragon_x / dragon_syndicate)', 'weaponry', 0.97, ?, ?)
        """,
        (t_offset(1800), now)
    )

    # 7. Investigation 2
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_investigations
        (investigation_id, target, target_type, status, source, notes, actor_id, created_at, updated_at)
        VALUES ('INV-BLACK-DRAGON', 'http://blackdragon-armory.onion', 'onion_service', 'completed', 'osint_engine',
                'BlackDragon Alias Mutation & Cyber Weapons Profiling', 'ACT-BLACK-DRAGON', ?, ?)
        """,
        (t_offset(1800), now)
    )

    # 8. Findings & Evidence for blackdragon
    dragon_findings = [
        ("FIND-DRAGON-01", "handle", "blackdragon", "SilkRoad v3", "http://silkroad-v3.onion/vendor/blackdragon", 0.97, "Primary darknet handle selling explosives & ordnance"),
        ("FIND-DRAGON-02", "handle", "dark_dragon_x", "BlackAxe Armory", "http://blackaxe-armory.onion/vendor/dark_dragon_x", 0.95, "Mutated alias offering military grade hardware"),
        ("FIND-DRAGON-03", "handle", "dragon_syndicate", "Dread Forum", "http://dread-forum.onion/user/dragon_syndicate", 0.93, "Syndicate persona selling zero-day exploit frameworks"),
        ("FIND-DRAGON-04", "crypto", "bc1qblackdragonwallet77777777777777777", "Blockchain Ledger", "https://mempool.space/address/bc1qblackdragonwallet77777777777777777", 0.99, "Shared crypto wallet confirmed on SilkRoad v3 and BlackAxe"),
        ("FIND-DRAGON-05", "pgp", "0xDRAGON7777BLACK", "PGP Key Server", "hkp://keys.openpgp.org", 0.99, "Master PGP public key used by blackdragon and dark_dragon_x"),
        ("FIND-DRAGON-06", "stylometry", "Bullet & Price Syntax Match (96%)", "Persona Profiler", "NLP Engine", 0.96, "96% Stylometric similarity: identical $XXXX/BTC price tag format and bullet formatting"),
        ("FIND-DRAGON-07", "tls_cert", "SHA256:BLACKDRAGON999999999999999999", "C2 Mesh", "https://dragon-c2-internal.net", 0.92, "Self-signed TLS certificate fingerprint matched on backend relay")
    ]

    for fid, ftype, val, src, surl, conf, desc in dragon_findings:
        meta = json.dumps({"description": desc})
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_findings
            (finding_id, investigation_id, actor_id, finding_type, value, source, source_url, confidence, metadata, first_seen, last_seen)
            VALUES (?, 'INV-BLACK-DRAGON', 'ACT-BLACK-DRAGON', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fid, ftype, val, src, surl, conf, meta, t_offset(1500), now)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_evidence
            (evidence_id, finding_id, evidence_type, source_url, excerpt, metadata, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (f"EVD-{fid}", fid, ftype, surl, desc, meta, t_offset(1500))
        )

    # 9. Relationships for blackdragon
    dragon_rels = [
        ("REL-DRAGON-01", "handle", "blackdragon", "mutated_to", "handle", "dark_dragon_x", 0.95),
        ("REL-DRAGON-02", "handle", "dark_dragon_x", "expanded_to", "handle", "dragon_syndicate", 0.93),
        ("REL-DRAGON-03", "handle", "blackdragon", "uses_crypto_wallet", "crypto", "bc1qblackdragonwallet77777777777777777", 0.99),
        ("REL-DRAGON-04", "handle", "dark_dragon_x", "uses_crypto_wallet", "crypto", "bc1qblackdragonwallet77777777777777777", 0.99),
        ("REL-DRAGON-05", "handle", "blackdragon", "uses_pgp_key", "pgp", "0xDRAGON7777BLACK", 0.99),
        ("REL-DRAGON-06", "handle", "dragon_syndicate", "uses_tls_certificate", "tls_cert", "SHA256:BLACKDRAGON999999999999999999", 0.92)
    ]
    for rid, ft, fv, rt, tt, tv, conf in dragon_rels:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_relationships
            (relationship_id, investigation_id, from_type, from_value, relationship_type, to_type, to_value, confidence, observed_at)
            VALUES (?, 'INV-BLACK-DRAGON', ?, ?, ?, ?, ?, ?, ?)
            """,
            (rid, ft, fv, rt, tt, tv, conf, t_offset(1200))
        )

    # 10. Timeline for blackdragon
    dragon_timeline = [
        ("TL-DRAGON-01", "CASE_INITIALIZED", "Investigation initialized for target http://blackdragon-armory.onion", t_offset(1800)),
        ("TL-DRAGON-02", "ALIAS_DISCOVERED", "Handle blackdragon indexed on SilkRoad v3 offering specialized darknet contraband.", t_offset(1600)),
        ("TL-DRAGON-03", "PGP_HARVESTED", "PGP Master Key 0xDRAGON7777BLACK published on open keyserver.", t_offset(1400)),
        ("TL-DRAGON-04", "MUTATION_DETECTED", "New vendor profile dark_dragon_x created on BlackAxe Armory using identical PGP public key.", t_offset(1100)),
        ("TL-DRAGON-05", "STYLOMETRY_MATCH", "Persona Profiler flagged 96% stylometric match (sentence length distribution, price syntax $XXXX/BTC).", t_offset(800)),
        ("TL-DRAGON-06", "CRYPTO_LINKED", "Bitcoin payment address bc1qblackdragonwallet77777777777777777 confirmed across both market listings.", t_offset(500)),
        ("TL-DRAGON-07", "INFRASTRUCTURE_CORRELATED", "TLS Certificate SHA256:BLACKDRAGON999999999999999999 matched on C2 backend relay.", t_offset(200)),
        ("TL-DRAGON-08", "DEANONYMIZATION_COMPLETE", "Threat actor entity BlackDragon de-anonymized with multi-alias historical tracking (blackdragon -> dark_dragon_x -> dragon_syndicate).", t_offset(30))
    ]
    for tid, etype, msg, cat in dragon_timeline:
        conn.execute(
            """
            INSERT OR REPLACE INTO sih_investigation_timeline
            (timeline_id, investigation_id, actor_id, event_type, message, created_at)
            VALUES (?, 'INV-BLACK-DRAGON', 'ACT-BLACK-DRAGON', ?, ?, ?)
            """,
            (tid, etype, msg, cat)
        )

    # 11. Watchlist items
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_watchlist (watch_id, target, investigation_id, actor_id, interval_minutes, status, last_scan_at, created_at, updated_at)
        VALUES ('WATCH-GYRO-01', 'http://gyro-blackmarket.onion', 'INV-GYRO-GHOST', 'ACT-GYRO-GHOST', 30, 'IDLE', ?, ?, ?)
        """,
        (t_offset(100), now, now)
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_watchlist (watch_id, target, investigation_id, actor_id, interval_minutes, status, last_scan_at, created_at, updated_at)
        VALUES ('WATCH-DRAGON-01', 'http://blackdragon-armory.onion', 'INV-BLACK-DRAGON', 'ACT-BLACK-DRAGON', 30, 'IDLE', ?, ?, ?)
        """,
        (t_offset(100), now, now)
    )

    # 12. Alerts
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_alerts (alert_id, investigation_id, alert_type, message, severity, status, source, created_at)
        VALUES ('ALT-GYRO-01', 'INV-GYRO-GHOST', 'ALIAS_MUTATION', 'Threat Actor gyroghost rebranded to @gyro_cyber with 91% stylometry similarity', 'CRITICAL', 'NEW', 'Persona Profiler', ?)
        """,
        (t_offset(200),)
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO sih_alerts (alert_id, investigation_id, alert_type, message, severity, status, source, created_at)
        VALUES ('ALT-DRAGON-01', 'INV-BLACK-DRAGON', 'ALIAS_MUTATION', 'Threat Actor blackdragon mutated to dark_dragon_x with 96% stylometry similarity & PGP key match', 'CRITICAL', 'NEW', 'Persona Profiler', ?)
        """,
        (t_offset(200),)
    )

    conn.commit()
    conn.close()
    print("[+] Successfully seeded gyroghost & blackdragon persona migration data into DB!")

if __name__ == "__main__":
    seed()
