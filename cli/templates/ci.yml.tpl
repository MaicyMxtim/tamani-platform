name: svc-__NAME__

on:
  push:
    branches: [main]
    paths: ["apps/__NAME__/**"]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        id: build
        with:
          context: apps/__NAME__
          push: true
          tags: |
            ghcr.io/maicymxtim/__NAME__:${{ github.sha }}
            ghcr.io/maicymxtim/__NAME__:main
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: trivy vulnerability scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/maicymxtim/__NAME__:${{ github.sha }}
          severity: CRITICAL
          ignore-unfixed: true
          exit-code: "1"
      - name: sbom
        uses: anchore/sbom-action@v0.17.8
        with:
          image: ghcr.io/maicymxtim/__NAME__:${{ github.sha }}
          artifact-name: sbom-__NAME__.spdx.json
      - uses: sigstore/cosign-installer@v3.7.0
      - run: cosign sign --yes ghcr.io/maicymxtim/__NAME__@${{ steps.build.outputs.digest }}
