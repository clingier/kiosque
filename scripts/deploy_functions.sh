#!/usr/bin/env bash
# Package config/sources.yaml with the Function App and publish it.
# Usage: scripts/deploy_functions.sh [function-app-name]
set -euo pipefail

APP_NAME="${1:-func-kiosque-prod}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$REPO_ROOT/functions/config"
cp "$REPO_ROOT/config/sources.yaml" "$REPO_ROOT/functions/config/sources.yaml"

cd "$REPO_ROOT/functions"
func azure functionapp publish "$APP_NAME" --python
