#!/usr/bin/env bash
set -euo pipefail
cd backend
python -m app.cli.main scan "$1"
python -m app.cli.main build-parse-queue
python -m app.cli.main parse --limit 20
