apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: svc-__NAME__
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/k8s/services/__NAME__
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    retry:
      limit: 5
      backoff: { duration: 30s, factor: 2 }
