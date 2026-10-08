#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 22.04/24.04 EC2 instance (t3.micro is enough).
# Run as the default login user (ubuntu), not root:   bash deploy/setup_ec2.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/hemapriyan-rk/MetricaML.git}"
APP_DIR=/opt/metricaml
DATA_DIR=/var/lib/metricaml
RUN_USER="$(id -un)"

echo "==> Installing system packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip nginx git curl ca-certificates

echo "==> Installing Node.js 20 (only needed to build the React app)"
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "==> Adding 1 GB of swap (a t3.micro has 1 GB RAM; this keeps builds and training safe)"
if ! swapon --show | grep -q .; then
  sudo fallocate -l 1G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> Fetching the code into $APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  sudo mkdir -p "$APP_DIR"
  sudo chown "$RUN_USER":"$RUN_USER" "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
fi
sudo mkdir -p "$DATA_DIR"
sudo chown "$RUN_USER":"$RUN_USER" "$DATA_DIR"

echo "==> Python environment"
cd "$APP_DIR/backend"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Building the web app"
cd "$APP_DIR/frontend"
npm ci --no-audit --no-fund
npm run build

echo "==> Registering the service and the web server"
sed "s/__USER__/$RUN_USER/" "$APP_DIR/deploy/metricaml.service" | sudo tee /etc/systemd/system/metricaml.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now metricaml

sudo cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/metricaml
sudo ln -sf /etc/nginx/sites-available/metricaml /etc/nginx/sites-enabled/metricaml
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 || true)
echo
echo "MetricaML is running. Open:  http://${IP:-<your-instance-public-ip>}/"
