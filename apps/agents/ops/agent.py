"""
The operations agent. Receives an alert, investigates the cluster with a
read-only service account, retrieves the matching runbook, asks the
gateway for a diagnosis grounded in the collected evidence, and opens a
pull request containing the diagnosis and proposed remediation. It never
applies a change directly.

    python agent.py --alert alert.json [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from governance import GovernanceViolation, Governor  # noqa: E402

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8001")
GATEWAY_KEY = os.getenv("GATEWAY_KEY", "agent-local-key")
KUBECONFIG = os.getenv("OPS_KUBECONFIG", str(Path.home() / ".kube/ops-agent.yaml"))
REPO_ROOT = Path(__file__).resolve().parents[3]

MANIFEST = json.load(open(Path(__file__).parent / "manifest.json"))

ALLOWED_VERBS = {"get", "describe", "logs", "top"}


def k8s_inspect(verb: str, args: str, namespace: str) -> dict:
    """Read-only kubectl, doubly enforced: verb allowlist here, and the
    service account has no write verbs even if this check were bypassed."""
    if verb not in ALLOWED_VERBS:
        raise ValueError(f"verb '{verb}' is not read-only")
    cmd = ["kubectl", "--kubeconfig", KUBECONFIG, "-n", namespace, verb] + args.split()
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return {"stdout": out.stdout[-4000:], "stderr": out.stderr[-500:],
            "rc": out.returncode}


def runbook_lookup(alert_name: str) -> dict:
    path = REPO_ROOT / "runbooks" / f"{alert_name}.md"
    if path.exists():
        return {"found": True, "runbook": path.read_text()[:3000]}
    return {"found": False, "runbook": "no runbook for this alert"}


def diagnose(alert: dict, evidence: str, runbook: str) -> dict:
    prompt = f"""You are a first-line SRE triaging a Kubernetes alert. Using ONLY the evidence given, produce a diagnosis.

ALERT: {json.dumps(alert)}

EVIDENCE (kubectl output):
{evidence}

RUNBOOK:
{runbook}

Respond in markdown with exactly these sections:
## Symptom
## Root cause (cite specific evidence lines)
## Proposed remediation (the change a human should review and apply)
## Confidence (high/medium/low, one sentence why)"""
    req = urllib.request.Request(
        f"{GATEWAY}/v1/complete",
        data=json.dumps({"prompt": prompt, "purpose": "ops-triage",
                         "max_tokens": 1200}).encode(),
        headers={"x-api-key": GATEWAY_KEY, "content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))


def open_pr(alert_name: str, diagnosis: str) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    branch = f"ops-agent/{alert_name.lower()}-{stamp}"
    rel = f"runbooks/diagnoses/{stamp}-{alert_name}.md"
    path = REPO_ROOT / rel
    path.parent.mkdir(exist_ok=True)
    path.write_text(diagnosis + "\n\n---\n*Opened autonomously by the ops agent. "
                    "A human must review and apply any remediation.*\n")
    run = lambda *c: subprocess.run(c, cwd=REPO_ROOT, capture_output=True,
                                    text=True, timeout=120)
    run("git", "checkout", "-b", branch)
    run("git", "add", rel)
    run("git", "commit", "-m", f"ops-agent: diagnosis for {alert_name}")
    run("git", "push", "-u", "origin", branch)
    pr = run("gh", "pr", "create", "--title",
             f"[ops-agent] {alert_name}: diagnosis and proposed remediation",
             "--body", diagnosis[:3000] + "\n\n---\n*Opened autonomously by the "
             "ops agent under its capability manifest. It has read-only cluster "
             "access and cannot apply this change.*")
    run("git", "checkout", "main")
    return {"branch": branch, "pr": pr.stdout.strip() or pr.stderr.strip()}


TOOLS = {
    "k8s_inspect": (k8s_inspect, False),
    "runbook_lookup": (runbook_lookup, False),
    "diagnose": (diagnose, False),
    "open_pr": (open_pr, True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    alert = json.load(open(args.alert))
    name = alert["labels"]["alertname"]
    ns = alert["labels"].get("namespace", "tamani-dev")

    gov = Governor(MANIFEST, TOOLS, dry_run=args.dry_run)
    try:
        pods = gov.call("k8s_inspect", verb="get", args="pods", namespace=ns)
        bad = [l.split()[0] for l in pods["stdout"].splitlines()[1:]
               if l and "Running" not in l and "Completed" not in l]
        evidence = ["$ kubectl get pods\n" + pods["stdout"]]
        for pod in bad[:3]:
            d = gov.call("k8s_inspect", verb="describe", args=f"pod {pod}", namespace=ns)
            evidence.append(f"$ kubectl describe pod {pod}\n" + d["stdout"][-2500:])
            lg = gov.call("k8s_inspect", verb="logs",
                          args=f"{pod} --tail=30 --all-containers", namespace=ns)
            evidence.append(f"$ kubectl logs {pod}\n" +
                            (lg["stdout"] or lg["stderr"])[-1500:])
        rb = gov.call("runbook_lookup", alert_name=name)
        diag = gov.call("diagnose", alert=alert, evidence="\n\n".join(evidence),
                        runbook=rb["runbook"] if isinstance(rb, dict) else "")
        if isinstance(diag, dict) and diag.get("dry_run"):
            print(json.dumps({"note": "dry run: diagnosis skipped"}))
        else:
            pr = gov.call("open_pr", alert_name=name, diagnosis=diag["text"])
            if not (isinstance(pr, dict) and pr.get("dry_run")):
                print(json.dumps({"pr": pr}))
    except GovernanceViolation as exc:
        print(json.dumps({"run": "terminated", "reason": str(exc)}))
    print(json.dumps({"run_summary": gov.finish()}))
    sys.exit(0 if gov.status == "complete" else 2)


if __name__ == "__main__":
    main()
