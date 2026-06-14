#!/usr/bin/env bash
set -euo pipefail
mysql -uroot -p < sql/001_init_schema_v1_1.sql
