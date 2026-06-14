#!/usr/bin/env bash
set -euo pipefail
mkdir -p backend/tests/fixtures/中文路径/银行项目
echo "示例方案内容" > backend/tests/fixtures/中文路径/银行项目/方案.txt
cp backend/tests/fixtures/中文路径/银行项目/方案.txt backend/tests/fixtures/中文路径/银行项目/方案副本.txt
