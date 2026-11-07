"""
helpers/ — read-only scanner/analyst bots that feed main towers.

Helpers never place paper fills. They write JSON signals mains may consume.
Paper only. Fee floors unchanged. Autonomy only after helper Gate A + staff promote.
"""

from helpers.advice_schema import (  # noqa: F401
    LOCKED_VENUE_FLOORS,
    SCHEMA_VERSION,
    validate_helper_advice,
)

PAPER_ONLY = True
HELPER_ONLY = True

__all__ = [
    "PAPER_ONLY",
    "HELPER_ONLY",
    "SCHEMA_VERSION",
    "LOCKED_VENUE_FLOORS",
    "validate_helper_advice",
    "may_place_alone",
    "assert_helper_only",
]


def may_place_alone(root=None, helper: str = "") -> bool:
    """Default False. True only when desk_roi_plan helper Gate A is armed."""
    try:
        import desk_roi_plan
        return desk_roi_plan.helper_may_place_alone(root, helper or "helpers")
    except Exception:
        return False


def assert_helper_only(helper: str = "helpers") -> None:
    """Hard guard: helper package stays paper/helper-only (never a live placer)."""
    assert HELPER_ONLY and PAPER_ONLY, (
        f"helper {helper} must stay paper/helper-only"
    )
