from __future__ import annotations

import importlib
import os
import sys


def load_crawler():
    root = os.getenv(
        "CRAWLER_PATH",
        "../DarkWeb-Deanonymization",
    )

    root = os.path.abspath(root)
    src = os.path.join(root, "src")

    if src not in sys.path:
        sys.path.insert(0, src)

    return importlib.import_module("service")


def run(
    db,
    job_id,
    investigation_id,
    actor_id,
    urls,
    target=None,
    workers=3,
):
    db.update_job(
        job_id,
        status="running",
        progress=0.03,
    )

    db.event(
        job_id,
        "status",
        "Crawler started",
        0.03,
        {
            "urls": len(urls),
            "target": target,
        },
    )

    try:
        service = load_crawler()

        db.event(
            job_id,
            "status",
            "Crawler service loaded",
            0.06,
        )

        # The crawler keeps using its own internal tables.
        # Platform receives the normalized result and stores it
        # in the SIH-prefixed integration tables.
        result = service.run_crawl(
            urls,
            target_username=target,
            workers=workers,
            db=None,
        )

        if not isinstance(result, dict):
            raise RuntimeError(
                "Crawler returned an invalid result."
            )

        if result.get("error"):
            raise RuntimeError(
                str(result["error"])
            )

        crawler_session_id = result.get("session_id")

        # Preserve mapping between the SIH investigation and
        # crawler session.
        if crawler_session_id:
            db.update_investigation(
                investigation_id,
                crawler_session_id=str(
                    crawler_session_id
                ),
            )

        db.event(
            job_id,
            "collection",
            "Crawler collection completed",
            0.70,
            result.get("summary", {}),
        )

        # ========================================================
        # ACTOR / INTELLIGENCE FINDINGS
        # ========================================================

        for row in result.get(
            "actor_rows",
            [],
        ):
            if not isinstance(row, dict):
                continue

            value = (
                row.get("value")
                or row.get("username")
                or row.get("email")
            )

            if not value:
                continue

            finding_type = (
                row.get("finding_type")
                or row.get("type")
                or "other"
            )

            source = (
                row.get("source")
                or "crawler"
            )

            source_url = (
                row.get("source_url")
                or row.get("url")
            )

            confidence = row.get(
                "confidence",
                0.5,
            )

            fid = db.finding(
                investigation_id,
                finding_type,
                str(value),
                source,
                source_url,
                confidence,
                row,
                actor_id,
            )

            sid = db.source(
                source,
                source_url,
            )

            db.evidence(
                fid,
                sid,
                "crawler_extraction",
                source_url,
                row.get("context")
                or row.get("content"),
                {
                    "raw_row": row,
                },
            )

        # ========================================================
        # NETWORK / INFRASTRUCTURE FINDINGS
        # ========================================================

        for row in result.get(
            "network_rows",
            [],
        ):
            if not isinstance(row, dict):
                continue

            value = (
                row.get("ip_address")
                or row.get("domain")
                or row.get("host")
                or row.get("source_url")
            )

            if not value:
                continue

            source = (
                row.get("source")
                or "crawler"
            )

            source_url = row.get(
                "source_url"
            )

            fid = db.finding(
                investigation_id,
                "infrastructure",
                str(value),
                source,
                source_url,
                row.get("confidence", 0.5),
                row,
                actor_id,
            )

            sid = db.source(
                source,
                source_url,
            )

            db.evidence(
                fid,
                sid,
                "network_artifact",
                source_url,
                None,
                {
                    "raw_row": row,
                },
            )

        # ========================================================
        # COMPLETE
        # ========================================================

        db.update_investigation(
            investigation_id,
            status="completed",
        )

        db.update_job(
            job_id,
            status="completed",
            progress=1.0,
            result_ref=investigation_id,
        )

        db.event(
            job_id,
            "completed",
            "Investigation ready",
            1.0,
            {
                "investigation_id": investigation_id,
                "crawler_session_id": crawler_session_id,
            },
        )

        return investigation_id

    except Exception as exc:
        db.update_investigation(
            investigation_id,
            status="failed",
        )

        db.update_job(
            job_id,
            status="failed",
            progress=1.0,
            error=str(exc),
        )

        db.event(
            job_id,
            "error",
            str(exc),
            1.0,
        )

        raise
