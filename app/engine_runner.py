

from __future__ import annotations

import importlib
import os
import sys
import traceback
from pathlib import Path
from typing import Any


# ============================================================
# ENGINE LOADER
# ============================================================

def load_engine():
    """
    Load the real osint-engine repository.

    The platform does not copy or duplicate the engine.
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
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.5,
) -> float:
    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default

    # Backward compatibility for percentage-style
    # confidence values such as 80 or 95.
    if value > 1.0:
        value /= 100.0

    return max(
        0.0,
        min(1.0, value),
    )


def _text(value: Any) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    return value if value else None


def _event(
    db,
    job_id: str,
    event_type: str,
    message: str,
    progress: float | None = None,
    payload: dict | None = None,
    run_id: str | None = None,
):
    """
    Persist a terminal/audit event.

    Terminal failure must never hide the actual OSINT
    engine result.
    """

    try:
        return db.event(
            job_id=job_id,
            event_type=event_type,
            message=message,
            progress=progress,
            payload=payload,
            run_id=run_id,
        )
    except Exception:
        return None


def _status(
    db,
    job_id: str,
    message: str,
    progress: float | None = None,
    payload: dict | None = None,
    run_id: str | None = None,
):
    return _event(
        db,
        job_id,
        "status",
        message,
        progress,
        payload,
        run_id,
    )


def _finding_value(finding) -> str | None:
    value = getattr(
        finding,
        "value",
        None,
    )

    if value is None:
        return None

    value = str(value).strip()

    return value if value else None


# ============================================================
# SOURCE / EVIDENCE PERSISTENCE
# ============================================================

def _persist_finding(
    db,
    finding,
    investigation_id: str,
    run_id: str,
    actor_id: str | None,
):
    """
    Persist one OSINT Finding into the PRALAYX evidence model.

    A finding is an observation, not automatic attribution.
    """

    value = _finding_value(
        finding
    )

    if value is None:
        return None

    finding_type = (
        getattr(
            finding,
            "finding_type",
            None,
        )
        or "other"
    )

    source = (
        getattr(
            finding,
            "source",
            None,
        )
        or "osint-engine"
    )

    source_url = _text(
        getattr(
            finding,
            "source_url",
            None,
        )
    )

    confidence = _safe_float(
        getattr(
            finding,
            "confidence",
            0.5,
        )
    )

    metadata = (
        getattr(
            finding,
            "metadata",
            None,
        )
        or {}
    )

    # --------------------------------------------------------
    # Main finding
    # --------------------------------------------------------

    finding_id = db.add_finding(
        investigation_id=investigation_id,
        finding_type=str(
            finding_type
        ),
        value=value,
        source=str(source),
        source_url=source_url,
        confidence=confidence,
        metadata=metadata,
        actor_id=actor_id,
        run_id=run_id,
    )

    # --------------------------------------------------------
    # Source registry
    # --------------------------------------------------------

    source_id = db.get_or_create_source(
        name=str(source),
        url=source_url,
        source_type="osint-provider",
    )

    # --------------------------------------------------------
    # Entity sighting
    # --------------------------------------------------------

    db.add_entity_sighting(
        investigation_id=investigation_id,
        entity_type=str(
            finding_type
        ),
        normalized_value=value.lower(),
        raw_value=value,
        source_id=source_id,
        source_url=source_url,
        actor_id=actor_id,
        run_id=run_id,
        confidence=confidence,
        metadata=metadata,
    )

    # --------------------------------------------------------
    # Generic observation
    # --------------------------------------------------------

    db.add_observation(
        investigation_id=investigation_id,
        entity_type=str(
            finding_type
        ),
        entity_value=value,
        actor_id=actor_id,
        source_id=source_id,
        confidence=confidence,
        metadata=metadata,
        run_id=run_id,
    )

    # --------------------------------------------------------
    # Evidence
    # --------------------------------------------------------

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
            _text(
                getattr(
                    evidence,
                    "source_url",
                    None,
                )
            )
            or source_url
        )

        title = _text(
            getattr(
                evidence,
                "title",
                None,
            )
        )

        excerpt = _text(
            getattr(
                evidence,
                "excerpt",
                None,
            )
        )

        evidence_metadata = (
            getattr(
                evidence,
                "metadata",
                None,
            )
            or {}
        )

        evidence_source_id = (
            db.get_or_create_source(
                name=str(
                    evidence_source
                ),
                url=evidence_url,
                source_type="osint-evidence",
            )
        )

        db.add_evidence(
            finding_id=finding_id,
            evidence_type="osint",
            source_url=evidence_url,
            excerpt=(
                excerpt
                or title
            ),
            metadata=evidence_metadata,
            source_id=evidence_source_id,
        )

    return finding_id


# ============================================================
# RAW RESULT SNAPSHOT
# ============================================================

def _serialize_finding(
    finding,
) -> dict:
    """
    Convert a Pydantic Finding into a JSON-safe dictionary.
    """

    if hasattr(
        finding,
        "model_dump",
    ):
        return finding.model_dump(
            mode="json"
        )

    if hasattr(
        finding,
        "dict",
    ):
        return finding.dict()

    return {
        "finding_type": getattr(
            finding,
            "finding_type",
            "other",
        ),
        "value": getattr(
            finding,
            "value",
            None,
        ),
        "source": getattr(
            finding,
            "source",
            None,
        ),
        "source_url": getattr(
            finding,
            "source_url",
            None,
        ),
        "confidence": getattr(
            finding,
            "confidence",
            0.5,
        ),
        "metadata": getattr(
            finding,
            "metadata",
            {},
        ),
    }


def _serialize_result(
    result,
) -> dict:
    """
    Preserve the complete OSINT engine result before
    normalization into PRALAYX findings.
    """

    if hasattr(
        result,
        "model_dump",
    ):
        return result.model_dump(
            mode="json"
        )

    findings = (
        getattr(
            result,
            "findings",
            None,
        )
        or []
    )

    errors = (
        getattr(
            result,
            "errors",
            None,
        )
        or []
    )

    return {
        "investigation_id":
            getattr(
                result,
                "investigation_id",
                None,
            ),
        "actor_id":
            getattr(
                result,
                "actor_id",
                None,
            ),
        "findings": [
            _serialize_finding(
                finding
            )
            for finding in findings
        ],
        "errors": list(errors),
    }


# ============================================================
# COMMON ENGINE EXECUTION
# ============================================================

def _execute_engine(
    db,
    job_id: str,
    investigation_id: str,
    actor_id: str | None,
    investigation_input,
    session_id: str,
    run_id: str,
):
    """
    Execute the actual OSINT engine and persist its complete result.
    """

    _status(
        db,
        job_id,
        "OSINT engine starting...",
        0.05,
        {
            "investigation_id":
                investigation_id,
            "session_id":
                session_id,
            "run_id":
                run_id,
        },
        run_id,
    )

    # --------------------------------------------------------
    # Load engine
    # --------------------------------------------------------

    engine_module, _ = load_engine()

    _status(
        db,
        job_id,
        "OSINT engine loaded",
        0.10,
        run_id=run_id,
    )

    engine = (
        engine_module.OSINTEngine()
    )

    # --------------------------------------------------------
    # Report which components actually loaded.
    # --------------------------------------------------------

    scanner_count = len(
        getattr(
            engine,
            "scanners",
            [],
        )
    )

    provider_count = len(
        getattr(
            engine,
            "providers",
            [],
        )
    )

    load_errors = list(
        getattr(
            engine,
            "load_errors",
            [],
        )
        or []
    )

    _status(
        db,
        job_id,
        (
            f"OSINT engine ready — "
            f"{scanner_count} scanners, "
            f"{provider_count} providers"
        ),
        0.15,
        {
            "scanner_count":
                scanner_count,
            "provider_count":
                provider_count,
            "load_errors":
                load_errors,
        },
        run_id,
    )

    # --------------------------------------------------------
    # Explicit component warnings
    # --------------------------------------------------------

    for error in load_errors:
        _event(
            db,
            job_id,
            "component_warning",
            str(error),
            0.16,
            run_id=run_id,
        )

    # --------------------------------------------------------
    # Execute engine
    # --------------------------------------------------------

    _status(
        db,
        job_id,
        "Running OSINT scanners and providers...",
        0.20,
        run_id=run_id,
    )

    result = engine.run(
        investigation_input
    )

    # --------------------------------------------------------
    # Preserve raw result BEFORE filtering/normalization.
    # --------------------------------------------------------

    raw_result = _serialize_result(
        result
    )

    db.add_raw_snapshot(
        investigation_id=investigation_id,
        source="osint-engine",
        payload=raw_result,
        session_id=session_id,
        run_id=run_id,
        snapshot_type="osint_result",
    )

    findings = (
        getattr(
            result,
            "findings",
            None,
        )
        or []
    )

    errors = (
        getattr(
            result,
            "errors",
            None,
        )
        or []
    )

    # --------------------------------------------------------
    # Truthful provider/scanner errors
    # --------------------------------------------------------

    for error in errors:
        _event(
            db,
            job_id,
            "warning",
            str(error),
            0.75,
            run_id=run_id,
        )

    _status(
        db,
        job_id,
        (
            f"OSINT engine returned "
            f"{len(findings)} findings"
        ),
        0.78,
        {
            "finding_count":
                len(findings),
            "error_count":
                len(errors),
        },
        run_id,
    )

    # --------------------------------------------------------
    # Persist findings
    # --------------------------------------------------------

    saved = 0

    for index, finding in enumerate(
        findings,
        start=1,
    ):
        try:
            finding_id = _persist_finding(
                db=db,
                finding=finding,
                investigation_id=investigation_id,
                run_id=run_id,
                actor_id=actor_id,
            )

            if finding_id:
                saved += 1

                finding_type = (
                    getattr(
                        finding,
                        "finding_type",
                        "other",
                    )
                )

                value = _finding_value(
                    finding
                )

                source = (
                    getattr(
                        finding,
                        "source",
                        "osint-engine",
                    )
                    or "osint-engine"
                )

                confidence = _safe_float(
                    getattr(
                        finding,
                        "confidence",
                        0.5,
                    )
                )

                progress = (
                    0.80
                    + (
                        0.15
                        * index
                        / max(
                            1,
                            len(findings),
                        )
                    )
                )

                _event(
                    db,
                    job_id,
                    "finding",
                    (
                        f"{finding_type}: "
                        f"{value or 'unknown'}"
                    ),
                    min(
                        0.95,
                        progress,
                    ),
                    {
                        "finding_id":
                            finding_id,
                        "finding_type":
                            finding_type,
                        "value":
                            value,
                        "source":
                            source,
                        "confidence":
                            confidence,
                    },
                    run_id,
                )

        except Exception as exc:
            _event(
                db,
                job_id,
                "warning",
                (
                    "Could not persist OSINT "
                    f"finding: {exc}"
                ),
                0.85,
                run_id=run_id,
            )

    # --------------------------------------------------------
    # Final state
    # --------------------------------------------------------

    if saved == 0 and not errors:
        final_status = "NO_RESULTS"
        final_message = (
            "OSINT completed but returned "
            "no findings."
        )

    elif saved == 0 and errors:
        final_status = "ERROR"
        final_message = (
            "OSINT execution completed with "
            "errors and no persisted findings."
        )

    else:
        final_status = "COMPLETED"
        final_message = (
            "OSINT investigation completed."
        )

    db.update_session(
        session_id,
        status=final_status,
        metadata={
            "finding_count":
                len(findings),
            "saved_findings":
                saved,
            "error_count":
                len(errors),
            "scanner_count":
                scanner_count,
            "provider_count":
                provider_count,
        },
    )

    db.update_run(
        run_id,
        status=final_status,
        progress=1.0,
        result_ref=investigation_id,
    )

    db.update_job(
        job_id,
        status=final_status,
        progress=1.0,
        result_ref=run_id,
    )

    db.update_investigation(
        investigation_id,
        status=(
            "completed"
            if final_status
            in (
                "COMPLETED",
                "NO_RESULTS",
            )
            else "failed"
        ),
    )

    db.add_timeline_event(
        investigation_id=investigation_id,
        event_type="osint_completed",
        message=final_message,
        session_id=session_id,
        run_id=run_id,
        actor_id=actor_id,
        payload={
            "status":
                final_status,
            "engine_findings":
                len(findings),
            "saved_findings":
                saved,
            "errors":
                errors,
        },
    )

    _event(
        db,
        job_id,
        "completed",
        final_message,
        1.0,
        {
            "status":
                final_status,
            "investigation_id":
                investigation_id,
            "session_id":
                session_id,
            "run_id":
                run_id,
            "engine_findings":
                len(findings),
            "saved_findings":
                saved,
            "errors":
                errors,
        },
        run_id,
    )

    return {
        "investigation_id":
            investigation_id,
        "session_id":
            session_id,
        "run_id":
            run_id,
        "status":
            final_status,
        "findings":
            len(findings),
        "saved_findings":
            saved,
        "errors":
            errors,
    }


# ============================================================
# MANUAL OSINT
# ============================================================

def run_osint(
    db,
    job_id: str,
    iid: str,
    actor_id: str | None,
    target: str,
    target_type: str = "other",
):
    """
    Run OSINT against one manually supplied target.
    """

    session_id = db.create_session(
        investigation_id=iid,
        session_type="osint",
        actor_id=actor_id,
        metadata={
            "input_mode": "manual",
            "target": target,
            "target_type": target_type,
        },
    )

    run_id = db.create_run(
        investigation_id=iid,
        run_type="osint",
        session_id=session_id,
        module_id="osint-engine",
        actor_id=actor_id,
        payload={
            "input_mode": "manual",
            "target": target,
            "target_type": target_type,
        },
    )

    try:
        _, models = load_engine()

        identifier = models.Identifier(
            type=target_type,
            value=target,
            source="manual",
            confidence=1.0,
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

        return _execute_engine(
            db=db,
            job_id=job_id,
            investigation_id=iid,
            actor_id=actor_id,
            investigation_input=
                investigation_input,
            session_id=session_id,
            run_id=run_id,
        )

    except Exception as exc:
        _handle_failure(
            db,
            job_id,
            iid,
            actor_id,
            session_id,
            run_id,
            exc,
        )
        raise


# ============================================================
# CRAWLER → OSINT
# ============================================================

def run_osint_from_crawl(
    db,
    job_id: str,
    iid: str,
    actor_id: str | None,
    identifiers: list[dict],
):
    """
    Run the OSINT engine using identifiers extracted from
    a crawler investigation.
    """

    session_id = db.create_session(
        investigation_id=iid,
        session_type="osint_from_crawl",
        actor_id=actor_id,
        metadata={
            "input_mode": "crawler",
            "identifier_count":
                len(identifiers or []),
        },
    )

    run_id = db.create_run(
        investigation_id=iid,
        run_type="osint_from_crawler",
        session_id=session_id,
        module_id="osint-engine",
        actor_id=actor_id,
        payload={
            "input_mode": "crawler",
            "identifier_count":
                len(identifiers or []),
        },
    )

    try:
        _, models = load_engine()

        engine_identifiers = []
        seen = set()

        for item in identifiers or []:

            if not isinstance(
                item,
                dict,
            ):
                continue

            value = _text(
                item.get("value")
            )

            if not value:
                continue

            identifier_type = (
                item.get("type")
                or item.get("finding_type")
                or "other"
            )

            key = (
                str(
                    identifier_type
                ).lower(),
                value.lower(),
            )

            if key in seen:
                continue

            seen.add(key)

            engine_identifiers.append(
                models.Identifier(
                    type=identifier_type,
                    value=value,
                    source=(
                        item.get(
                            "source"
                        )
                        or "darkweb-crawler"
                    ),
                    source_url=item.get(
                        "source_url"
                    ),
                    confidence=_safe_float(
                        item.get(
                            "confidence"
                        ),
                        0.5,
                    ),
                )
            )

        if not engine_identifiers:
            raise RuntimeError(
                "No valid OSINT identifiers "
                "were supplied by the crawler."
            )

        _status(
            db,
            job_id,
            (
                f"Prepared "
                f"{len(engine_identifiers)} "
                "unique crawler identifiers"
            ),
            0.15,
            {
                "identifiers": [
                    {
                        "type":
                            item.type,
                        "value":
                            item.value,
                        "source":
                            item.source,
                    }
                    for item in engine_identifiers
                ]
            },
            run_id,
        )

        investigation_input = (
            models.InvestigationInput(
                investigation_id=iid,
                actor_id=actor_id,
                identifiers=
                    engine_identifiers,
                notes=(
                    "Input imported from "
                    "DarkWeb-Deanonymization "
                    "crawler."
                ),
            )
        )

        return _execute_engine(
            db=db,
            job_id=job_id,
            investigation_id=iid,
            actor_id=actor_id,
            investigation_input=
                investigation_input,
            session_id=session_id,
            run_id=run_id,
        )

    except Exception as exc:
        _handle_failure(
            db,
            job_id,
            iid,
            actor_id,
            session_id,
            run_id,
            exc,
        )
        raise


# ============================================================
# FAILURE HANDLING
# ============================================================

def _handle_failure(
    db,
    job_id: str,
    investigation_id: str,
    actor_id: str | None,
    session_id: str,
    run_id: str,
    exc: Exception,
):
    """
    Persist a truthful failure state.

    Missing API keys, provider errors, import errors and
    unexpected exceptions must not become NO_RESULTS.
    """

    error_message = (
        f"{type(exc).__name__}: {exc}"
    )

    trace = traceback.format_exc()

    _event(
        db,
        job_id,
        "error",
        error_message,
        1.0,
        {
            "traceback": trace,
        },
        run_id,
    )

    try:
        db.add_raw_snapshot(
            investigation_id=
                investigation_id,
            source="osint-engine",
            payload={
                "error":
                    error_message,
                "traceback":
                    trace,
            },
            session_id=session_id,
            run_id=run_id,
            snapshot_type="osint_error",
        )
    except Exception:
        pass

    try:
        db.update_session(
            session_id,
            status="ERROR",
            metadata={
                "error":
                    error_message,
            },
        )
    except Exception:
        pass

    try:
        db.update_run(
            run_id,
            status="ERROR",
            progress=1.0,
            error=error_message,
        )
    except Exception:
        pass

    try:
        db.update_job(
            job_id,
            status="ERROR",
            progress=1.0,
            error=error_message,
        )
    except Exception:
        pass

    try:
        db.update_investigation(
            investigation_id,
            status="failed",
        )
    except Exception:
        pass

    try:
        db.add_timeline_event(
            investigation_id=
                investigation_id,
            event_type="osint_failed",
            message=error_message,
            session_id=session_id,
            run_id=run_id,
            actor_id=actor_id,
            payload={
                "traceback":
                    trace,
            },
        )
    except Exception:
        pass
