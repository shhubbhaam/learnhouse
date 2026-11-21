"""Access control for support-ticket attachment files.

Ticket images are stored under ``orgs/{org_uuid}/tickets/{ticket_uuid}/{file}``
(internal-note images under ``.../{ticket_uuid}/internal/{file}``). The generic
content rule treats everything under ``orgs/`` as public, which would let
anyone holding a link see a learner's screenshot. These helpers are called by
both content routers before that rule and allow a file only when:

* an attachment row exists for exactly this ticket, file and internal flag, and
* the caller is org staff (admin/maintainer, or superadmin), the uploader, or
  the ticket owner for a non-internal image that has been sent.
"""

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.tickets.ticket_attachments import TicketAttachment
from src.db.tickets.tickets import SupportTicket
from src.db.users import AnonymousUser, APITokenUser


def is_ticket_file(parts: list[str]) -> bool:
    """True when the split content path points inside a ticket's folder."""
    return len(parts) >= 5 and parts[0] == "orgs" and parts[2] == "tickets"


def _deny() -> HTTPException:
    return HTTPException(status_code=403, detail="Access denied")


async def enforce_ticket_file_access(parts: list[str], current_user, db_session: AsyncSession) -> None:
    """Raise 401/403 unless the caller may read this ticket file.

    Assumes ``is_ticket_file(parts)`` matched. Never falls through to a more
    permissive rule: every path out of this function either returns (allowed)
    or raises.
    """
    if isinstance(current_user, AnonymousUser) or getattr(current_user, "id", None) is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    # API tokens are not a person: there is no owner/uploader identity to check.
    if isinstance(current_user, APITokenUser):
        raise _deny()

    org_uuid, ticket_uuid = parts[1], parts[3]
    rest = parts[4:]
    if len(rest) == 1:
        is_internal, file_id = False, rest[0]
    elif len(rest) == 2 and rest[0] == "internal":
        is_internal, file_id = True, rest[1]
    else:
        raise _deny()

    ticket = (
        await db_session.execute(select(SupportTicket).where(SupportTicket.ticket_uuid == ticket_uuid))
    ).scalars().first()
    if ticket is None:
        raise _deny()

    # The org segment of the path must be the ticket's own org.
    org = (
        await db_session.execute(select(Organization.org_uuid).where(Organization.id == ticket.org_id))
    ).scalars().first()
    if org != org_uuid:
        raise _deny()

    attachment = (
        await db_session.execute(
            select(TicketAttachment)
            .where(TicketAttachment.ticket_id == ticket.id)
            .where(TicketAttachment.file_id == file_id)
            .where(TicketAttachment.is_internal == is_internal)  # noqa: E712
        )
    ).scalars().first()
    if attachment is None:
        raise _deny()

    # Imported here to avoid a module cycle (services import security helpers).
    from src.services.tickets.tickets import is_ticket_staff

    user_id = current_user.id
    if await is_ticket_staff(db_session, user_id, ticket.org_id):
        return
    if attachment.uploader_id == user_id:
        return
    if ticket.user_id == user_id and attachment.attached and not attachment.is_internal:
        return
    raise _deny()
