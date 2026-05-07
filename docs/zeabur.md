# Zeabur Deployment Notes

If the Web service runtime log shows Caddy serving on `:8080`, Zeabur is not running the Next.js frontend. It is treating the repo as a static service. Redeploy the Web service with one of these Dockerfile paths.

## Web Service

Recommended when the Zeabur service root is the repository root:

```text
Root directory: .
Dockerfile: Dockerfile
Port: 3000
```

Alternative when the Zeabur service root is `apps/web`:

```text
Root directory: apps/web
Dockerfile: apps/web/Dockerfile
Port: 3000
```

Recommended Web environment variable:

```text
API_BASE_URL=https://your-api-domain.zeabur.app/api
```

The frontend calls its own `/api-proxy` route first, then the server-side proxy forwards requests to `API_BASE_URL`. This avoids browser CORS and stale build-time public env values. `NEXT_PUBLIC_API_BASE_URL`, `BACKEND_URL`, `API_URL`, and common public backend env names are also supported as fallbacks. If none are set, the proxy tries the same domain `/api`.

The Web Dockerfiles build Next.js with `output: "standalone"` and run `node server.js`. The runtime honors Zeabur's `PORT` variable if Zeabur provides one.

## API Service

Use a separate service for the backend:

```text
Root directory: apps/api
Dockerfile: apps/api/Dockerfile
Port: 8000
Volume mount: /data/storage
```

Required API environment variables:

```text
DATABASE_URL=postgresql+psycopg://...
STORAGE_ROOT=/data/storage
BACKEND_CORS_ORIGINS=https://your-web-domain.zeabur.app
RECORD_START_AT=2026-05-07T18:30:00+08:00
ENFORCE_MINIMUM_RECORD_START=true
DEFAULT_TIMEZONE=Asia/Taipei
BITGET_API_BASE_URL=https://api.bitget.com
BITGET_API_KEY=
BITGET_API_SECRET=
BITGET_API_PASSPHRASE=
BITGET_LOCALE=en-US
```

The API also accepts common aliases such as `BITGET_SECRET`, `BITGET_SECRET_KEY`, `BITGET_PASSPHRASE`, `BITGET_PASS_PHRASE`, `API_KEY`, `SECRET_KEY`, and `PASSPHRASE`, but the canonical names above are recommended. `/api/bitget/status` reports which required key part is still missing.

## Postgres

Create a Zeabur Postgres service and keep its volume persistent. The API service and `/data/storage` volume should also be persistent so raw imports and database rows survive redeploys.
