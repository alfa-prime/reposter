# Production / demo deployment

Recommended VPS baseline: Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 40+ GB SSD.

## Fast demo mode without a domain

For the current customer demo, the simplest setup is plain HTTP by VPS IPv4 address with Caddy Basic Auth.

Use:

```dotenv
SITE_ADDRESS=:80
ADMIN_USER=demo
ADMIN_PASSWORD_HASH='<bcrypt-hash>'
```

Then open:

```text
http://VPS_IP
```

Important: Basic Auth over plain HTTP is suitable only as a temporary demo barrier. HTTP does not encrypt the login/password or traffic. Use a unique temporary password, do not reuse any real password, and do not place sensitive data in this demo instance. When a domain is added, switch `SITE_ADDRESS` to the domain and Caddy will provide HTTPS automatically.

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
git switch feature/frontend-admin
```

Use an SSH deploy key or another secure GitHub credential for the private repository.

## 3. Environment

```bash
cp .env.example .env
chmod 600 .env
```

For the current IP-only demo set at least:

```dotenv
API_KEY=<random-secret>
VK_ACCESS_TOKEN=<token>
MAX_ACCESS_TOKEN=<token>
POSTGRES_PASSWORD=<strong-random-password>
SITE_ADDRESS=:80
ADMIN_USER=demo
ADMIN_PASSWORD_HASH='<bcrypt-hash>'
```

Generate a strong API key and database password, for example:

```bash
openssl rand -hex 32
```

Generate the Caddy-compatible bcrypt password hash on the server:

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'YOUR_TEMP_DEMO_PASSWORD'
```

Copy the complete output into `ADMIN_PASSWORD_HASH` in `.env`. Keep the value single-quoted because bcrypt hashes contain `$` characters.

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

The web UI, API, Swagger and health endpoint are protected by HTTP Basic Authentication at Caddy. FastAPI is not exposed publicly in the production override.

## 5. Open the demo

Go to:

```text
http://VPS_IP
```

The browser will ask for `ADMIN_USER` and the temporary password used to create `ADMIN_PASSWORD_HASH`.

## 6. Later: add a domain and HTTPS

Point an A record at the VPS IPv4 address, for example:

```text
news.example.ru -> 203.0.113.10
```

Change only:

```dotenv
SITE_ADDRESS=news.example.ru
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
