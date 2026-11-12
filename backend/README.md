# Security Monitoring API — Sprint 3

Flask backend for authentication, upload, search and security policy management.

## Services

- Flask API on `http://localhost:8000`
- MongoDB: users, uploaded file metadata, search history, security events, settings
- Redis: failed-login counters and temporary IP blocks
- Elasticsearch: log search, statistics and upload status
- Logstash: CSV, JSON and TXT ingestion pipelines

## Start

From the repository root:

```bash
cp .env.example .env
# Edit .env: passwords, secrets, GeoIP settings
make up
make seed
make api
```

Or rebuild only the API:

```bash
make api
make seed
```

Health check:

```bash
curl http://localhost:8000/health
```

Swagger UI:

```text
http://localhost:8000/api/v1/docs
```

OpenAPI file:

```text
http://localhost:8000/api/v1/openapi.yaml
```

## Seeded users

| Username | Role | Purpose |
| --- | --- | --- |
| `admin` | admin | User management, settings, full access |
| `analyst` | analyst | Upload and search |
| `user` | user | Read-only testing |

Passwords come from `ADMIN_PASSWORD`, `ANALYST_PASSWORD` and `USER_PASSWORD`.

There is no public registration. Admins create users through `/api/v1/admin/users`.

## Authentication

Login:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"ChangeMe-Admin-123!"}'
```

Use the returned token:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me
```

## GeoIP country policy

The admin can choose allowlist or blocklist mode:

```bash
curl -X PUT http://localhost:8000/api/v1/admin/settings/geo \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "enabled": true,
    "mode": "allowlist",
    "allowed_countries": ["TN", "FR", "DE"],
    "blocked_countries": [],
    "unknown_country": "deny",
    "allow_private_ips": true
  }'
```

- Allowlist mode: only listed countries can log in.
- Blocklist mode: listed countries cannot log in.
- Unknown country: denied by default.
- Private/local IPs are allowed only when `allow_private_ips` is true.
- The GeoIP database is `infra/geoip/GeoLite2-Country.mmdb`.

Download the database:

```bash
export MAXMIND_LICENSE_KEY="your-key"
./scripts/download_geolite2.sh
```

If the database is missing:

- `GEOIP_FAIL_MODE=open` allows login and logs a warning.
- `GEOIP_FAIL_MODE=closed` denies login.

## Upload

Preview:

```bash
curl -X POST http://localhost:8000/api/v1/files/preview \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.csv"
```

Upload:

```bash
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.csv"
```

Files are saved in `data/input/` and picked up by Logstash. Check status:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/files?status=completed"
```

## Search

```bash
curl -G http://localhost:8000/api/v1/logs \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "q=login" \
  --data-urlencode "level=WARNING" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=50"
```

Export CSV:

```bash
curl -G http://localhost:8000/api/v1/logs/export \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "q=login" \
  -o security-logs.csv
```

## Statistics

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/stats
```

## Tests

Inside Docker:

```bash
make test
```

Locally:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/pytest tests -q
```

Unit tests use `mongomock` and `fakeredis`. Elasticsearch integration tests require the full stack.
