"""
helpers/ — read-only scanner/analyst bots that feed main towers.

Helpers never place paper fills. They write JSON signals mains may consume.
Paper only. Fee floors unchanged. Autonomy only after helper Gate A + staff promote.
"""

PAPER_ONLY = True
HELPER_ONLY = True


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
