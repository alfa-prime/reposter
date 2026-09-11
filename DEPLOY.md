# Production deployment

Recommended VPS baseline: Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 40+ GB SSD.

## 1. DNS

Create an A record for the chosen domain/subdomain and point it to the VPS IPv4 address.

Example:

```text
news.example.ru -> 203.0.113.10
```

## 2. Server preparation

Install Docker Engine and the Docker Compose plugin. Allow only SSH, HTTP and HTTPS through the firewall.

Example with UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 3. Clone repository

```bash
git clone git@github.com:alfa-prime/reposter.git
cd reposter
git switch feature/frontend-admin
```

Use an SSH deploy key or another secure GitHub credential for the private repository.

## 4. Environment

```bash
cp .env.example .env
chmod 600 .env
```

At minimum set strong values for:

```dotenv
API_KEY=<random-secret>
VK_ACCESS_TOKEN=<token>
MAX_ACCESS_TOKEN=<token>
POSTGRES_PASSWORD=<strong-random-password>
SITE_ADDRESS=news.example.ru
ADMIN_USER=admin
ADMIN_PASSWORD_HASH='<bcrypt-hash>'
```

Generate the Caddy-compatible bcrypt password hash on the server:

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'YOUR_PASSWORD'
```

Copy the complete output into `ADMIN_PASSWORD_HASH` in `.env`. Keep the value single-quoted because bcrypt hashes contain `$` characters.

## 5. Start production

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Caddy will obtain and renew a public TLS certificate automatically when `SITE_ADDRESS` is a real domain pointing to the VPS and ports 80/443 are reachable.

The web UI, API, Swagger and health endpoint are protected by HTTP Basic Authentication at Caddy. The backend port is bound only to `127.0.0.1` on the VPS and is not exposed publicly.

## 6. Useful commands

```bash
docker compose -f compose.yaml -f compose.prod.yaml ps
docker compose -f compose.yaml -f compose.prod.yaml logs -f frontend app
docker compose -f compose.yaml -f compose.prod.yaml pull
git pull
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

PostgreSQL data and Caddy certificates/config are stored in Docker volumes. Add periodic PostgreSQL backups before treating the instance as production data storage.
