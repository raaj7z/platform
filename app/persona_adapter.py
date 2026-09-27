"""
PRALAYX Persona Analysis Adapter

Integrates the standalone Persona repository (AI stylometry, semantic embeddings,
behavioral analysis, candidate pseudonymous continuity detection) with the PRALAYX platform.

Responsibilities:
- Call Persona REST API (or import module fallback if offline)
- Normalize stylometry and rebrand migration outputs into shared contract
- Persist findings and relationships into canonical PRALAYX database
- Provide explicitly labeled synthetic demo corpora for candidate rebrand visualization
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

# Ensure Persona module can be imported directly if needed
PERSONA_PATH = os.path.abspath(
    os.getenv("PERSONA_PATH", "../Persona")
)
if os.path.isdir(PERSONA_PATH) and PERSONA_PATH not in sys.path:
    sys.path.insert(0, PERSONA_PATH)


PERSONA_API_URL = os.getenv("PERSONA_API_URL", "http://127.0.0.1:8010")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _call_persona_api(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Try calling the live Persona FastAPI microservice over HTTP."""
    url = f"{PERSONA_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        pass
    return None


def _call_persona_module_directly(action: str, **kwargs) -> Dict[str, Any]:
    """Fallback: Import and call Persona functions in-process if microservice is offline."""
    try:
        if action == "analyze":
            from src.persona.profile_builder import build_profile
            from src.models.post import Post
            posts_objs = [Post(**p) if isinstance(p, dict) else p for p in kwargs.get("posts", [])]
            return build_profile(
                persona_id=kwargs.get("persona_id", "PERS-UNK"),
                posts=posts_objs,
                investigation_id=kwargs.get("investigation_id"),
                actor_id=kwargs.get("actor_id"),
                run_id=kwargs.get("run_id"),
                session_id=kwargs.get("session_id"),
            )
        elif action == "migration":
            from src.persona.migration import detect_migration
            from src.persona.profile_builder import build_profile
            from src.models.post import Post
            p_a = kwargs.get("persona_a", {})
            p_b = kwargs.get("persona_b", {})
            posts_a = [Post(**p) if isinstance(p, dict) else p for p in p_a.get("posts", [])]
            posts_b = [Post(**p) if isinstance(p, dict) else p for p in p_b.get("posts", [])]
            prof_a = build_profile(persona_id=p_a.get("persona_id", "A"), posts=posts_a)
            prof_b = build_profile(persona_id=p_b.get("persona_id", "B"), posts=posts_b)
            return detect_migration(prof_a, prof_b, kwargs.get("investigation_id"))
    except Exception as exc:
        return {"status": "error", "error": f"Direct module execution failed: {exc}"}
    return {"status": "error", "error": f"Unknown action {action}"}


def analyze_persona(
    persona_id: str,
    posts: List[Dict[str, Any]],
    investigation_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run stylometry and feature extraction on a post corpus."""
    payload = {
        "persona_id": persona_id,
        "posts": posts,
        "investigation_id": investigation_id,
        "actor_id": actor_id,
        "run_id": run_id,
        "session_id": session_id,
    }
    res = _call_persona_api("/analyze", payload)
    if not res:
        res = _call_persona_module_directly("analyze", **payload)
    return res


def check_pseudonymous_migration(
    persona_a_id: str,
    posts_a: List[Dict[str, Any]],
    persona_b_id: str,
    posts_b: List[Dict[str, Any]],
    investigation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Detect candidate pseudonymous continuity across rebranded or migrated profiles."""
    payload = {
        "investigation_id": investigation_id,
        "persona_a": {"persona_id": persona_a_id, "posts": posts_a},
        "persona_b": {"persona_id": persona_b_id, "posts": posts_b},
    }
    res = _call_persona_api("/migration", payload)
    if not res:
        res = _call_persona_module_directly("migration", **payload)
    return res


def get_synthetic_rebrand_demo(investigation_id: str = "INV-DEMO-2026") -> Dict[str, Any]:
    """
    Returns an explicitly labeled synthetic example showing candidate pseudonymous continuity
    between an earlier handle ('DarkViper_2024') and a migrated handle ('AetherSec_2026').

    Does NOT contain real identities or real person data.
    """
    sample_a = [
        {
            "post_id": "SYN-A1",
            "author_id": "DarkViper_2024",
            "platform": "dark_forum_v1",
            "text": "Greetings, colleagues. We are releasing our updated custom proxy chain script today! Always verify SHA256 checksums before deploying -- security first, always.",
            "timestamp": "2024-03-15T14:20:00Z",
            "source_url": "http://forum.onion/threads/10293",
        },
        {
            "post_id": "SYN-A2",
            "author_id": "DarkViper_2024",
            "platform": "dark_forum_v1",
            "text": "Please note: we NEVER request private keys or raw passwords via PM. If anyone contacts you claiming to be us, report them immediately -- stay vigilant.",
            "timestamp": "2024-04-02T09:45:00Z",
            "source_url": "http://forum.onion/threads/11054",
        }
    ]

    sample_b = [
        {
            "post_id": "SYN-B1",
            "author_id": "AetherSec_2026",
            "platform": "dark_forum_v2",
            "text": "Hello again, community. We have migrated our infrastructure to new onion endpoints! Always verify SHA256 checksums before deploying -- security first, always.",
            "timestamp": "2026-08-10T14:35:00Z",
            "source_url": "http://newforum.onion/threads/401",
        },
        {
            "post_id": "SYN-B2",
            "author_id": "AetherSec_2026",
            "platform": "dark_forum_v2",
            "text": "Reminder for all users: we NEVER request private keys or credentials via direct message. Report any suspicious impersonators immediately -- stay vigilant.",
            "timestamp": "2026-09-01T10:15:00Z",
            "source_url": "http://newforum.onion/threads/512",
        }
    ]

    migration_res = check_pseudonymous_migration(
        persona_a_id="DarkViper_2024 (Legacy Handle)",
        posts_a=sample_a,
        persona_b_id="AetherSec_2026 (Migrated Handle)",
        posts_b=sample_b,
        investigation_id=investigation_id,
    )

    return {
        "is_synthetic_demo": True,
        "label": "Synthetic Candidate Pseudonymous Continuity Demonstration",
        "disclaimer": "This is a synthetic demonstration example for testing candidate handle continuity. It does NOT represent any real person or real-world identity.",
        "sample_group_a": {
            "handle": "DarkViper_2024",
            "period": "2024 (Forum V1)",
            "sample_count": len(sample_a),
            "posts": sample_a,
        },
        "sample_group_b": {
            "handle": "AetherSec_2026",
            "period": "2026 (Forum V2)",
            "sample_count": len(sample_b),
            "posts": sample_b,
        },
        "analysis_result": migration_res,
    }


def persist_persona_analysis(
    db: Any,
    investigation_id: str,
    persona_result: Dict[str, Any],
    run_id: Optional[str] = None,
) -> Dict[str, int]:
    """
    Persist Persona stylometry findings and relationship links into the PRALAYX database.
    """
    counts = {"findings": 0, "relationships": 0}
    now = _utc_now()

    # Extract profiles or migration details
    profiles = persona_result.get("profiles", [])
    if not profiles and "profile" in persona_result:
        profiles = [persona_result["profile"]]

    for prof in profiles:
        pid = prof.get("persona_id", "UNKNOWN")
        sty = prof.get("stylometry", {})
        usable = prof.get("usable", True)

        # Record finding for stylometry profile
        fid = f"FIND-STY-{uuid.uuid4().hex[:8]}"
        try:
            db.conn.execute(
                """
                INSERT INTO sih_findings
                (finding_id, investigation_id, run_id, finding_type, value, source, source_url, confidence, metadata, first_seen, last_seen)
                VALUES (?, ?, ?, 'stylometry_profile', ?, 'Persona Engine', 'http://127.0.0.1:8010/analyze', ?, ?, ?, ?)
                """,
                (
                    fid,
                    investigation_id,
                    run_id,
                    f"Stylometric Profile: {pid}",
                    0.80 if usable else 0.40,
                    json.dumps(sty),
                    now,
                    now,
                )
            )
            counts["findings"] += 1
        except Exception:
            pass

    # Record migration / continuity candidate relationships
    migration = persona_result.get("migration", {})
    if not migration and "migration_hypothesis" in persona_result:
        migration = persona_result["migration_hypothesis"]

    if migration:
        handle_a = migration.get("persona_a_id", "Persona_A")
        handle_b = migration.get("persona_b_id", "Persona_B")
        score = migration.get("similarity_score", migration.get("fusion_score", 0.75))
        basis = migration.get("explanation", "High stylometric feature overlap and structural similarity")

        rel_id = f"REL-CONT-{uuid.uuid4().hex[:8]}"
        try:
            db.conn.execute(
                """
                INSERT INTO sih_relationships
                (relationship_id, investigation_id, run_id, from_type, from_value, relationship_type, to_type, to_value, confidence, observed_at)
                VALUES (?, ?, ?, 'handle', ?, 'candidate_pseudonymous_continuity', 'handle', ?, ?, ?)
                """,
                (
                    rel_id,
                    investigation_id,
                    run_id,
                    handle_a,
                    handle_b,
                    float(score),
                    now,
                )
            )
            counts["relationships"] += 1
        except Exception:
            pass

    db.conn.commit()
    return counts
