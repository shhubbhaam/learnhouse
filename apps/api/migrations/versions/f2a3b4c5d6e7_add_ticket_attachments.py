"""add_ticket_attachments

Revision ID: f2a3b4c5d6e7
Revises: e1ebd9e62249
Create Date: 2026-10-31 21:30:00

Private image attachments on support tickets and replies.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1ebd9e62249'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing(bind):
    """Tables and indexes already present.

    The API's startup runs SQLModel.metadata.create_all, so a dev server started
    before this migration has already created these tables. Skip what exists.
    """
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    indexes = {
        (t, ix["name"]) for t in tables for ix in inspector.get_indexes(t)
    }
    return tables, indexes


def upgrade() -> None:
    tables, indexes = _existing(op.get_bind())
    if 'ticketattachment' not in tables:
        op.create_table(
            'ticketattachment',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('attachment_uuid', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('ticket_id', sa.Integer(), nullable=False),
            sa.Column('message_id', sa.Integer(), nullable=True),
            sa.Column('uploader_id', sa.Integer(), nullable=False),
            sa.Column('file_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('size', sa.Integer(), nullable=False),
            sa.Column('is_internal', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('attached', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('creation_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.ForeignKeyConstraint(['ticket_id'], ['supportticket.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['message_id'], ['ticketmessage.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['uploader_id'], ['user.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
    for name, cols, unique in [
        ('ix_ticketattachment_attachment_uuid', ['attachment_uuid'], True),
        ('ix_ticketattachment_ticket_id', ['ticket_id'], False),
        ('ix_ticketattachment_message_id', ['message_id'], False),
    ]:
        if ('ticketattachment', name) not in indexes:
            op.create_index(name, 'ticketattachment', cols, unique=unique)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS ticketattachment')
