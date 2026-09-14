from __future__ import annotations

import importlib
import os
import sys
import traceback


# ============================================================
# OSINT ENGINE LOADER
# ============================================================

def load_engine():
    """
    Load the separate osint-engine repository.

    The platform does not duplicate the OSINT engine.
    It imports the existing engine and passes normalized
    investigation data to it.
    """

    root = os.getenv(
        "OSINT_ENGINE_PATH",
        "../osint-engine",
    )

    root = os.path.abspath(root)

    if not os.path.isdir(root):
        raise RuntimeError(
            f"OSINT engine directory not found: {root}"
        )

    if root not in sys.path:
        sys.path.insert(0, root)

    engine = importlib.import_module(
        "src.engine"
    )

    models = importlib.import_module(
        "src.models"
    )

    return engine, models


# ============================================================
# EVENT HELPERS
# ============================================================

def _event(
    db,
    job_id,
    event_type,
    message,
    progress=None,
    payload=None,
):
    try:
        db.event(
            job_id,
            event_type,
            message,
            progress,
            payload,
        )
    except Exception:
        pass


def _status(
    db,
    job_id,
    message,
    progress=None,
    payload=None,
):
    _event(
        db,
        job_id,
        "status",
        message,
        progress,
        payload,
    )


# ============================================================
# NORMALIZE IDENTIFIERS
# ============================================================

def _make_identifier(
    models,
    item,
):
    """
    Convert a crawler/platform finding into the OSINT engine's
    Identifier model.
    """

    if not isinstance(item, dict):
        return None

    value = item.get("value")

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    identifier_type = (
        item.get("type")
        or item.get("finding_type")
        or "other"
    )

    source = (
        item.get("source")
        or "dark-crawler"
    )

    source_url = item.get(
        "source_url"
    )

    confidence = item.get(
        "confidence",
        0.5,
    )

    try:
        confidence = float(
            confidence
        )
    except Exception:
        confidence = 0.5

    confidence = max(
        0.0,
        min(1.0, confidence),
    )

    return models.Identifier(
        type=identifier_type,
        value=value,
        source=source,
        source_url=source_url,
        confidence=confidence,
    )


# ============================================================
# SAVE ENGINE FINDING
# ============================================================

def _save_finding(
    db,
    finding,
    actor_id,
):
    """
    Store one OSINT-engine Finding in the platform database.
    """

    finding_type = (
        getattr(
            finding,
            "finding_type",
            None,
        )
        or "other"
    )

    value = getattr(
        finding,
        "value",
        None,
    )

    if value is None:
        return None

    source = (
        getattr(
            finding,
            "source",
            None,
        )
        or "osint-engine"
    )

    source_url = getattr(
        finding,
        "source_url",
        None,
    )

    confidence = getattr(
        finding,
        "confidence",
        0.5,
    )

    try:
        confidence = float(
            confidence
        )
    except Exception:
        confidence = 0.5

    metadata = getattr(
        finding,
        "metadata",
        None,
    ) or {}

    fid = db.finding(
        finding.investigation_id,
        finding_type,
        str(value),
        source,
        source_url,
        confidence,
        metadata,
        actor_id,
    )

    # --------------------------------------------------------
    # Preserve source/evidence information.
    # --------------------------------------------------------

    try:

        source_id = db.source(
            source,
            source_url,
        )

        evidence_items = (
            getattr(
                finding,
                "evidence",
                None,
            )
            or []
        )

        for evidence in evidence_items:

            evidence_source = (
                getattr(
                    evidence,
                    "source",
                    None,
                )
                or source
            )

            evidence_url = (
                getattr(
                    evidence,
                    "source_url",
                    None,
                )
                or source_url
            )

            title = getattr(
                evidence,
                "title",
                None,
            )

            excerpt = getattr(
                evidence,
                "excerpt",
                None,
            )

            evidence_metadata = (
                getattr(
                    evidence,
                    "metadata",
                    None,
                )
                or {}
            )

            db.evidence(
                fid,
                source_id,
                "osint",
                evidence_url,
                excerpt
                or title,
                evidence_metadata,
            )

    except Exception:
        # Evidence storage should not cause the entire
        # OSINT investigation to fail.
        pass

    return fid


# ============================================================
# MANUAL OSINT
# ============================================================

def run_osint(
    db,
    job_id,
    iid,
    actor_id,
    target,
    target_type="other",
):
    """
    Run the OSINT engine for one manually supplied identifier.
    """

    db.update_job(
        job_id,
        status="running",
        progress=0.02,
    )

    _status(
        db,
        job_id,
        "OSINT engine starting...",
        0.02,
        {
            "target": target,
            "target_type": target_type,
        },
    )

    try:

        engine, models = load_engine()

        _status(
            db,
            job_id,
            "OSINT engine loaded",
            0.08,
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
                identifiers=[
                    identifier
                ],
            )
        )

        _status(
            db,
            job_id,
            "Running OSINT scanners and providers...",
            0.12,
        )

        result = (
            engine.OSINTEngine()
            .run(
                investigation_input
            )
        )

        findings = (
            getattr(
                result,
                "findings",
                None,
            )
            or []
        )

        _status(
            db,
            job_id,
            f"OSINT engine returned {len(findings)} findings",
            0.80,
        )

        saved = 0

        for finding in findings:

            try:

                if _save_finding(
                    db,
                    finding,
                    actor_id,
                ):
                    saved += 1

            except Exception as exc:

                _event(
                    db,
                    job_id,
                    "warning",
                    f"Could not save OSINT finding: {exc}",
                    0.85,
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

        _event(
            db,
            job_id,
            "completed",
            "OSINT investigation completed successfully",
            1.0,
            {
                "investigation_id": iid,
                "returned_findings":
                    len(findings),
                "saved_findings":
                    saved,
            },
        )

        return iid

    except Exception as exc:

        error_message = (
            f"{type(exc).__name__}: {exc}"
        )

        _event(
            db,
            job_id,
            "error",
            error_message,
            1.0,
            {
                "traceback":
                    traceback.format_exc(),
            },
        )

        try:
            db.update_investigation(
                iid,
                status="failed",
            )
        except Exception:
            pass

        try:
            db.update_job(
                job_id,
                status="failed",
                progress=1.0,
                error=error_message,
            )
        except Exception:
            pass

        raise


# ============================================================
# CRAWLER → OSINT
# ============================================================

def run_osint_from_crawl(
    db,
    job_id,
    iid,
    actor_id,
    identifiers,
):
    """
    Take identifiers extracted by the crawler and send them
    together into the existing OSINT engine.

    Example:

        username
        email
        domain
        URL
        IP
        PGP
        crypto

    are all passed as one InvestigationInput.
    """

    db.update_job(
        job_id,
        status="running",
        progress=0.02,
    )

    _status(
        db,
        job_id,
        "Starting crawler → OSINT handoff...",
        0.02,
        {
            "investigation_id": iid,
            "identifier_count":
                len(identifiers or []),
        },
    )

    try:

        # ====================================================
        # LOAD ENGINE
        # ====================================================

        engine, models = load_engine()

        _status(
            db,
            job_id,
            "OSINT engine loaded",
            0.08,
        )

        # ====================================================
        # CONVERT IDENTIFIERS
        # ====================================================

        engine_identifiers = []

        seen = set()

        for item in identifiers or []:

            identifier = _make_identifier(
                models,
                item,
            )

            if identifier is None:
                continue

            key = (
                identifier.type,
                identifier.value.lower(),
            )

            if key in seen:
                continue

            seen.add(key)

            engine_identifiers.append(
                identifier
            )

        if not engine_identifiers:
            raise RuntimeError(
                "Crawler report contained no valid "
                "OSINT identifiers."
            )

        _status(
            db,
            job_id,
            (
                f"Prepared "
                f"{len(engine_identifiers)} "
                f"unique identifiers for OSINT"
            ),
            0.15,
            {
                "identifiers": [
                    {
                        "type":
                            x.type,
                        "value":
                            x.value,
                        "source":
                            x.source,
                    }
                    for x in engine_identifiers
                ],
            },
        )

        # ====================================================
        # CREATE INVESTIGATION INPUT
        # ====================================================

        investigation_input = (
            models.InvestigationInput(
                investigation_id=iid,
                actor_id=actor_id,
                identifiers=
                    engine_identifiers,
                notes=(
                    "Identifiers imported from "
                    "DarkWeb-Deanonymization "
                    "crawler."
                ),
            )
        )

        # ====================================================
        # RUN ENGINE
        # ====================================================

        _status(
            db,
            job_id,
            "Running OSINT scanners and providers...",
            0.20,
        )

        result = (
            engine.OSINTEngine()
            .run(
                investigation_input
            )
        )

        findings = (
            getattr(
                result,
                "findings",
                None,
            )
            or []
        )

        engine_errors = (
            getattr(
                result,
                "errors",
                None,
            )
            or []
        )

        # ====================================================
        # ENGINE ERRORS
        # ====================================================

        for error in engine_errors:

            _event(
                db,
                job_id,
                "warning",
                str(error),
                0.75,
            )

        _status(
            db,
            job_id,
            (
                f"OSINT engine completed with "
                f"{len(findings)} findings"
            ),
            0.78,
            {
                "finding_count":
                    len(findings),
                "errors":
                    engine_errors,
            },
        )

        # ====================================================
        # SAVE FINDINGS
        # ====================================================

        saved = 0

        for index, finding in enumerate(
            findings,
            start=1,
        ):

            try:

                fid = _save_finding(
                    db,
                    finding,
                    actor_id,
                )

                if fid:
                    saved += 1

                    _event(
                        db,
                        job_id,
                        "finding",
                        (
                            f"OSINT finding "
                            f"{index}/{len(findings)}: "
                            f"{finding.value}"
                        ),
                        min(
                            0.95,
                            0.80
                            + (
                                0.15
                                * index
                                / max(
                                    1,
                                    len(findings),
                                )
                            ),
                        ),
                        {
                            "finding_id":
                                fid,
                            "type":
                                getattr(
                                    finding,
                                    "finding_type",
                                    "other",
                                ),
                            "value":
                                str(
                                    getattr(
                                        finding,
                                        "value",
                                        "",
                                    )
                                ),
                            "source":
                                getattr(
                                    finding,
                                    "source",
                                    "osint-engine",
                                ),
                            "confidence":
                                getattr(
                                    finding,
                                    "confidence",
                                    0.5,
                                ),
                        },
                    )

            except Exception as exc:

                _event(
                    db,
                    job_id,
                    "warning",
                    (
                        "Could not save OSINT "
                        f"finding: {exc}"
                    ),
                    0.85,
                )

        # ====================================================
        # COMPLETE INVESTIGATION
        # ====================================================

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

        _event(
            db,
            job_id,
            "completed",
            "Crawler findings successfully processed by OSINT engine",
            1.0,
            {
                "investigation_id":
                    iid,
                "input_identifiers":
                    len(engine_identifiers),
                "engine_findings":
                    len(findings),
                "saved_findings":
                    saved,
            },
        )

        return iid

    # ========================================================
    # FAILURE
    # ========================================================

    except Exception as exc:

        error_message = (
            f"{type(exc).__name__}: {exc}"
        )

        _event(
            db,
            job_id,
            "error",
            error_message,
            1.0,
            {
                "traceback":
                    traceback.format_exc(),
            },
        )

        try:
            db.update_investigation(
                iid,
                status="failed",
            )
        except Exception:
            pass

        try:
            db.update_job(
                job_id,
                status="failed",
                progress=1.0,
                error=error_message,
            )
        except Exception:
            pass

        raise
