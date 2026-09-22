# Production / demo deployment

Recommended VPS baseline: Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 40+ GB SSD.

## Recommended production mode

Point a domain at the server and set it in `.env`:

```dotenv
SITE_ADDRESS=news.example.ru
AUTH_COOKIE_SECURE=true
```

Caddy will obtain and renew the public TLS certificate automatically. The application uses its own user accounts, server-side sessions, roles, CSRF protection and login rate limiting; Caddy Basic Auth is not used.

Allow SSH, HTTP and HTTPS:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Temporary IP-only mode

For a short test without a domain, use plain HTTP:

```dotenv
SITE_ADDRESS=:80
AUTH_COOKIE_SECURE=false
```

Then open:

```text
http://VPS_IP
```

Important: HTTP does not encrypt credentials or traffic. Use this mode only for a temporary test, do not reuse real passwords and do not place sensitive data in the instance. Switch to a domain and HTTPS before regular use.

For IP-only demo mode the firewall only needs SSH and HTTP:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw enable
```

## 1. Server preparation

Install Docker Engine, the Docker Compose plugin and Git.

On Ubuntu 24.04 you can use Docker's official repository or the provider's preinstalled Docker image. Verify:

```bash
docker --version
docker compose version
git --version
```

## 2. Clone repository

```bash
git clone git@github.com:alfa-prime/reposter.git
cd reposter
git switch master
```

Use an SSH deploy key or another secure GitHub credential for the private repository.

## 3. Environment

```bash
cp .env.example .env
chmod 600 .env
```

Set at least:

```dotenv
VK_ACCESS_TOKEN=<token>
MAX_ACCESS_TOKEN=<token>
POSTGRES_PASSWORD=<strong-random-password>
SITE_ADDRESS=:80
AUTH_COOKIE_SECURE=false
```

Generate a strong database password, for example:

```bash
openssl rand -hex 32
```

## 4. Start demo/production stack

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Check status:

```bash
docker compose -f compose.yaml -f compose.prod.yaml ps
```

Watch logs if needed:

```bash
docker compose -f compose.yaml -f compose.prod.yaml logs -f frontend app
```

FastAPI is not exposed directly in the production override. Caddy terminates HTTP/HTTPS and proxies API requests; application access is protected by FastAPI user sessions and permissions.

For a fresh database, create the first administrator interactively:

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec app \
  python -m news_reposter.cli create-admin
```

## 5. Open the demo

Go to:

```text
http://VPS_IP
```

Sign in with the application administrator account.

## 6. Later: add a domain and HTTPS

Point an A record at the VPS IPv4 address, for example:

```text
news.example.ru -> 203.0.113.10
```

Change only:

```dotenv
SITE_ADDRESS=news.example.ru
AUTH_COOKIE_SECURE=true
```

Then allow HTTPS and restart:

```bash
sudo ufw allow 443/tcp
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Caddy will obtain and renew the public TLS certificate automatically when the domain points to the VPS and ports 80/443 are reachable.

## 7. Updating

```bash
git pull
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

PostgreSQL data and Caddy configuration are stored in Docker volumes. Add periodic PostgreSQL backups before treating the instance as permanent production data storage.
