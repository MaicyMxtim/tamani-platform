#!/usr/bin/env bash
# Bootstraps k3s on first boot. Traefik disabled: ingress-nginx is the
# planned edge per the project plan.
set -euo pipefail
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
