"""Service tests for src/services/tickets/tickets.py.

Focus: org scoping, staff-only operations, internal-note visibility and the
status side effects of replies.
"""

from datetime import datetime

import pytest
from fastapi import HTTPException

from src.db.courses.courses import Course
from src.db.tickets.ticket_messages import TicketMessage, TicketMessageCreate  # noqa: F401 (registers table)
from src.db.tickets.tickets import (
    SupportTicketCreate,
    SupportTicketUpdate,
    TicketCategoryEnum,
    TicketPriorityEnum,
    TicketStatusEnum,
)
from src.db.user_organizations import UserOrganization
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User
from src.services.tickets.tickets import (
    add_ticket_message,
    create_support_ticket,
    get_org_tickets_admin,
    get_ticket_detail,
    get_user_tickets,
    update_support_ticket,
)


async def _make_user(db, user_id, username, org_id=None, role_id=None, superadmin=False) -> PublicUser:
    u = User(
        id=user_id,
        username=username,
        first_name=username.title(),
        last_name="Test",
        email=f"{username}@test.com",
        password="hashed_password",
        user_uuid=f"user_{username}",
        is_superadmin=superadmin,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(u)
    await db.commit()
    if org_id is not None:
        db.add(UserOrganization(
            user_id=user_id, org_id=org_id, role_id=role_id,
            creation_date=str(datetime.now()), update_date=str(datetime.now()),
        ))
        await db.commit()
    return PublicUser(
        id=u.id, username=u.username, first_name=u.first_name, last_name=u.last_name,
        email=u.email, user_uuid=u.user_uuid,
    )


def _ticket_in(org_id=1, **overrides) -> SupportTicketCreate:
    data = dict(
        org_id=org_id,
        subject="Video won't play",
        description="The lesson video shows a black screen on Chrome.",
        category=TicketCategoryEnum.TECHNICAL,
    )
    data.update(overrides)
    return SupportTicketCreate(**data)


@pytest.fixture
async def maintainer_user(db, org, admin_role):
    # Role id 2 is MAINTAINER_ROLE_ID; the FK target only needs to exist for
    # SQLite, which doesn't enforce it, so we don't create a Role row.
    return await _make_user(db, 20, "maintainer", org_id=org.id, role_id=2)


@pytest.fixture
async def outsider(db, other_org, admin_role):
    # Admin of a DIFFERENT org: must get nothing from org 1.
    return await _make_user(db, 30, "outsider", org_id=other_org.id, role_id=1)


@pytest.fixture
async def other_learner(db, org, user_role):
    return await _make_user(db, 40, "otherlearner", org_id=org.id, role_id=4)


@pytest.fixture
async def ticket(db, org, regular_user):
    return await create_support_ticket(db, _ticket_in(org.id), regular_user)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestCreate:
    async def test_member_creates_open_medium_ticket(self, db, org, regular_user):
        t = await create_support_ticket(db, _ticket_in(org.id), regular_user)
        assert t.ticket_uuid.startswith("ticket_")
        assert t.status == TicketStatusEnum.OPEN
        assert t.priority == TicketPriorityEnum.MEDIUM
        assert t.user_id == regular_user.id
        assert t.author.username == "regular"
        assert not hasattr(t.author, "email")

    async def test_non_member_rejected(self, db, org, outsider):
        with pytest.raises(HTTPException) as exc:
            await create_support_ticket(db, _ticket_in(org.id), outsider)
        assert exc.value.status_code == 403

    async def test_course_from_other_org_rejected(self, db, org, other_org, regular_user):
        db.add(Course(
            id=99, name="Foreign", description="", public=True, published=True,
            open_to_contributors=False, org_id=other_org.id, course_uuid="course_foreign",
            creation_date=str(datetime.now()), update_date=str(datetime.now()),
        ))
        await db.commit()
        with pytest.raises(HTTPException) as exc:
            await create_support_ticket(db, _ticket_in(org.id, course_id=99), regular_user)
        assert exc.value.status_code == 400

    async def test_course_in_same_org_attached(self, db, org, course, regular_user):
        t = await create_support_ticket(db, _ticket_in(org.id, course_id=course.id), regular_user)
        assert t.course is not None and t.course.course_uuid == course.course_uuid

    async def test_anonymous_and_api_token_rejected(self, db, org):
        with pytest.raises(HTTPException) as exc:
            await create_support_ticket(db, _ticket_in(org.id), AnonymousUser())
        assert exc.value.status_code == 401
        token_user = APITokenUser.model_construct(id=0, created_by_user_id=1, org_id=org.id)
        with pytest.raises(HTTPException) as exc:
            await create_support_ticket(db, _ticket_in(org.id), token_user)
        assert exc.value.status_code == 403

    def test_learner_cannot_set_priority(self):
        assert "priority" not in SupportTicketCreate.model_fields


# ---------------------------------------------------------------------------
# visibility
# ---------------------------------------------------------------------------

class TestVisibility:
    async def test_my_tickets_only_returns_own(self, db, org, ticket, regular_user, other_learner):
        await create_support_ticket(db, _ticket_in(org.id, subject="Someone else's"), other_learner)
        mine = await get_user_tickets(db, org.id, regular_user)
        assert [t.ticket_uuid for t in mine] == [ticket.ticket_uuid]

    async def test_other_learner_gets_404(self, db, ticket, other_learner):
        with pytest.raises(HTTPException) as exc:
            await get_ticket_detail(db, ticket.ticket_uuid, other_learner)
        assert exc.value.status_code == 404

    async def test_admin_of_other_org_gets_404(self, db, ticket, outsider):
        with pytest.raises(HTTPException) as exc:
            await get_ticket_detail(db, ticket.ticket_uuid, outsider)
        assert exc.value.status_code == 404

    async def test_internal_notes_hidden_from_owner(self, db, ticket, regular_user, admin_user):
        await add_ticket_message(db, ticket.ticket_uuid, TicketMessageCreate(content="Public reply"), admin_user)
        await add_ticket_message(
            db, ticket.ticket_uuid, TicketMessageCreate(content="Staff only", is_internal=True), admin_user
        )
        owner_view = await get_ticket_detail(db, ticket.ticket_uuid, regular_user)
        staff_view = await get_ticket_detail(db, ticket.ticket_uuid, admin_user)
        assert [m.content for m in owner_view.messages] == ["Public reply"]
        assert owner_view.message_count == 1
        assert [m.content for m in staff_view.messages] == ["Public reply", "Staff only"]
        assert staff_view.message_count == 2


# ---------------------------------------------------------------------------
# replies
# ---------------------------------------------------------------------------

class TestReplies:
    async def test_staff_reply_flagged_is_staff(self, db, ticket, maintainer_user):
        m = await add_ticket_message(db, ticket.ticket_uuid, TicketMessageCreate(content="On it"), maintainer_user)
        assert m.is_staff is True

    async def test_owner_reply_not_staff(self, db, ticket, regular_user):
        m = await add_ticket_message(db, ticket.ticket_uuid, TicketMessageCreate(content="More info"), regular_user)
        assert m.is_staff is False

    async def test_learner_cannot_post_internal(self, db, ticket, regular_user):
        with pytest.raises(HTTPException) as exc:
            await add_ticket_message(
                db, ticket.ticket_uuid, TicketMessageCreate(content="x", is_internal=True), regular_user
            )
        assert exc.value.status_code == 403

    async def test_owner_reply_reopens_resolved(self, db, ticket, regular_user, admin_user):
        await update_support_ticket(
            db, ticket.ticket_uuid, SupportTicketUpdate(status=TicketStatusEnum.RESOLVED), admin_user
        )
        await add_ticket_message(db, ticket.ticket_uuid, TicketMessageCreate(content="Still broken"), regular_user)
        detail = await get_ticket_detail(db, ticket.ticket_uuid, regular_user)
        assert detail.status == TicketStatusEnum.OPEN

    async def test_closed_ticket_rejects_replies(self, db, ticket, regular_user, admin_user):
        await update_support_ticket(
            db, ticket.ticket_uuid, SupportTicketUpdate(status=TicketStatusEnum.CLOSED), admin_user
        )
        for who in (regular_user, admin_user):
            with pytest.raises(HTTPException) as exc:
                await add_ticket_message(db, ticket.ticket_uuid, TicketMessageCreate(content="hi"), who)
            assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# staff queue + triage
# ---------------------------------------------------------------------------

class TestStaff:
    async def test_learner_cannot_list_queue(self, db, org, regular_user):
        with pytest.raises(HTTPException) as exc:
            await get_org_tickets_admin(db, org.id, regular_user)
        assert exc.value.status_code == 403

    async def test_other_org_admin_cannot_list_queue(self, db, org, outsider):
        with pytest.raises(HTTPException) as exc:
            await get_org_tickets_admin(db, org.id, outsider)
        assert exc.value.status_code == 403

    async def test_maintainer_can_list_and_filter(self, db, org, regular_user, maintainer_user):
        await create_support_ticket(db, _ticket_in(org.id, category=TicketCategoryEnum.BILLING), regular_user)
        await create_support_ticket(db, _ticket_in(org.id, category=TicketCategoryEnum.TECHNICAL), regular_user)
        page = await get_org_tickets_admin(db, org.id, maintainer_user, category=TicketCategoryEnum.BILLING)
        assert page.total == 1
        assert page.items[0].category == TicketCategoryEnum.BILLING

    async def test_pagination(self, db, org, regular_user, admin_user):
        for i in range(5):
            await create_support_ticket(db, _ticket_in(org.id, subject=f"Ticket {i}"), regular_user)
        page = await get_org_tickets_admin(db, org.id, admin_user, page=2, limit=2)
        assert page.total == 5 and len(page.items) == 2 and page.page == 2

    async def test_superadmin_can_list_any_org(self, db, org, ticket):
        root = await _make_user(db, 50, "root", superadmin=True)
        page = await get_org_tickets_admin(db, org.id, root)
        assert page.total == 1

    async def test_triage_update(self, db, ticket, admin_user, maintainer_user):
        updated = await update_support_ticket(
            db,
            ticket.ticket_uuid,
            SupportTicketUpdate(
                status=TicketStatusEnum.RESOLVED,
                priority=TicketPriorityEnum.HIGH,
                assigned_to=maintainer_user.id,
                resolution_note="  Cleared the CDN cache.  ",
            ),
            admin_user,
        )
        assert updated.status == TicketStatusEnum.RESOLVED
        assert updated.priority == TicketPriorityEnum.HIGH
        assert updated.assignee.username == "maintainer"
        assert updated.resolution_note == "Cleared the CDN cache."

    async def test_unassign_with_explicit_null(self, db, ticket, admin_user, maintainer_user):
        await update_support_ticket(db, ticket.ticket_uuid, SupportTicketUpdate(assigned_to=maintainer_user.id), admin_user)
        updated = await update_support_ticket(db, ticket.ticket_uuid, SupportTicketUpdate(assigned_to=None), admin_user)
        assert updated.assigned_to is None
        # Omitting the field leaves it alone.
        await update_support_ticket(db, ticket.ticket_uuid, SupportTicketUpdate(assigned_to=maintainer_user.id), admin_user)
        updated = await update_support_ticket(db, ticket.ticket_uuid, SupportTicketUpdate(priority=TicketPriorityEnum.LOW), admin_user)
        assert updated.assigned_to == maintainer_user.id

    async def test_cannot_assign_to_learner(self, db, ticket, admin_user, other_learner):
        with pytest.raises(HTTPException) as exc:
            await update_support_ticket(db, ticket.ticket_uuid, SupportTicketUpdate(assigned_to=other_learner.id), admin_user)
        assert exc.value.status_code == 400

    async def test_cannot_assign_to_other_org_admin(self, db, ticket, admin_user, outsider):
        with pytest.raises(HTTPException) as exc:
            await update_support_ticket(db, ticket.ticket_uuid, SupportTicketUpdate(assigned_to=outsider.id), admin_user)
        assert exc.value.status_code == 400

    async def test_learner_and_outsider_cannot_update(self, db, ticket, regular_user, outsider):
        for who in (regular_user, outsider):
            with pytest.raises(HTTPException) as exc:
                await update_support_ticket(
                    db, ticket.ticket_uuid, SupportTicketUpdate(status=TicketStatusEnum.CLOSED), who
                )
            assert exc.value.status_code == 404
