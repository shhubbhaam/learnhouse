from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text
from sqlmodel import Field, SQLModel

from src.db.tickets.tickets import DESCRIPTION_MAX_LENGTH, SupportTicketRead
from src.db.users import UserReadAuthor


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TicketMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    message_uuid: str = Field(index=True, unique=True)
    ticket_id: int = Field(
        sa_column=Column(Integer, ForeignKey("supportticket.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    # True when written by org staff (admin/maintainer/superadmin) on someone
    # else's ticket. Lets the UI style replies without a role lookup.
    is_staff: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    # Staff-only note. Never returned to the ticket owner.
    is_internal: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    creation_date: str = Field(default_factory=_utcnow_iso)


class TicketMessageCreate(SQLModel):
    content: str = Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    is_internal: bool = False


class TicketMessageRead(SQLModel):
    id: int
    message_uuid: str
    ticket_id: int
    author_id: int
    content: str
    is_staff: bool
    is_internal: bool
    creation_date: str
    author: Optional[UserReadAuthor] = None


class SupportTicketDetail(SupportTicketRead):
    messages: List[TicketMessageRead] = []
