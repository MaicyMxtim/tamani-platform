#!/usr/bin/env bash
# Bootstraps k3s on first boot. Traefik disabled: ingress-nginx is the
# planned edge per the project plan. The public IP is fetched from IMDS
# so the API server cert is valid for remote kubectl from day one.
set -euo pipefail
# Swap before anything else: a 2 GiB node without swap thrashes to
# lockup under deploy surge (see postmortem 2026-07-23).
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
mkdir -p /etc/rancher/k3s
cat > /etc/rancher/k3s/config.yaml <<EOF
tls-san:
  - ${PUBLIC_IP}
  - platform.waypear.com
EOF
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
