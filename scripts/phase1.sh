#!/usr/bin/env bash
# Phase 1 Nexus ↔ GitHub Codex contract verification
# Runs the isolated contract test with proper PYTHONPATH

set -euo pipefail

echo "Running Phase 1 contract test..."

PYTHONPATH=. python -m pytest -q tests/test_nexus_codex_task_contract.py

echo ""
echo "✅ Phase 1 contract test complete."
