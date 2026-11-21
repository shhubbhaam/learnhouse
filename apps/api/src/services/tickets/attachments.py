"""Image attachments on support tickets.

Upload flow: the client uploads each image first (``upload_ticket_attachment``),
which stores the file and records a *pending* row. Sending a reply then links
the pending rows by ``attachment_uuids`` (``link_attachments``). Images raised
with the ticket are uploaded with ``attach_to_ticket=True`` and are attached
immediately at ticket level.

Files are private: see src/security/ticket_file_access.py.
"""

from collections import defaultdict
from typing import Dict, List, Tuple
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.tickets.ticket_attachments import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    MAX_PENDING_PER_USER,
    TICKET_IMAGE_MAX_BYTES,
    TicketAttachment,
    TicketAttachmentRead,
)
from src.db.tickets.tickets import SupportTicket, TicketStatusEnum
from src.services.utils.upload_content import upload_file


def _directory(ticket: SupportTicket, is_internal: bool) -> str:
    base = f"tickets/{ticket.ticket_uuid}"
    return f"{base}/internal" if is_internal else base


def _read(att: TicketAttachment, ticket: SupportTicket, org_uuid: str) -> TicketAttachmentRead:
    return TicketAttachmentRead(
        attachment_uuid=att.attachment_uuid,
        file_path=f"orgs/{org_uuid}/{_directory(ticket, att.is_internal)}/{att.file_id}",
        content_type=att.content_type,
        size=att.size,
        is_internal=att.is_internal,
    )


async def _org_uuid(db_session: AsyncSession, org_id: int) -> str:
    org_uuid = (
        await db_session.execute(select(Organization.org_uuid).where(Organization.id == org_id))
    ).scalars().first()
    if org_uuid is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org_uuid


async def _count(db_session: AsyncSession, *where) -> int:
    return (await db_session.execute(select(func.count(TicketAttachment.id)).where(*where))).scalar_one()


async def upload_ticket_attachment(
    db_session: AsyncSession,
    ticket_uuid: str,
    file: UploadFile,
    is_internal: bool,
    attach_to_ticket: bool,
    current_user,
) -> TicketAttachmentRead:
    # Imported here: tickets.py imports this module for serialization.
    from src.services.tickets.tickets import _acting_user_id, _load_visible_ticket

    user_id = _acting_user_id(current_user)
    ticket, staff = await _load_visible_ticket(db_session, ticket_uuid, user_id)

    if ticket.status == TicketStatusEnum.CLOSED:
        raise HTTPException(status_code=409, detail="This ticket is closed.")
    if is_internal and not staff:
        raise HTTPException(status_code=403, detail="Only staff can add images to internal notes")
    if attach_to_ticket:
        if ticket.user_id != user_id or is_internal:
            raise HTTPException(status_code=403, detail="Only the ticket owner can add images to the ticket itself")
        existing = await _count(
            db_session,
            TicketAttachment.ticket_id == ticket.id,
            TicketAttachment.message_id.is_(None),
            TicketAttachment.attached == True,  # noqa: E712
        )
        if existing >= MAX_ATTACHMENTS_PER_MESSAGE:
            raise HTTPException(status_code=400, detail=f"A ticket can have at most {MAX_ATTACHMENTS_PER_MESSAGE} images")
    else:
        pending = await _count(
            db_session,
            TicketAttachment.ticket_id == ticket.id,
            TicketAttachment.uploader_id == user_id,
            TicketAttachment.attached == False,  # noqa: E712
        )
        if pending >= MAX_PENDING_PER_USER:
            raise HTTPException(status_code=400, detail="Too many unsent images on this ticket. Send or discard some first.")

    org_uuid = await _org_uuid(db_session, ticket.org_id)
    file_id = await upload_file(
        file=file,
        directory=_directory(ticket, is_internal),
        type_of_dir="orgs",
        uuid=org_uuid,
        allowed_types=["image"],
        filename_prefix="ticket",
        max_size=TICKET_IMAGE_MAX_BYTES,
    )

    attachment = TicketAttachment(
        attachment_uuid=f"ticketatt_{uuid4()}",
        ticket_id=ticket.id,
        uploader_id=user_id,
        file_id=file_id,
        content_type=file.content_type or "application/octet-stream",
        size=file.size or 0,
        is_internal=is_internal,
        attached=attach_to_ticket,
    )
    db_session.add(attachment)
    await db_session.commit()
    await db_session.refresh(attachment)
    return _read(attachment, ticket, org_uuid)


async def claim_pending_attachments(
    db_session: AsyncSession,
    ticket: SupportTicket,
    attachment_uuids: List[str],
    user_id: int,
    is_internal: bool,
) -> List[TicketAttachment]:
    """Load the rows a reply wants to attach, or raise 400.

    Every uuid must be a pending upload on this ticket by this user with the
    same internal flag as the message. Nothing is modified here, so a rejected
    reply leaves no partial state.
    """
    if not attachment_uuids:
        return []
    if len(set(attachment_uuids)) != len(attachment_uuids):
        raise HTTPException(status_code=400, detail="Invalid attachment")
    rows = (
        await db_session.execute(
            select(TicketAttachment).where(TicketAttachment.attachment_uuid.in_(attachment_uuids))
        )
    ).scalars().all()
    by_uuid = {r.attachment_uuid: r for r in rows}
    claimed = []
    for uuid in attachment_uuids:
        row = by_uuid.get(uuid)
        if (
            row is None
            or row.ticket_id != ticket.id
            or row.uploader_id != user_id
            or row.attached
            or row.is_internal != is_internal
        ):
            raise HTTPException(status_code=400, detail="Invalid attachment")
        claimed.append(row)
    return claimed


async def attachments_for(
    db_session: AsyncSession, ticket: SupportTicket, include_internal: bool
) -> Tuple[List[TicketAttachmentRead], Dict[int, List[TicketAttachmentRead]]]:
    """Sent attachments of a ticket: (ticket-level, by message id)."""
    stmt = (
        select(TicketAttachment)
        .where(TicketAttachment.ticket_id == ticket.id)
        .where(TicketAttachment.attached == True)  # noqa: E712
        .order_by(TicketAttachment.id.asc())
    )
    if not include_internal:
        stmt = stmt.where(TicketAttachment.is_internal == False)  # noqa: E712
    rows = (await db_session.execute(stmt)).scalars().all()
    if not rows:
        return [], {}
    org_uuid = await _org_uuid(db_session, ticket.org_id)
    ticket_level: List[TicketAttachmentRead] = []
    by_message: Dict[int, List[TicketAttachmentRead]] = defaultdict(list)
    for row in rows:
        if row.message_id is None:
            ticket_level.append(_read(row, ticket, org_uuid))
        else:
            by_message[row.message_id].append(_read(row, ticket, org_uuid))
    return ticket_level, dict(by_message)


async def read_attachments(
    db_session: AsyncSession, ticket: SupportTicket, rows: List[TicketAttachment]
) -> List[TicketAttachmentRead]:
    if not rows:
        return []
    org_uuid = await _org_uuid(db_session, ticket.org_id)
    return [_read(r, ticket, org_uuid) for r in rows]
