"""DPI scaling utilities for customtkinter widgets."""

import customtkinter as ctk


def get_scaling_factor() -> float:
    """Get the current widget scaling factor from customtkinter."""
    try:
        return ctk.ScalingTracker.get_widget_scaling(None)
    except Exception:
        return 1.0


def scaled(base_value: int) -> int:
    """Return a scaled value based on current widget scaling factor.

    Args:
        base_value: The base pixel value to scale.

    Returns:
        The scaled pixel value as an integer.
    """
    try:
        factor = ctk.ScalingTracker.get_widget_scaling(None)
        return int(base_value * factor)
    except Exception:
        return base_value
