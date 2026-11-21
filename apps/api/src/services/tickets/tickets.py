"""Support ticket service.

Access model
------------
* Learner endpoints require membership of the target org. A ticket is only
  visible to its owner and to that org's staff.
* "Staff" = admin or maintainer of the ticket's org (ADMIN_OR_MAINTAINER_ROLE_IDS),
  or a platform superadmin. This mirrors the rest of the dashboard.
* Ticket lookups that fail authorization return 404, not 403, so a caller
  cannot probe which ticket uuids exist in other orgs.
* Internal notes (is_internal=True) are never returned to non-staff.
"""

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Union
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.courses import Course
from src.db.organizations import Organization
from src.db.tickets.ticket_messages import (
    SupportTicketDetail,
    TicketMessage,
    TicketMessageCreate,
    TicketMessageRead,
)
from src.db.tickets.tickets import (
    SupportTicket,
    SupportTicketCreate,
    SupportTicketPage,
    SupportTicketRead,
    SupportTicketUpdate,
    TicketCategoryEnum,
    TicketCourseRef,
    TicketPriorityEnum,
    TicketStatusEnum,
)
from src.db.tickets.ticket_attachments import TicketAttachmentRead
from src.db.user_organizations import UserOrganization
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User, UserReadAuthor
from src.security.rbac.constants import ADMIN_OR_MAINTAINER_ROLE_IDS
from src.security.superadmin import is_user_superadmin
from src.services.tickets.attachments import (
    attachments_for,
    claim_pending_attachments,
    read_attachments,
)

MAX_PAGE_SIZE = 100

CurrentUser = Union[PublicUser, AnonymousUser, APITokenUser]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def _acting_user_id(current_user: CurrentUser) -> int:
    """Tickets are a session-only feature: reject anonymous and API tokens.

    The router is mounted behind require_authenticated_user already; this is
    defence in depth for any future caller of the service.
    """
    if isinstance(current_user, AnonymousUser):
        raise HTTPException(status_code=401, detail="Authentication required")
    if isinstance(current_user, APITokenUser):
        raise HTTPException(status_code=403, detail="API tokens cannot access support tickets")
    return current_user.id


async def _member_role_id(db_session: AsyncSession, user_id: int, org_id: int) -> Optional[int]:
    result = await db_session.execute(
        select(UserOrganization.role_id)
        .where(UserOrganization.user_id == user_id)
        .where(UserOrganization.org_id == org_id)
    )
    return result.scalars().first()


async def _is_staff(db_session: AsyncSession, user_id: int, org_id: int) -> bool:
    if await is_user_superadmin(user_id, db_session):
        return True
    role_id = await _member_role_id(db_session, user_id, org_id)
    return role_id is not None and role_id in ADMIN_OR_MAINTAINER_ROLE_IDS


async def is_ticket_staff(db_session: AsyncSession, user_id: int, org_id: int) -> bool:
    """Public form of the staff check, used by src/security/ticket_file_access.py."""
    return await _is_staff(db_session, user_id, org_id)


async def _require_member(db_session: AsyncSession, user_id: int, org_id: int) -> None:
    if await is_user_superadmin(user_id, db_session):
        org = (await db_session.execute(select(Organization.id).where(Organization.id == org_id))).scalars().first()
        if org is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return
    if await _member_role_id(db_session, user_id, org_id) is None:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")


async def _require_staff(db_session: AsyncSession, user_id: int, org_id: int) -> None:
    if not await _is_staff(db_session, user_id, org_id):
        raise HTTPException(status_code=403, detail="Only organization admins and maintainers can manage support tickets")


async def _load_ticket(db_session: AsyncSession, ticket_uuid: str) -> SupportTicket:
    ticket = (
        await db_session.execute(select(SupportTicket).where(SupportTicket.ticket_uuid == ticket_uuid))
    ).scalars().first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


async def _load_visible_ticket(
    db_session: AsyncSession, ticket_uuid: str, user_id: int
) -> tuple[SupportTicket, bool]:
    """Return (ticket, caller_is_staff). 404 if the caller may not see it."""
    ticket = await _load_ticket(db_session, ticket_uuid)
    staff = await _is_staff(db_session, user_id, ticket.org_id)
    if not staff and ticket.user_id != user_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket, staff


# ---------------------------------------------------------------------------
# Serialization helpers (batched to avoid N+1 queries on list endpoints)
# ---------------------------------------------------------------------------

def _author(user: Optional[User]) -> Optional[UserReadAuthor]:
    if user is None:
        return None
    return UserReadAuthor(**{name: getattr(user, name) for name in UserReadAuthor.model_fields})


async def _users_by_id(db_session: AsyncSession, ids: Iterable[Optional[int]]) -> Dict[int, User]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = (await db_session.execute(select(User).where(User.id.in_(wanted)))).scalars().all()
    return {u.id: u for u in rows}


async def _courses_by_id(db_session: AsyncSession, ids: Iterable[Optional[int]]) -> Dict[int, Course]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = (await db_session.execute(select(Course).where(Course.id.in_(wanted)))).scalars().all()
    return {c.id: c for c in rows}


async def _message_counts(
    db_session: AsyncSession, ticket_ids: List[int], include_internal: bool
) -> Dict[int, int]:
    if not ticket_ids:
        return {}
    stmt = (
        select(TicketMessage.ticket_id, func.count(TicketMessage.id))
        .where(TicketMessage.ticket_id.in_(ticket_ids))
        .group_by(TicketMessage.ticket_id)
    )
    if not include_internal:
        stmt = stmt.where(TicketMessage.is_internal == False)  # noqa: E712
    rows = (await db_session.execute(stmt)).all()
    return {ticket_id: count for ticket_id, count in rows}


async def _serialize_tickets(
    db_session: AsyncSession, tickets: List[SupportTicket], include_internal: bool
) -> List[SupportTicketRead]:
    users = await _users_by_id(db_session, [t.user_id for t in tickets] + [t.assigned_to for t in tickets])
    courses = await _courses_by_id(db_session, [t.course_id for t in tickets])
    counts = await _message_counts(db_session, [t.id for t in tickets], include_internal)

    out: List[SupportTicketRead] = []
    for t in tickets:
        course = courses.get(t.course_id) if t.course_id else None
        out.append(
            SupportTicketRead(
                **t.model_dump(),
                author=_author(users.get(t.user_id)),
                assignee=_author(users.get(t.assigned_to)) if t.assigned_to else None,
                course=TicketCourseRef(id=course.id, course_uuid=course.course_uuid, name=course.name) if course else None,
                message_count=counts.get(t.id, 0),
            )
        )
    return out


def _serialize_message(
    msg: TicketMessage,
    author: Optional[User],
    attachments: Optional[List[TicketAttachmentRead]] = None,
) -> TicketMessageRead:
    return TicketMessageRead(**msg.model_dump(), author=_author(author), attachments=attachments or [])


# ---------------------------------------------------------------------------
# Learner operations
# ---------------------------------------------------------------------------

async def create_support_ticket(
    db_session: AsyncSession,
    ticket_in: SupportTicketCreate,
    current_user: CurrentUser,
) -> SupportTicketRead:
    user_id = _acting_user_id(current_user)
    await _require_member(db_session, user_id, ticket_in.org_id)

    # SECURITY: course_id is client-supplied. Without this check a learner could
    # attach a ticket to a course in another tenant by guessing its id.
    if ticket_in.course_id is not None:
        course = (
            await db_session.execute(select(Course).where(Course.id == ticket_in.course_id))
        ).scalars().first()
        if course is None or course.org_id != ticket_in.org_id:
            raise HTTPException(status_code=400, detail="Course does not belong to this organization")

    now = _now()
    ticket = SupportTicket(
        ticket_uuid=f"ticket_{uuid4()}",
        org_id=ticket_in.org_id,
        user_id=user_id,
        subject=ticket_in.subject.strip(),
        description=ticket_in.description.strip(),
        category=ticket_in.category,
        priority=TicketPriorityEnum.MEDIUM,
        status=TicketStatusEnum.OPEN,
        course_id=ticket_in.course_id,
        creation_date=now,
        update_date=now,
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)
    return (await _serialize_tickets(db_session, [ticket], include_internal=False))[0]


async def get_user_tickets(
    db_session: AsyncSession,
    org_id: int,
    current_user: CurrentUser,
) -> List[SupportTicketRead]:
    user_id = _acting_user_id(current_user)
    await _require_member(db_session, user_id, org_id)
    tickets = (
        await db_session.execute(
            select(SupportTicket)
            .where(SupportTicket.org_id == org_id)
            .where(SupportTicket.user_id == user_id)
            .order_by(SupportTicket.creation_date.desc())
        )
    ).scalars().all()
    return await _serialize_tickets(db_session, list(tickets), include_internal=False)


async def get_ticket_detail(
    db_session: AsyncSession,
    ticket_uuid: str,
    current_user: CurrentUser,
) -> SupportTicketDetail:
    user_id = _acting_user_id(current_user)
    ticket, staff = await _load_visible_ticket(db_session, ticket_uuid, user_id)

    stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket.id)
    if not staff:
        stmt = stmt.where(TicketMessage.is_internal == False)  # noqa: E712
    messages = list(
        (await db_session.execute(stmt.order_by(TicketMessage.creation_date.asc(), TicketMessage.id.asc()))).scalars().all()
    )

    base = (await _serialize_tickets(db_session, [ticket], include_internal=staff))[0]
    authors = await _users_by_id(db_session, [m.author_id for m in messages])
    ticket_level, by_message = await attachments_for(db_session, ticket, include_internal=staff)
    return SupportTicketDetail(
        **base.model_dump(),
        attachments=ticket_level,
        messages=[
            _serialize_message(m, authors.get(m.author_id), by_message.get(m.id, []))
            for m in messages
        ],
    )


async def add_ticket_message(
    db_session: AsyncSession,
    ticket_uuid: str,
    msg_in: TicketMessageCreate,
    current_user: CurrentUser,
) -> TicketMessageRead:
    user_id = _acting_user_id(current_user)
    ticket, staff = await _load_visible_ticket(db_session, ticket_uuid, user_id)

    if ticket.status == TicketStatusEnum.CLOSED:
        raise HTTPException(status_code=409, detail="This ticket is closed. Open a new ticket if you still need help.")
    if msg_in.is_internal and not staff:
        raise HTTPException(status_code=403, detail="Only staff can add internal notes")

    # Validated before anything is written, so a bad uuid leaves no message behind.
    claimed = await claim_pending_attachments(
        db_session, ticket, msg_in.attachment_uuids, user_id, msg_in.is_internal
    )

    is_owner = ticket.user_id == user_id
    now = _now()
    message = TicketMessage(
        message_uuid=f"ticketmsg_{uuid4()}",
        ticket_id=ticket.id,
        author_id=user_id,
        content=msg_in.content.strip(),
        # Staff filing their own ticket are acting as a requester, not as support.
        is_staff=staff and not is_owner,
        is_internal=msg_in.is_internal,
        creation_date=now,
    )
    db_session.add(message)

    # A learner replying to a resolved ticket means it isn't resolved: reopen it.
    if is_owner and not msg_in.is_internal and ticket.status == TicketStatusEnum.RESOLVED:
        ticket.status = TicketStatusEnum.OPEN
    ticket.update_date = now
    db_session.add(ticket)

    if claimed:
        await db_session.flush()  # assigns message.id
        for row in claimed:
            row.attached = True
            row.message_id = message.id
            db_session.add(row)

    await db_session.commit()
    await db_session.refresh(message)
    author = (await _users_by_id(db_session, [user_id])).get(user_id)
    return _serialize_message(message, author, await read_attachments(db_session, ticket, claimed))


# ---------------------------------------------------------------------------
# Staff operations
# ---------------------------------------------------------------------------

async def get_org_tickets_admin(
    db_session: AsyncSession,
    org_id: int,
    current_user: CurrentUser,
    status: Optional[TicketStatusEnum] = None,
    priority: Optional[TicketPriorityEnum] = None,
    category: Optional[TicketCategoryEnum] = None,
    assigned_to: Optional[int] = None,
    page: int = 1,
    limit: int = 25,
) -> SupportTicketPage:
    user_id = _acting_user_id(current_user)
    await _require_staff(db_session, user_id, org_id)

    page = max(page, 1)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)

    filters = [SupportTicket.org_id == org_id]
    if status is not None:
        filters.append(SupportTicket.status == status)
    if priority is not None:
        filters.append(SupportTicket.priority == priority)
    if category is not None:
        filters.append(SupportTicket.category == category)
    if assigned_to is not None:
        filters.append(SupportTicket.assigned_to == assigned_to)

    total = (
        await db_session.execute(select(func.count(SupportTicket.id)).where(*filters))
    ).scalar_one()
    tickets = (
        await db_session.execute(
            select(SupportTicket)
            .where(*filters)
            .order_by(SupportTicket.creation_date.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    items = await _serialize_tickets(db_session, list(tickets), include_internal=True)
    return SupportTicketPage(items=items, total=total, page=page, limit=limit)


async def update_support_ticket(
    db_session: AsyncSession,
    ticket_uuid: str,
    update_in: SupportTicketUpdate,
    current_user: CurrentUser,
) -> SupportTicketRead:
    user_id = _acting_user_id(current_user)
    ticket = await _load_ticket(db_session, ticket_uuid)
    if not await _is_staff(db_session, user_id, ticket.org_id):
        # Same 404 as a missing ticket: don't reveal tickets in other orgs.
        raise HTTPException(status_code=404, detail="Ticket not found")

    sent = update_in.model_fields_set

    if "status" in sent and update_in.status is not None:
        ticket.status = update_in.status
    if "priority" in sent and update_in.priority is not None:
        ticket.priority = update_in.priority
    if "assigned_to" in sent:
        if update_in.assigned_to is not None and not await _is_staff(
            db_session, update_in.assigned_to, ticket.org_id
        ):
            raise HTTPException(status_code=400, detail="Tickets can only be assigned to admins or maintainers of this organization")
        ticket.assigned_to = update_in.assigned_to
    if "resolution_note" in sent:
        note = (update_in.resolution_note or "").strip()
        ticket.resolution_note = note or None

    ticket.update_date = _now()
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)
    return (await _serialize_tickets(db_session, [ticket], include_internal=True))[0]
