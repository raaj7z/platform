# SIH26151 Platform API — Step 1 + Step 2

This is the first integration layer between the existing crawler and the existing `osint-engine` repository.

## Important design choice

The crawler already owns `sessions` and `investigations`. This implementation does **not** replace those tables. It adds normalized tables (`actors`, `identifiers`, `findings`, `evidence`, `observations`, `relationships`, `jobs`, `job_events`, `watchlist`, `alerts`) to the same SQLite database.

The canonical investigation ID exposed by the API is the crawler/session `session_id` string. This prevents a second unrelated database or JSON handoff.

## Run locally

1. Put `shared/schema_sqlite.sql` beside this directory and set `OSINT_DB_PATH` to the crawler's `data/crawler.db`.
2. Set `OSINT_ENGINE_PATH` to the checked-out `osint-engine` repository.
3. Install `requirements.txt` in your normal Python installation (no virtual environment required).
4. Start:

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger: `/docs`.

## Endpoints

- `POST /investigate` — manual OSINT input
- `POST /investigate/from-crawler/{investigation_id}` — convert an existing crawler investigation into an OSINT job
- `POST /crawl` — queue a crawler command (configure `CRAWLER_COMMAND` first)
- `GET /jobs/{job_id}` — job status
- `GET /investigations` — history
- `GET /investigations/{id}` — investigation data
- `GET /reports/{id}/network`
- `GET /reports/{id}/threat-actor`
- `WS /ws/investigation/{job_id}` — persisted live job events

The current background execution uses FastAPI `BackgroundTasks`, which is suitable for the initial single-process demo. Heavy/multi-worker production execution should later move to a real job queue.
