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

PostgreSQL data and Caddy configuration are stored in Docker volumes. Configure the encrypted off-site backups below before treating the instance as permanent production data storage.

## 8. Encrypted S3 backups

The backup contains a consistent PostgreSQL dump and the complete media volume. Restic encrypts all data locally before uploading it to a private S3 bucket. The S3 secret and the Restic encryption password are read only from the server's `.env` file and must never be committed.

Add the private bucket settings to `.env`:

```dotenv
BACKUP_S3_ENDPOINT=https://s3.twcstorage.ru
BACKUP_S3_BUCKET=replace_with_bucket_name
BACKUP_S3_REGION=ru-1
BACKUP_S3_PREFIX=reposter
BACKUP_S3_ACCESS_KEY=replace_with_access_key
BACKUP_S3_SECRET_KEY=replace_with_secret_key
RESTIC_PASSWORD=replace_with_a_separate_long_random_password
BACKUP_HOST_NAME=reposter-production
BACKUP_KEEP_DAILY=14
BACKUP_KEEP_WEEKLY=8
BACKUP_KEEP_MONTHLY=6
BACKUP_CHECK_SUBSET=5%
```

Generate the Restic password separately from the database password and keep an offline copy in a password manager. Losing it makes every backup unrecoverable:

```bash
openssl rand -base64 48
chmod 600 .env
```

Create the first backup manually:

```bash
./backup/run-backup.sh
```

List stored snapshots and run an integrity check:

```bash
docker compose -f compose.yaml -f compose.prod.yaml --profile backup run --rm backup snapshots
./backup/run-verify.sh
```

The default policy retains 14 daily, 8 weekly and 6 monthly snapshots. `BACKUP_CHECK_SUBSET=5%` verifies repository metadata and reads a rotating sample of stored data. A successful backup must be followed by a test restore before relying on it.

### Automatic daily backup

The repository contains systemd unit templates. Replace `REPLACE_WITH_PROJECT_DIRECTORY` in both `.service` files with the absolute repository directory, then install and enable them:

```bash
sudo cp backup/reposter-backup.service /etc/systemd/system/
sudo cp backup/reposter-backup.timer /etc/systemd/system/
sudo cp backup/reposter-backup-verify.service /etc/systemd/system/
sudo cp backup/reposter-backup-verify.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now reposter-backup.timer reposter-backup-verify.timer
systemctl list-timers 'reposter-backup*'
```

The daily job runs around 03:15 server time and catches up after downtime. Repository verification runs monthly. Inspect the latest results with:

```bash
systemctl status reposter-backup.service
journalctl -u reposter-backup.service -n 100 --no-pager
systemctl status reposter-backup-verify.service
```

### Restore drill and disaster recovery

Always test recovery on a disposable server first. A restore replaces the selected database and all media files. Save the current state before starting and make sure no editors are using the application.

List snapshots and note the required ID:

```bash
docker compose -f compose.yaml -f compose.prod.yaml --profile backup run --rm backup snapshots
```

Stop application traffic while keeping PostgreSQL available:

```bash
docker compose -f compose.yaml -f compose.prod.yaml stop frontend app
```

Restore `latest`, or replace it with a snapshot ID. The explicit confirmation protects against an accidental destructive restore:

```bash
RESTORE_CONFIRM=RESTORE RESTORE_SNAPSHOT=latest \
  docker compose -f compose.yaml -f compose.prod.yaml --profile backup \
  run --rm -e RESTORE_CONFIRM -e RESTORE_SNAPSHOT backup restore
```

Apply any migrations added after that snapshot, start the application and check database health, authentication, queue items and several media files:

```bash
docker compose -f compose.yaml -f compose.prod.yaml run --rm migrate
docker compose -f compose.yaml -f compose.prod.yaml up -d app frontend
curl --fail --silent "https://${SITE_ADDRESS}/health/database"
```

Record the date, selected snapshot, duration and result of each restore drill. Repeat the drill after changes to PostgreSQL, Docker volumes or backup scripts, and at least once every three months.
