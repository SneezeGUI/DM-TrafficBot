"""UI package for DarkMatter Traffic Bot.

This package contains the user interface components:
- app.py: Main application window (ModernTrafficBot)
- components.py: Reusable UI components (VirtualGrid, ActivityLog, DraggableSash)
- styles.py: Color scheme and styling constants
- utils.py: Utility functions (settings, validation)
- scaling.py: DPI scaling utilities
- pages/: Page-specific UI modules
"""

from .components import ActivityLog, DraggableSash, VirtualGrid
from .scaling import get_scaling_factor, scaled
from .styles import COLORS
from .utils import Utils

__all__ = [
    "scaled",
    "get_scaling_factor",
    "COLORS",
    "Utils",
    "VirtualGrid",
    "ActivityLog",
    "DraggableSash",
]
