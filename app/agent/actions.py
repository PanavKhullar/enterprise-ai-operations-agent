"""
Whitelisted operational actions the agent is allowed to execute.

These are intentionally simulated (no real infrastructure calls) so the
agent can never take a destructive or unbounded action: it can only ever
invoke one of the functions below, with the exact parameters a human
operator approved.
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reassign_carrier_volume(params: dict) -> dict:
    carrier = params.get("carrier", "the underperforming carrier")
    target_carrier = params.get("target_carrier", "an alternate carrier")
    percentage = params.get("percentage", 100)

    return {
        "status": "executed",
        "action": "reassign_carrier_volume",
        "message": (
            f"Reassigned {percentage}% of shipping volume from {carrier} "
            f"to {target_carrier}."
        ),
        "timestamp": _now(),
    }


def scale_warehouse(params: dict) -> dict:
    warehouse = params.get("warehouse", "the affected warehouse")
    extra_staff = params.get("extra_staff", 0)

    return {
        "status": "executed",
        "action": "scale_warehouse",
        "message": (
            f"Scaled staffing at {warehouse} by {extra_staff} additional "
            f"workers."
        ),
        "timestamp": _now(),
    }


def escalate_vendor(params: dict) -> dict:
    vendor = params.get("vendor", "the vendor")

    return {
        "status": "executed",
        "action": "escalate_vendor",
        "message": f"Escalated the performance issue to {vendor} account management.",
        "timestamp": _now(),
    }


def no_action(params: dict) -> dict:
    return {
        "status": "skipped",
        "action": "no_action",
        "message": "No remediation action was taken.",
        "timestamp": _now(),
    }


ALLOWED_ACTIONS = {
    "reassign_carrier_volume": reassign_carrier_volume,
    "scale_warehouse": scale_warehouse,
    "escalate_vendor": escalate_vendor,
    "no_action": no_action,
}
