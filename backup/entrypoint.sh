#!/usr/bin/env bash
set -Eeuo pipefail

readonly DATABASE_DUMP=/work/database.dump
readonly RESTORE_DIR=/work/restore

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
  log "ERROR: $*" >&2
  exit 1
}

require_variable() {
  local name=$1
  [[ -n "${!name:-}" ]] || die "Required variable ${name} is not set"
}

configure_restic() {
  require_variable BACKUP_S3_ENDPOINT
  require_variable BACKUP_S3_BUCKET
  require_variable BACKUP_S3_ACCESS_KEY
  require_variable BACKUP_S3_SECRET_KEY
  require_variable RESTIC_PASSWORD

  export AWS_ACCESS_KEY_ID=$BACKUP_S3_ACCESS_KEY
  export AWS_SECRET_ACCESS_KEY=$BACKUP_S3_SECRET_KEY
  export AWS_DEFAULT_REGION=${BACKUP_S3_REGION:-ru-1}
  export RESTIC_REPOSITORY="s3:${BACKUP_S3_ENDPOINT%/}/${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX:-reposter}"
}

configure_database() {
  require_variable POSTGRES_DB
  require_variable POSTGRES_USER
  require_variable POSTGRES_PASSWORD

  export PGHOST=${POSTGRES_HOST:-postgres}
  export PGPORT=${POSTGRES_PORT:-5432}
  export PGDATABASE=$POSTGRES_DB
  export PGUSER=$POSTGRES_USER
  export PGPASSWORD=$POSTGRES_PASSWORD
}

ensure_repository() {
  if ! restic snapshots --no-lock >/dev/null 2>&1; then
    log "Initializing encrypted backup repository"
    restic init
  fi
}

create_backup() {
  configure_restic
  configure_database
  ensure_repository

  mkdir -p "$(dirname "$DATABASE_DUMP")"
  local temporary_dump="${DATABASE_DUMP}.tmp"
  rm -f "$temporary_dump"

  log "Creating PostgreSQL dump"
  pg_dump --format=custom --compress=6 --file="$temporary_dump"
  mv "$temporary_dump" "$DATABASE_DUMP"

  log "Uploading encrypted database and media snapshot"
  restic backup \
    --tag automatic \
    --host "${BACKUP_HOST_NAME:-reposter-production}" \
    "$DATABASE_DUMP" /media

  log "Applying retention policy"
  restic forget \
    --host "${BACKUP_HOST_NAME:-reposter-production}" \
    --tag automatic \
    --keep-daily "${BACKUP_KEEP_DAILY:-14}" \
    --keep-weekly "${BACKUP_KEEP_WEEKLY:-8}" \
    --keep-monthly "${BACKUP_KEEP_MONTHLY:-6}" \
    --prune

  rm -f "$DATABASE_DUMP"
  log "Backup completed successfully"
}

verify_backup() {
  configure_restic
  ensure_repository

  log "Checking repository metadata and a sample of stored data"
  restic check --read-data-subset="${BACKUP_CHECK_SUBSET:-5%}"
  log "Backup repository check completed successfully"
}

list_snapshots() {
  configure_restic
  ensure_repository
  restic snapshots --host "${BACKUP_HOST_NAME:-reposter-production}"
}

restore_snapshot() {
  configure_restic
  configure_database

  local snapshot=${RESTORE_SNAPSHOT:-latest}
  [[ "${RESTORE_CONFIRM:-}" == "RESTORE" ]] || die \
    "Restore is destructive. Set RESTORE_CONFIRM=RESTORE to continue"

  rm -rf "$RESTORE_DIR"
  mkdir -p "$RESTORE_DIR"

  log "Downloading snapshot ${snapshot}"
  restic restore "$snapshot" \
    --host "${BACKUP_HOST_NAME:-reposter-production}" \
    --target "$RESTORE_DIR"

  local restored_dump="${RESTORE_DIR}${DATABASE_DUMP}"
  local restored_media="${RESTORE_DIR}/media"
  [[ -f "$restored_dump" ]] || die "Database dump is missing in snapshot"
  [[ -d "$restored_media" ]] || die "Media directory is missing in snapshot"

  log "Restoring PostgreSQL database"
  pg_restore \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    --dbname="$PGDATABASE" \
    "$restored_dump"

  log "Restoring media files"
  find /media -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  cp -a "${restored_media}/." /media/
  log "Snapshot ${snapshot} restored successfully"
}

case "${1:-backup}" in
  backup) create_backup ;;
  verify) verify_backup ;;
  snapshots) list_snapshots ;;
  restore) restore_snapshot ;;
  *) die "Unknown command: $1 (expected backup, verify, snapshots or restore)" ;;
esac
