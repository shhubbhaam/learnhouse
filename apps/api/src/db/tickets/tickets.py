from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import ConfigDict
from sqlalchemy import Column, ForeignKey, Index, Integer, Text
from sqlmodel import Field, SQLModel

from src.db.users import UserReadAuthor


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TicketStatusEnum(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriorityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategoryEnum(str, Enum):
    TECHNICAL = "TECHNICAL"
    COURSE_CONTENT = "COURSE_CONTENT"
    BILLING = "BILLING"
    ACCOUNT = "ACCOUNT"
    OTHER = "OTHER"


SUBJECT_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 10_000


class SupportTicket(SQLModel, table=True):
    __table_args__ = (
        Index("ix_supportticket_org_status", "org_id", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_uuid: str = Field(index=True, unique=True)
    subject: str
    description: str = Field(sa_column=Column(Text, nullable=False))
    category: TicketCategoryEnum = Field(default=TicketCategoryEnum.OTHER)
    priority: TicketPriorityEnum = Field(default=TicketPriorityEnum.MEDIUM)
    status: TicketStatusEnum = Field(default=TicketStatusEnum.OPEN, index=True)
    resolution_note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    course_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="SET NULL"), nullable=True),
    )
    assigned_to: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    creation_date: str = Field(default_factory=_utcnow_iso)
    update_date: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------

class SupportTicketCreate(SQLModel):
    """Learner-submitted ticket. Priority is deliberately absent: staff set it
    during triage so learners cannot self-escalate everything to URGENT."""
    model_config = ConfigDict(str_strip_whitespace=True)

    org_id: int
    subject: str = Field(min_length=3, max_length=SUBJECT_MAX_LENGTH)
    description: str = Field(min_length=10, max_length=DESCRIPTION_MAX_LENGTH)
    category: TicketCategoryEnum = TicketCategoryEnum.OTHER
    course_id: Optional[int] = None


class SupportTicketUpdate(SQLModel):
    """Staff-only triage update. Every field is optional; only sent fields change."""
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Optional[TicketStatusEnum] = None
    priority: Optional[TicketPriorityEnum] = None
    assigned_to: Optional[int] = None
    resolution_note: Optional[str] = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)


class TicketCourseRef(SQLModel):
    id: int
    course_uuid: str
    name: str


class SupportTicketRead(SQLModel):
    id: int
    ticket_uuid: str
    org_id: int
    subject: str
    description: str
    category: TicketCategoryEnum
    priority: TicketPriorityEnum
    status: TicketStatusEnum
    resolution_note: Optional[str] = None
    user_id: int
    course_id: Optional[int] = None
    assigned_to: Optional[int] = None
    creation_date: str
    update_date: str
    author: Optional[UserReadAuthor] = None
    assignee: Optional[UserReadAuthor] = None
    course: Optional[TicketCourseRef] = None
    message_count: int = 0


class SupportTicketPage(SQLModel):
    items: List[SupportTicketRead]
    total: int
    page: int
    limit: int
