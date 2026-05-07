# Crypto Backtest Record System

FastAPI + Next.js dashboard for storing and reviewing real Bitget read-only order history.

## Record Window

Core order and fill data is counted only after:

```text
2026-05-07 18:30:00 Asia/Taipei
```

The backend default is `RECORD_START_AT=2026-05-07T18:30:00+08:00`.
`ENFORCE_MINIMUM_RECORD_START=true` prevents older deployment env values from moving the effective start earlier than 18:30.

## Real Bitget Data

Use read-only Bitget API keys only:

```text
BITGET_API_KEY=
BITGET_API_SECRET=
BITGET_API_PASSPHRASE=
```

The backend also accepts common aliases such as `BITGET_SECRET` and `BITGET_PASSPHRASE`.

The real-data endpoints are:

```text
POST /api/bitget/import-readonly
GET  /api/bitget/recorded-data
```

The web dashboard and `/recorded` page use only database rows from `data_source=bitget_api_v2`.

For deployment, set the Web service runtime variable:

```text
API_BASE_URL=https://your-api-domain.zeabur.app/api
```

The frontend uses `/api-proxy` so the browser does not call the backend directly.

## Local Run

```bash
docker compose up --build
```

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000/api/docs
```

## Project Structure

```text
apps/api   FastAPI + SQLAlchemy + Alembic
apps/web   Next.js + TypeScript + Tailwind + React Query
docs
```
