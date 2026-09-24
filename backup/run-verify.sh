#!/usr/bin/env bash
set -Eeuo pipefail

project_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_directory"

docker compose -f compose.yaml -f compose.prod.yaml --profile backup run --rm backup verify
