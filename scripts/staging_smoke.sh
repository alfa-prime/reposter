#!/usr/bin/env bash
# Disposable backend-only staging run. No public ports or external credentials.
set -euo pipefail

cd "$(dirname "$0")/.."

project=reposter-stage
compose=(docker compose -p "$project" -f compose.yaml -f compose.prod.yaml -f compose.tasks.yaml --profile background)
services=(postgres redis migrate app scheduler task-outbox task-rewrite task-collection task-maintenance task-publication)

if [[ -e .env || -e certs/russian_trusted_ca.pem ]]; then
  echo 'Staging requires a fresh checkout without .env or a local CA file.' >&2
  exit 1
fi
if [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$project")" ]] ||
   [[ -n "$(docker volume ls -q --filter "label=com.docker.compose.project=$project")" ]]; then
  echo "Docker project $project already exists; inspect it before starting another run." >&2
  exit 1
fi

cp .env.example .env
chmod 600 .env
sed -i \
  -e 's/^API_WORKERS=.*/API_WORKERS=2/' \
  -e 's/^VK_ACCESS_TOKEN=.*/VK_ACCESS_TOKEN=/' \
  -e 's/^MAX_ACCESS_TOKEN=.*/MAX_ACCESS_TOKEN=/' \
  .env
cp /etc/ssl/certs/ca-certificates.crt certs/russian_trusted_ca.pem

"${compose[@]}" up -d --build --wait "${services[@]}"
"${compose[@]}" ps
"${compose[@]}" exec -T app python - \
  --url http://127.0.0.1:8000/health/database \
  --requests 320 --concurrency 16 < scripts/bench_api_health.py
"${compose[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SHOW max_connections;
SELECT state, count(*) FROM pg_stat_activity
WHERE datname = current_database() GROUP BY state ORDER BY state;
SQL
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'
free -h
df -h /var/lib/docker
