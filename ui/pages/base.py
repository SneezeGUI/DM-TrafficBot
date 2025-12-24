"""Base page mixin providing common functionality for all pages."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.app import ModernTrafficBot


class PageMixin:
    """Mixin class providing common page functionality.

    Pages inherit from this to get access to common patterns like:
    - Thread-safe logging
    - Settings access
    - UI update scheduling
    """

    app: "ModernTrafficBot"

    def log(self, message: str) -> None:
        """Log a message to the activity log (main thread only)."""
        if hasattr(self.app, "activity_log"):
            self.app.activity_log.log(message)

    def log_safe(self, message: str) -> None:
        """Thread-safe logging - schedules log on main thread."""
        self.app.after(0, lambda: self.log(message))

    @property
    def settings(self) -> dict:
        """Access the app settings dictionary."""
        return self.app.settings
