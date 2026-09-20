

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Callable, Iterable, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HIGH_CONFIDENCE_THRESHOLD = 0.80

PLATFORM_TYPES = {
    "username",
    "forum_profile",
    "forum",
    "marketplace",
    "profile",
    "social_profile",
}

WALLET_TYPES = {
    "crypto",
    "wallet",
    "crypto_wallet",
}

ALIAS_TYPES = {
    "username",
    "alias",
    "handle",
    "nickname",
}

POST_TYPES = {
    "post",
    "forum_post",
    "message",
    "content",
}


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _finding_key(finding: dict[str, Any]) -> tuple:
    """
    Stable identity for a finding.

    Source is included because the same identifier appearing on two
    independent sources should remain distinguishable.
    """
    return (
        _normalize(finding.get("finding_type")),
        _normalize(
            finding.get("normalized_value")
            or finding.get("value")
            or finding.get("identifier")
        ),
        _normalize(
            finding.get("source")
            or finding.get("source_url")
        ),
    )


def _value(finding: dict[str, Any]) -> str:
    return str(
        finding.get("normalized_value")
        or finding.get("value")
        or finding.get("identifier")
        or ""
    ).strip()


def _finding_type(finding: dict[str, Any]) -> str:
    return _normalize(
        finding.get("finding_type")
        or finding.get("entity_type")
        or finding.get("type")
    )


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def diff(
    old: Iterable[dict[str, Any]],
    current: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare two finding collections.

    Returned categories are deliberately explicit so the dashboard can show
    exactly what changed rather than reducing everything to "new findings".
    """
    old = list(old or [])
    current = list(current or [])

    old_map = {
        _finding_key(item): item
        for item in old
    }

    current_map = {
        _finding_key(item): item
        for item in current
    }

    added = [
        value
        for key, value in current_map.items()
        if key not in old_map
    ]

    removed = [
        value
        for key, value in old_map.items()
        if key not in current_map
    ]

    changed: list[dict[str, Any]] = []

    for key, new_value in current_map.items():
        old_value = old_map.get(key)

        if old_value is None:
            continue

        if _materially_changed(old_value, new_value):
            changed.append(
                {
                    "before": old_value,
                    "after": new_value,
                }
            )

    new_platforms = [
        item
        for item in added
        if _finding_type(item) in PLATFORM_TYPES
    ]

    new_wallets = [
        item
        for item in added
        if _finding_type(item) in WALLET_TYPES
    ]

    new_aliases = [
        item
        for item in added
        if _finding_type(item) in ALIAS_TYPES
    ]

    new_posts = [
        item
        for item in added
        if _finding_type(item) in POST_TYPES
        or _looks_like_post(item)
    ]

    high_confidence = [
        item
        for item in added
        if _safe_float(item.get("confidence")) >= HIGH_CONFIDENCE_THRESHOLD
    ]

    profile_changes = [
        item
        for item in changed
        if _is_profile_change(
            item["before"],
            item["after"],
        )
    ]

    return {
        "added": added,
        "removed": removed,
        "changed": changed,

        "new_platforms": new_platforms,
        "new_posts": new_posts,
        "new_wallets": new_wallets,
        "new_aliases": new_aliases,
        "profile_changes": profile_changes,

        "high_confidence": high_confidence,

        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "new_platforms": len(new_platforms),
            "new_posts": len(new_posts),
            "new_wallets": len(new_wallets),
            "new_aliases": len(new_aliases),
            "profile_changes": len(profile_changes),
            "high_confidence": len(high_confidence),
        },

        "checked_at": _now(),
    }


def _materially_changed(
    old: dict[str, Any],
    new: dict[str, Any],
) -> bool:
    """
    Detect meaningful changes while ignoring volatile metadata fields.
    """
    ignored = {
        "last_seen",
        "first_seen",
        "updated_at",
        "observed_at",
        "timestamp",
        "timestamp_parsed",
    }

    keys = (
        set(old.keys())
        | set(new.keys())
    ) - ignored

    for key in keys:
        if old.get(key) != new.get(key):
            return True

    return False


def _is_profile_change(
    old: dict[str, Any],
    new: dict[str, Any],
) -> bool:
    """
    Determine whether a changed finding represents a profile-level change.
    """
    profile_fields = {
        "display_name",
        "username",
        "handle",
        "bio",
        "description",
        "profile_url",
        "avatar",
        "pgp",
        "pgp_key",
        "location",
        "category",
        "status",
    }

    return any(
        old.get(field) != new.get(field)
        for field in profile_fields
        if field in old or field in new
    )


def _looks_like_post(
    finding: dict[str, Any],
) -> bool:
    """
    Handle providers that do not explicitly label a result as a post.
    """
    post_fields = {
        "content",
        "body",
        "message",
        "post_content",
        "post_url",
    }

    return any(
        finding.get(field)
        for field in post_fields
    )


# ---------------------------------------------------------------------------
# Human-readable change messages
# ---------------------------------------------------------------------------

def change_messages(
    changes: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert raw change detection into investigator-facing alert records.
    """
    alerts: list[dict[str, Any]] = []

    for item in changes.get("new_platforms", []):
        alerts.append(
            {
                "alert_type": "new_platform",
                "severity": "high",
                "message": (
                    f"New platform/profile found: "
                    f"{_value(item)}"
                ),
                "finding": item,
            }
        )

    for item in changes.get("new_posts", []):
        alerts.append(
            {
                "alert_type": "new_post",
                "severity": "medium",
                "message": (
                    f"New post/content found: "
                    f"{_value(item)[:160]}"
                ),
                "finding": item,
            }
        )

    for item in changes.get("new_wallets", []):
        alerts.append(
            {
                "alert_type": "new_wallet",
                "severity": "high",
                "message": (
                    f"New wallet identifier found: "
                    f"{_value(item)}"
                ),
                "finding": item,
            }
        )

    for item in changes.get("new_aliases", []):
        alerts.append(
            {
                "alert_type": "new_alias",
                "severity": "medium",
                "message": (
                    f"New alias/handle found: "
                    f"{_value(item)}"
                ),
                "finding": item,
            }
        )

    for item in changes.get("profile_changes", []):
        after = item.get("after") or {}

        alerts.append(
            {
                "alert_type": "profile_changed",
                "severity": "medium",
                "message": (
                    f"Tracked profile changed: "
                    f"{_value(after)}"
                ),
                "finding": after,
                "before": item.get("before"),
            }
        )

    for item in changes.get("high_confidence", []):
        alerts.append(
            {
                "alert_type": "high_confidence_finding",
                "severity": "high",
                "message": (
                    f"High-confidence finding detected: "
                    f"{_value(item)}"
                ),
                "finding": item,
            }
        )

    return alerts


# ---------------------------------------------------------------------------
# Database state helpers
# ---------------------------------------------------------------------------

def _set_watchlist_state(
    db: Any,
    watch_id: str,
    *,
    enabled: Optional[bool] = None,
    last_scan_at: Optional[str] = None,
) -> None:
    """
    Update watchlist state using the database compatibility layer.

    The current DB exposes a generic execute() helper but does not yet expose
    a dedicated update_watchlist() method.
    """
    updates: list[str] = []
    values: list[Any] = []

    if enabled is not None:
        updates.append("enabled = ?")
        values.append(1 if enabled else 0)

    if last_scan_at is not None:
        updates.append("last_scan_at = ?")
        values.append(last_scan_at)

    if not updates:
        return

    updates.append("updated_at = ?")
    values.append(_now())

    values.append(watch_id)

    db.execute(
        f"""
        UPDATE sih_watchlist
        SET {", ".join(updates)}
        WHERE watch_id = ?
        """,
        tuple(values),
    )


def _watch_due(item: dict[str, Any]) -> bool:
    """
    Determine whether a watchlist item is due for another scan.
    """
    if not item.get("enabled"):
        return False

    interval_minutes = max(
        1,
        int(
            item.get("interval_minutes")
            or 60
        ),
    )

    last_scan = item.get("last_scan_at")

    if not last_scan:
        return True

    try:
        parsed = datetime.fromisoformat(
            str(last_scan).replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc,
            )

        elapsed_seconds = (
            datetime.now(timezone.utc) - parsed
        ).total_seconds()

        return elapsed_seconds >= interval_minutes * 60

    except (TypeError, ValueError):
        # Invalid timestamp should not permanently disable a watch.
        return True


# ---------------------------------------------------------------------------
# Alert persistence
# ---------------------------------------------------------------------------

def persist_alerts(
    db: Any,
    actor_id: Optional[str],
    changes: dict[str, Any],
    run_id: Optional[str] = None,
) -> list[str]:
    """
    Persist detected changes as investigator alerts.
    """
    if db is None:
        return []

    alert_ids: list[str] = []

    for alert in change_messages(changes):
        finding = alert.get("finding") or {}

        finding_id = finding.get("finding_id")

        confidence = finding.get("confidence")

        try:
            alert_id = db.add_alert(
                actor_id=actor_id,
                finding_id=finding_id,
                alert_type=alert["alert_type"],
                message=alert["message"],
                confidence=(
                    float(confidence)
                    if confidence is not None
                    else None
                ),
            )

            alert_ids.append(alert_id)

        except Exception:
            # Alert creation must never stop a monitoring scan.
            continue

        # Also add a timeline event when possible.
        try:
            db.add_timeline_event(
                investigation_id=(
                    finding.get("investigation_id")
                    or ""
                ),
                event_type="monitoring_alert",
                message=alert["message"],
                run_id=run_id,
                actor_id=actor_id,
                payload={
                    "alert_type": alert["alert_type"],
                    "severity": alert["severity"],
                    "finding": finding,
                },
            )
        except Exception:
            pass

    return alert_ids


# ---------------------------------------------------------------------------
# Complete tracking cycle
# ---------------------------------------------------------------------------

def process_tracking_result(
    db: Any,
    *,
    actor_id: Optional[str],
    previous_findings: Iterable[dict[str, Any]],
    current_findings: Iterable[dict[str, Any]],
    investigation_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Compare a completed monitoring scan with its previous snapshot.

    Returns the complete change report used by the monitoring UI.
    """
    changes = diff(
        previous_findings,
        current_findings,
    )

    alert_ids = persist_alerts(
        db,
        actor_id,
        changes,
        run_id=run_id,
    )

    result = {
        "status": "ok",
        "actor_id": actor_id,
        "investigation_id": investigation_id,
        "run_id": run_id,
        "changes": changes,
        "alerts_created": alert_ids,
        "alert_count": len(alert_ids),
        "checked_at": _now(),
    }

    if db is not None and investigation_id:
        try:
            db.add_raw_snapshot(
                investigation_id=investigation_id,
                source="tracking",
                snapshot_type="change_detection",
                payload=result,
                run_id=run_id,
            )
        except Exception:
            pass

        try:
            db.add_timeline_event(
                investigation_id=investigation_id,
                event_type="monitoring_completed",
                message=(
                    f"Monitoring completed: "
                    f"{changes['counts']['added']} new findings, "
                    f"{changes['counts']['changed']} changed findings, "
                    f"{len(alert_ids)} alerts"
                ),
                run_id=run_id,
                actor_id=actor_id,
                payload=result,
            )
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Watchlist manager
# ---------------------------------------------------------------------------

class WatchlistManager:
    """
    Application-level watchlist manager.

    The manager handles:
        add
        remove
        pause
        resume
        list
        due checks
    """

    def __init__(self, db: Any):
        self.db = db

    def add(
        self,
        actor_id: str,
        interval_minutes: int = 60,
    ) -> str:
        interval_minutes = max(
            1,
            int(interval_minutes),
        )

        return self.db.add_watchlist(
            actor_id=actor_id,
            interval_minutes=interval_minutes,
        )

    def remove(
        self,
        watch_id: str,
    ) -> None:
        self.db.remove_watchlist(
            watch_id,
        )

    def pause(
        self,
        watch_id: str,
    ) -> None:
        _set_watchlist_state(
            self.db,
            watch_id,
            enabled=False,
        )

    def resume(
        self,
        watch_id: str,
    ) -> None:
        _set_watchlist_state(
            self.db,
            watch_id,
            enabled=True,
        )

    def list(
        self,
    ) -> list[dict[str, Any]]:
        return self.db.list_watchlist()

    def due(
        self,
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in self.list()
            if _watch_due(item)
        ]


# ---------------------------------------------------------------------------
# Background scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """
    Lightweight PRALAYX monitoring scheduler.

    callback(item) is responsible for performing the actual OSINT/crawl
    operation for the tracked actor.

    The scheduler itself only decides when a watch is due.

    threading.Event is used for cooperative shutdown rather than abruptly
    terminating the worker thread. This follows Python's recommended event-
    based signalling model for threads. 0
    """

    def __init__(
        self,
        db: Any,
        callback: Callable[[dict[str, Any]], Any],
        tick_seconds: int = 15,
    ):
        self.db = db
        self.callback = callback

        self.tick_seconds = max(
            1,
            int(tick_seconds),
        )

        self.stop_event = threading.Event()

        self.thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()

        self.last_error: Optional[str] = None

    # --------------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------------

    def start(self) -> bool:
        with self._lock:
            if (
                self.thread
                and self.thread.is_alive()
            ):
                return False

            self.stop_event.clear()

            self.thread = threading.Thread(
                target=self.loop,
                name="pralayx-watchlist-scheduler",
                daemon=True,
            )

            self.thread.start()

            return True

    def stop(
        self,
        timeout: float = 5.0,
    ) -> bool:
        self.stop_event.set()

        thread = self.thread

        if (
            thread
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(
                timeout=max(
                    0.1,
                    float(timeout),
                )
            )

        return not (
            thread
            and thread.is_alive()
        )

    def running(self) -> bool:
        return bool(
            self.thread
            and self.thread.is_alive()
        )

    # --------------------------------------------------------------
    # Main loop
    # --------------------------------------------------------------

    def loop(self) -> None:
        """
        Scheduler loop.

        The wait() call also allows stop() to wake the scheduler instead
        of forcing it to sleep for the entire interval.
        """
        while not self.stop_event.wait(
            self.tick_seconds
        ):
            try:
                self.tick()
            except Exception as exc:
                self.last_error = str(exc)

    def tick(self) -> list[dict[str, Any]]:
        """
        Execute callbacks for all currently due watchlist entries.
        """
        processed: list[dict[str, Any]] = []

        manager = WatchlistManager(
            self.db,
        )

        for item in manager.due():
            watch_id = item.get("watch_id")

            # Mark before invoking callback.
            # This prevents a slow callback from being launched repeatedly
            # during successive scheduler ticks.
            if watch_id:
                _set_watchlist_state(
                    self.db,
                    watch_id,
                    last_scan_at=_now(),
                )

            record = {
                "watch_id": watch_id,
                "actor_id": item.get("actor_id"),
                "started_at": _now(),
                "status": "RUNNING",
            }

            try:
                result = self.callback(
                    item,
                )

                record["status"] = "COMPLETED"
                record["result"] = result

            except Exception as exc:
                record["status"] = "ERROR"
                record["error"] = str(exc)
                self.last_error = str(exc)

                # Monitoring failure is itself useful investigator state.
                try:
                    self.db.add_alert(
                        actor_id=item.get("actor_id"),
                        finding_id=None,
                        alert_type="monitoring_error",
                        message=(
                            f"Scheduled monitoring failed for "
                            f"actor {item.get('actor_id')}: {exc}"
                        ),
                        confidence=None,
                    )
                except Exception:
                    pass

            record["finished_at"] = _now()

            processed.append(
                record,
            )

        return processed


# ---------------------------------------------------------------------------
# Backwards-compatible functional API
# ---------------------------------------------------------------------------

def watchlist(
    db: Any,
) -> list[dict[str, Any]]:
    """
    Compatibility helper for older platform modules.
    """
    return db.list_watchlist()


def add_to_watchlist(
    db: Any,
    actor_id: str,
    interval_minutes: int = 60,
) -> str:
    return WatchlistManager(
        db,
    ).add(
        actor_id,
        interval_minutes,
    )


def remove_from_watchlist(
    db: Any,
    watch_id: str,
) -> None:
    WatchlistManager(
        db,
    ).remove(
        watch_id,
    )


def pause_watch(
    db: Any,
    watch_id: str,
) -> None:
    WatchlistManager(
        db,
    ).pause(
        watch_id,
    )


def resume_watch(
    db: Any,
    watch_id: str,
) -> None:
    WatchlistManager(
        db,
    ).resume(
        watch_id,
    )


__all__ = [
    "diff",
    "change_messages",
    "persist_alerts",
    "process_tracking_result",
    "WatchlistManager",
    "Scheduler",
    "watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "pause_watch",
    "resume_watch",
]
