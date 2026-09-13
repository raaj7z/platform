from pathlib import Path
import os


BASE_DIR = Path(
    __file__
).resolve().parent.parent


def resolve_path(
    value: str,
) -> str:
    path = Path(value)

    if path.is_absolute():
        return str(path)

    return str(
        (BASE_DIR / path).resolve()
    )


DB_PATH = resolve_path(
    os.getenv(
        "OSINT_DB_PATH",
        "../DarkWeb-Deanonymization/data/crawler.db",
    )
)

SCHEMA_PATH = resolve_path(
    os.getenv(
        "SHARED_SCHEMA_PATH",
        "shared/schema_sqlite.sql",
    )
)

CRAWLER_PATH = resolve_path(
    os.getenv(
        "CRAWLER_PATH",
        "../DarkWeb-Deanonymization",
    )
)

OSINT_ENGINE_PATH = resolve_path(
    os.getenv(
        "OSINT_ENGINE_PATH",
        "../osint-engine",
    )
)
