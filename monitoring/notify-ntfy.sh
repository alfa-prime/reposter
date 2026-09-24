#!/usr/bin/env bash
set -Eeuo pipefail

title=${1:-News Reposter}
message=${2:-Unknown monitoring event}
priority=${3:-high}
tags=${4:-warning}

[[ -n "${NTFY_URL:-}" ]] || {
  printf 'NTFY_URL is not configured\n' >&2
  exit 1
}

headers=(
  --header "Title: ${title}"
  --header "Priority: ${priority}"
  --header "Tags: ${tags}"
)
if [[ -n "${NTFY_TOKEN:-}" ]]; then
  headers+=(--header "Authorization: Bearer ${NTFY_TOKEN}")
fi

curl \
  --fail \
  --silent \
  --show-error \
  --retry 2 \
  --retry-delay 2 \
  --connect-timeout 10 \
  --max-time 20 \
  "${headers[@]}" \
  --data-binary "$message" \
  "$NTFY_URL" >/dev/null
