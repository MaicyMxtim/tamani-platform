"""Prove the governance runtime refuses what it must refuse."""
import json

from governance import GovernanceViolation, Governor

MANIFEST = json.load(open("manifest.json"))
noop = {t: (lambda **kw: {}, False) for t in MANIFEST["allowed_tools"]}
noop["delete_everything"] = (lambda **kw: {}, True)


def expect_violation(label, fn):
    try:
        fn()
        print(f"{label}: FAILED — call was allowed")
    except GovernanceViolation as exc:
        print(f"{label}: REFUSED — {exc}")


g1 = Governor(MANIFEST, noop)
expect_violation("undeclared tool", lambda: g1.call("delete_everything"))

tiny = json.loads(json.dumps(MANIFEST))
tiny["budgets"]["max_tool_calls"] = 2
g2 = Governor(tiny, noop)
g2.call("lookup_venue", venue_id="a")
g2.call("lookup_venue", venue_id="b")
expect_violation("tool-call budget", lambda: g2.call("lookup_venue", venue_id="c"))
print(json.dumps({"run_summary": g2.finish()}))

g3 = Governor(MANIFEST, noop)
g3.call("classify", venue_id="x", description="same")
g3.call("classify", venue_id="x", description="same")
expect_violation("loop detection", lambda: g3.call("classify", venue_id="x", description="same"))
