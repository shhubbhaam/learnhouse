"""Add course-level weighted grading

Adds two tables and three nullable columns:

- ``coursegradecategory``    : weighted groups of assignments within a course
                               (name, weight %, drop_lowest, position).
- ``coursegradingsettings``  : one row per course that opted in (grading mode,
                               final grade type, pass mark, missing-work policy,
                               certificate rule).
- ``assignment.grade_category_id`` : FK to the category (SET NULL on delete).
- ``assignment.category_weight``   : weight inside the category (default 1).
- ``assignment.never_drop``        : exempt from the category's drop_lowest.

A course without a settings row keeps the legacy behaviour (every assignment
must pass), so existing courses are unchanged.

The three new enum columns are native enums, matching what ``create_all``
builds; ``final_grading_type`` reuses the existing ``gradingtypeenum`` type.

Revision ID: g7h8i9j0k1l2
Revises: f2a3b4c5d6e7
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GRADING_MODE_ENUM = postgresql.ENUM(
    'ALL_MUST_PASS', 'WEIGHTED', name='gradingmodeenum', create_type=False
)
MISSING_POLICY_ENUM = postgresql.ENUM(
    'ZERO_AFTER_DUE', 'EXCLUDE', name='missingworkpolicyenum', create_type=False
)
CERTIFICATE_RULE_ENUM = postgresql.ENUM(
    'ALL_ASSIGNMENTS', 'FINAL_GRADE', 'BOTH', name='certificateruleenum', create_type=False
)
# Already exists (assignment.grading_type); never created or dropped here.
GRADING_TYPE_ENUM = postgresql.ENUM(
    'ALPHABET', 'NUMERIC', 'PERCENTAGE', 'PASS_FAIL', 'GPA_SCALE',
    name='gradingtypeenum', create_type=False,
)


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    return any(c['name'] == column for c in sa.inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (GRADING_MODE_ENUM, MISSING_POLICY_ENUM, CERTIFICATE_RULE_ENUM):
        enum.create(bind, checkfirst=True)

    if not _has_table('coursegradecategory'):
        op.create_table(
            'coursegradecategory',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('category_uuid', sa.String(), nullable=False),
            sa.Column(
                'course_id', sa.Integer(),
                sa.ForeignKey('course.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('weight', sa.Float(), nullable=False, server_default='0'),
            sa.Column('drop_lowest', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('creation_date', sa.String(), nullable=True),
            sa.Column('update_date', sa.String(), nullable=True),
        )
        op.create_index(
            'ix_coursegradecategory_category_uuid', 'coursegradecategory',
            ['category_uuid'], unique=True,
        )
        op.create_index(
            'ix_coursegradecategory_course_id', 'coursegradecategory', ['course_id'],
        )

    if not _has_table('coursegradingsettings'):
        op.create_table(
            'coursegradingsettings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column(
                'course_id', sa.Integer(),
                sa.ForeignKey('course.id', ondelete='CASCADE'),
                nullable=False, unique=True,
            ),
            sa.Column(
                'grading_mode', GRADING_MODE_ENUM, nullable=False,
                server_default='ALL_MUST_PASS',
            ),
            sa.Column(
                'final_grading_type', GRADING_TYPE_ENUM, nullable=False,
                server_default='PERCENTAGE',
            ),
            sa.Column('final_pass_threshold', sa.Float(), nullable=True),
            sa.Column(
                'missing_policy', MISSING_POLICY_ENUM, nullable=False,
                server_default='ZERO_AFTER_DUE',
            ),
            sa.Column(
                'certificate_rule', CERTIFICATE_RULE_ENUM, nullable=False,
                server_default='ALL_ASSIGNMENTS',
            ),
            sa.Column('creation_date', sa.String(), nullable=True),
            sa.Column('update_date', sa.String(), nullable=True),
        )

    if not _has_column('assignment', 'grade_category_id'):
        op.add_column(
            'assignment',
            sa.Column(
                'grade_category_id', sa.Integer(),
                sa.ForeignKey(
                    'coursegradecategory.id', ondelete='SET NULL',
                    name='fk_assignment_grade_category_id',
                ),
                nullable=True,
            ),
        )
        op.create_index(
            'ix_assignment_grade_category_id', 'assignment', ['grade_category_id'],
        )
    if not _has_column('assignment', 'category_weight'):
        op.add_column(
            'assignment',
            sa.Column('category_weight', sa.Float(), nullable=True, server_default='1'),
        )
    if not _has_column('assignment', 'never_drop'):
        op.add_column(
            'assignment',
            sa.Column('never_drop', sa.Boolean(), nullable=True, server_default=sa.false()),
        )


def downgrade() -> None:
    if _has_column('assignment', 'never_drop'):
        op.drop_column('assignment', 'never_drop')
    if _has_column('assignment', 'category_weight'):
        op.drop_column('assignment', 'category_weight')
    if _has_column('assignment', 'grade_category_id'):
        op.drop_index('ix_assignment_grade_category_id', table_name='assignment')
        op.drop_constraint('fk_assignment_grade_category_id', 'assignment', type_='foreignkey')
        op.drop_column('assignment', 'grade_category_id')

    if _has_table('coursegradingsettings'):
        op.drop_table('coursegradingsettings')
    if _has_table('coursegradecategory'):
        op.drop_index('ix_coursegradecategory_course_id', table_name='coursegradecategory')
        op.drop_index('ix_coursegradecategory_category_uuid', table_name='coursegradecategory')
        op.drop_table('coursegradecategory')

    bind = op.get_bind()
    for enum in (CERTIFICATE_RULE_ENUM, MISSING_POLICY_ENUM, GRADING_MODE_ENUM):
        enum.drop(bind, checkfirst=True)
