#!/usr/bin/env bash
# Pull the latest code from GitHub and restart.   Run on the instance: bash /opt/metricaml/deploy/update.sh
set -euo pipefail
cd /opt/metricaml
git pull --ff-only
backend/.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm ci --no-audit --no-fund && npm run build)
sudo systemctl restart metricaml
sudo systemctl status metricaml --no-pager | head -5
