"""The event log (PRD §7.9): record who did what in the panel, and when.

Call `record()` next to the change, inside the same transaction, so an entry exists exactly when
the change does. Entries are plain text meant for the administrator, written in Polish.
"""

from typing import Any

from workshop_manager.core.models import AuditEvent


def record(
    user: Any, action: str, target: Any = "", *, details: str = "", url: str = ""
) -> AuditEvent:
    """Log `action` ("Przyjęto zgłoszenie") on `target` (an object or a text) by `user`."""
    if not url and hasattr(target, "get_panel_url"):
        url = target.get_panel_url()
    actor = user if getattr(user, "is_authenticated", False) else None
    return AuditEvent.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", "") if actor else "",
        action=action[:120],
        target=str(target)[:250],
        url=url[:250],
        details=details,
    )
