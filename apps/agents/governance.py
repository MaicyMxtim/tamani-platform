"""
The governance runtime. Building an agent is a weekend; this is what
makes autonomous execution safe enough to run unattended:

  - capability manifest: a tool not declared in the manifest cannot be
    called, no matter what the agent decides
  - bounded execution: token, wall-clock and tool-call budgets, with the
    run terminated and marked incomplete on breach
  - loop detection: identical tool call repeated beyond the limit halts
    the run (the most common and most expensive runaway failure)
  - dry-run: every call is recorded; side-effectful tools are simulated
  - traceability: every call emitted as a span with args, latency,
    outcome and token cost
"""
import json
import time


class GovernanceViolation(Exception):
    pass


class Governor:
    def __init__(self, manifest: dict, tools: dict, dry_run: bool = False):
        self.manifest = manifest
        self.tools = tools  # name -> (fn, has_side_effects)
        self.dry_run = dry_run
        self.started = time.monotonic()
        self.tokens_used = 0
        self.call_count = 0
        self.recent_calls: list[str] = []
        self.spans: list[dict] = []
        self.status = "running"

    def _check(self, tool: str, args: dict):
        b = self.manifest["budgets"]
        if tool not in self.manifest["allowed_tools"]:
            raise GovernanceViolation(f"tool '{tool}' is not in the capability manifest")
        if time.monotonic() - self.started > b["max_wall_clock_seconds"]:
            raise GovernanceViolation("wall clock budget exhausted")
        if self.call_count >= b["max_tool_calls"]:
            raise GovernanceViolation("tool call budget exhausted")
        if self.tokens_used >= b["max_tokens_per_run"]:
            raise GovernanceViolation("token budget exhausted")
        fingerprint = tool + ":" + json.dumps(args, sort_keys=True)
        limit = self.manifest["loop_detection"]["identical_call_limit"]
        if self.recent_calls.count(fingerprint) >= limit:
            raise GovernanceViolation(
                f"loop detected: identical call to '{tool}' repeated {limit}x")
        self.recent_calls.append(fingerprint)

    def call(self, tool: str, **args):
        started = time.monotonic()
        try:
            self._check(tool, args)
        except GovernanceViolation as exc:
            self.status = "terminated"
            self._span(tool, args, started, "refused", str(exc))
            raise
        fn, side_effects = self.tools[tool]
        self.call_count += 1
        if self.dry_run and side_effects:
            self._span(tool, args, started, "simulated", None)
            return {"dry_run": True, "tool": tool}
        try:
            result = fn(**args)
        except Exception as exc:  # noqa: BLE001
            self._span(tool, args, started, "error", str(exc))
            raise
        if isinstance(result, dict):
            self.tokens_used += result.get("input_tokens", 0) + result.get("output_tokens", 0)
        self._span(tool, args, started, "ok", None)
        return result

    def _span(self, tool, args, started, outcome, detail):
        span = {
            "span": tool,
            "args": args,
            "ms": round((time.monotonic() - started) * 1000, 1),
            "outcome": outcome,
            "tokens_used_total": self.tokens_used,
            "call_n": self.call_count,
        }
        if detail:
            span["detail"] = detail
        self.spans.append(span)
        print(json.dumps(span), flush=True)

    def finish(self):
        if self.status == "running":
            self.status = "complete"
        return {
            "status": self.status,
            "tool_calls": self.call_count,
            "tokens": self.tokens_used,
            "seconds": round(time.monotonic() - self.started, 2),
            "dry_run": self.dry_run,
        }
