#!/usr/bin/env bash
set -euo pipefail

if ! command -v poetry >/dev/null 2>&1; then
  echo "Poetry is required. Install Poetry before running this script." >&2
  exit 1
fi

poetry install --with dev
cp -n .env.example .env || true

echo "Environment prepared. Start MySQL with: docker compose up -d mysql adminer"
