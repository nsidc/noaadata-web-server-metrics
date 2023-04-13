#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT_DIR="$(realpath "$THIS_DIR/..")"

cd "$REPO_ROOT_DIR"
docker-compose run --rm metrics-cli "$@"
