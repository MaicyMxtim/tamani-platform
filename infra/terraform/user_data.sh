#!/usr/bin/env bash
# Bootstraps k3s on first boot. Traefik disabled: ingress-nginx is the
# planned edge per the project plan. The public IP is fetched from IMDS
# so the API server cert is valid for remote kubectl from day one.
set -euo pipefail
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
mkdir -p /etc/rancher/k3s
cat > /etc/rancher/k3s/config.yaml <<EOF
tls-san:
  - ${PUBLIC_IP}
  - platform.waypear.com
EOF
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
