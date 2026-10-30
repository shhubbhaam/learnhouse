"""Help & Support ticket endpoints.

Mounted behind ``require_authenticated_user`` in src/router.py (rejects
anonymous callers and API tokens). Org scoping and staff checks live in
src/services/tickets/tickets.py.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.tickets.ticket_messages import (
    SupportTicketDetail,
    TicketMessageCreate,
    TicketMessageRead,
)
from src.db.tickets.tickets import (
    SupportTicketCreate,
    SupportTicketPage,
    SupportTicketRead,
    SupportTicketUpdate,
    TicketCategoryEnum,
    TicketPriorityEnum,
    TicketStatusEnum,
)
from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.services.tickets.tickets import (
    MAX_PAGE_SIZE,
    add_ticket_message,
    create_support_ticket,
    get_org_tickets_admin,
    get_ticket_detail,
    get_user_tickets,
    update_support_ticket,
)

router = APIRouter()


@router.post(
    "/",
    response_model=SupportTicketRead,
    summary="Raise a support ticket",
    description="Create a ticket in an organization the caller belongs to. Priority is set by staff during triage.",
    responses={
        400: {"description": "Course does not belong to the organization"},
        403: {"description": "Caller is not a member of the organization"},
    },
)
async def api_create_ticket(
    ticket_in: SupportTicketCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SupportTicketRead:
    return await create_support_ticket(db_session, ticket_in, current_user)


@router.get(
    "/org/{org_id}/me",
    response_model=List[SupportTicketRead],
    summary="List my tickets",
    description="The caller's own tickets in this organization, newest first.",
)
async def api_get_my_tickets(
    org_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[SupportTicketRead]:
    return await get_user_tickets(db_session, org_id, current_user)


@router.get(
    "/org/{org_id}/admin",
    response_model=SupportTicketPage,
    summary="Support queue (staff)",
    description="All tickets in the organization with optional filters. Org admins and maintainers only.",
    responses={403: {"description": "Caller is not an org admin or maintainer"}},
)
async def api_get_org_tickets(
    org_id: int,
    status: Optional[TicketStatusEnum] = None,
    priority: Optional[TicketPriorityEnum] = None,
    category: Optional[TicketCategoryEnum] = None,
    assigned_to: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SupportTicketPage:
    return await get_org_tickets_admin(
        db_session,
        org_id,
        current_user,
        status=status,
        priority=priority,
        category=category,
        assigned_to=assigned_to,
        page=page,
        limit=limit,
    )


@router.get(
    "/{ticket_uuid}",
    response_model=SupportTicketDetail,
    summary="Get a ticket with its thread",
    description="Visible to the ticket owner and org staff. Internal notes are only returned to staff.",
    responses={404: {"description": "Ticket not found or not visible to the caller"}},
)
async def api_get_ticket(
    ticket_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SupportTicketDetail:
    return await get_ticket_detail(db_session, ticket_uuid, current_user)


@router.patch(
    "/{ticket_uuid}",
    response_model=SupportTicketRead,
    summary="Triage a ticket (staff)",
    description="Update status, priority, assignee or resolution note. Org admins and maintainers only.",
    responses={
        400: {"description": "Assignee is not staff in this organization"},
        404: {"description": "Ticket not found or caller is not staff"},
    },
)
async def api_update_ticket(
    ticket_uuid: str,
    update_in: SupportTicketUpdate,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SupportTicketRead:
    return await update_support_ticket(db_session, ticket_uuid, update_in, current_user)


@router.post(
    "/{ticket_uuid}/messages",
    response_model=TicketMessageRead,
    summary="Reply to a ticket",
    description="Owner or staff can reply. Staff may post internal notes. Closed tickets reject replies; a learner reply reopens a resolved ticket.",
    responses={
        403: {"description": "Non-staff tried to post an internal note"},
        404: {"description": "Ticket not found or not visible to the caller"},
        409: {"description": "Ticket is closed"},
    },
)
async def api_reply_to_ticket(
    ticket_uuid: str,
    msg_in: TicketMessageCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> TicketMessageRead:
    return await add_ticket_message(db_session, ticket_uuid, msg_in, current_user)
