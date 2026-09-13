from __future__ import annotations

import importlib
import os
import sys


def load_engine():
    root = os.getenv(
        "OSINT_ENGINE_PATH",
        "../osint-engine",
    )

    root = os.path.abspath(root)

    if root not in sys.path:
        sys.path.insert(0, root)

    engine = importlib.import_module(
        "src.engine"
    )

    models = importlib.import_module(
        "src.models"
    )

    return engine, models


def run_osint(
    db,
    job_id,
    iid,
    actor_id,
    target,
    target_type="other",
):
    db.update_job(
        job_id,
        status="running",
        progress=0.05,
    )

    db.event(
        job_id,
        "status",
        "OSINT engine started",
        0.05,
        {
            "target": target,
            "target_type": target_type,
        },
    )

    try:
        engine, models = load_engine()

        db.event(
            job_id,
            "status",
            "OSINT engine loaded",
            0.10,
        )

        identifier = models.Identifier(
            type=target_type,
            value=target,
            source="manual",
        )

        investigation_input = (
            models.InvestigationInput(
                investigation_id=iid,
                actor_id=actor_id,
                identifiers=[identifier],
            )
        )

        result = engine.OSINTEngine().run(
            investigation_input
        )

        total = len(result.findings)

        for index, finding in enumerate(
            result.findings,
            start=1,
        ):
            progress = 0.10

            if total:
                progress = 0.10 + (
                    0.75 * index / total
                )

            db.event(
                job_id,
                "finding",
                "OSINT finding collected",
                progress,
                {
                    "finding_type": finding.finding_type,
                    "value": finding.value,
                },
            )

            fid = db.finding(
                iid,
                finding.finding_type,
                finding.value,
                finding.source,
                finding.source_url,
                finding.confidence,
                finding.metadata,
                actor_id,
            )

            sid = db.source(
                finding.source,
                finding.source_url,
            )

            for evidence in (
                finding.evidence or []
            ):
                db.evidence(
                    fid,
                    sid,
                    "osint_evidence",
                    evidence.source_url,
                    evidence.excerpt,
                    evidence.metadata,
                )

        db.update_investigation(
            iid,
            status="completed",
        )

        db.update_job(
            job_id,
            status="completed",
            progress=1.0,
            result_ref=iid,
        )

        db.event(
            job_id,
            "completed",
            "OSINT analysis completed",
            1.0,
            {
                "investigation_id": iid,
                "findings": total,
            },
        )

        return iid

    except Exception as exc:
        db.update_investigation(
            iid,
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
