from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

# Same image rules as community media (src/services/communities/media.py).
TICKET_IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")
TICKET_IMAGE_MAX_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_MESSAGE = 5
# Uploaded-but-not-yet-sent files per user per ticket. Stops one user from
# filling storage through a ticket they can see.
MAX_PENDING_PER_USER = 20


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TicketAttachment(SQLModel, table=True):
    """One uploaded image.

    ``attached`` is False between upload and the reply that uses it. Ticket-level
    images (raised with the ticket) are attached with ``message_id`` NULL.
    Access to the file itself is enforced by src/security/ticket_file_access.py.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    attachment_uuid: str = Field(index=True, unique=True)
    ticket_id: int = Field(
        sa_column=Column(Integer, ForeignKey("supportticket.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    message_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("ticketmessage.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    uploader_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    file_id: str
    content_type: str
    size: int
    is_internal: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    attached: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    creation_date: str = Field(default_factory=_utcnow_iso)


class TicketAttachmentRead(SQLModel):
    attachment_uuid: str
    # Content-relative path, e.g. orgs/{org}/tickets/{ticket}/{file}; the client
    # loads it from `${mediaUrl}content/${file_path}` with its bearer token.
    file_path: str
    content_type: str
    size: int
    is_internal: bool
