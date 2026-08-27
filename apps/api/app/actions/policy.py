"""
Approval policy engine (§67, §70). Every action that reaches outside the
system (send email, publish to a social platform) must be APPROVED by a
human with at least MEMBER role before `executor.py` will touch it. This is
the one gate the whole safety model depends on — do not bypass it from a
router or a background task.
"""
from app.db.models.enums import OrgRole

MIN_APPROVAL_ROLE = OrgRole.MEMBER
_ROLE_RANK = {OrgRole.VIEWER: 0, OrgRole.MEMBER: 1, OrgRole.ADMIN: 2, OrgRole.OWNER: 3}


def can_approve(role: OrgRole) -> bool:
    return _ROLE_RANK[role] >= _ROLE_RANK[MIN_APPROVAL_ROLE]


def can_send(role: OrgRole) -> bool:
    """Sending is the same bar as approving in this build — organizations can
    tighten this per-role mapping later without touching executor.py."""
    return can_approve(role)
