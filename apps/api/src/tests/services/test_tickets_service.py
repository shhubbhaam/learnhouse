"""Service tests for src/services/tickets/tickets.py.

Focus: org scoping, staff-only operations, internal-note visibility and the
status side effects of replies.
"""

from datetime import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

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

    def test_whitespace_only_subject_rejected(self):
        with pytest.raises(ValidationError):
            SupportTicketCreate(org_id=1, subject="     ", description="A real description here.")

    def test_subject_is_trimmed(self):
        t = SupportTicketCreate(org_id=1, subject="  Video  ", description="A real description here.")
        assert t.subject == "Video"

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

    def test_whitespace_only_reply_rejected(self):
        with pytest.raises(ValidationError):
            TicketMessageCreate(content="   ")

    def test_empty_reply_without_attachments_rejected(self):
        with pytest.raises(ValidationError):
            TicketMessageCreate(content="")

    def test_images_only_reply_allowed(self):
        msg = TicketMessageCreate(content="", attachment_uuids=["ticketatt_1"])
        assert msg.attachment_uuids == ["ticketatt_1"]

    def test_more_than_five_attachments_rejected(self):
        with pytest.raises(ValidationError):
            TicketMessageCreate(content="x", attachment_uuids=[f"ticketatt_{i}" for i in range(6)])

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


# ---------------------------------------------------------------------------
# attachments
# ---------------------------------------------------------------------------

from io import BytesIO  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

from starlette.datastructures import Headers, UploadFile  # noqa: E402

from src.services.tickets.attachments import upload_ticket_attachment  # noqa: E402


def _png(name="shot.png") -> UploadFile:
    return UploadFile(file=BytesIO(b"\x89PNG fake"), filename=name, size=9,
                      headers=Headers({"content-type": "image/png"}))


@pytest.fixture
def stored_files():
    """Stub storage: each upload gets a unique stored filename."""
    counter = {"n": 0}

    async def fake_upload_file(**kwargs):
        counter["n"] += 1
        return f"file{counter['n']}_ticket.png"

    with patch("src.services.tickets.attachments.upload_file", side_effect=fake_upload_file) as mock:
        yield mock


async def _upload(db, ticket, who, *, internal=False, to_ticket=False):
    return await upload_ticket_attachment(db, ticket.ticket_uuid, _png(), internal, to_ticket, who)


class TestAttachmentUpload:
    async def test_owner_upload_is_pending_and_private_path(self, db, org, ticket, regular_user, stored_files):
        att = await _upload(db, ticket, regular_user)
        assert att.attachment_uuid.startswith("ticketatt_")
        assert att.file_path == f"orgs/{org.org_uuid}/tickets/{ticket.ticket_uuid}/file1_ticket.png"
        assert att.is_internal is False
        kwargs = stored_files.call_args.kwargs
        assert kwargs["directory"] == f"tickets/{ticket.ticket_uuid}"
        assert kwargs["allowed_types"] == ["image"]
        # Pending uploads are not shown on the ticket yet.
        detail = await get_ticket_detail(db, ticket.ticket_uuid, regular_user)
        assert detail.attachments == []

    async def test_attach_to_ticket_shows_under_description(self, db, ticket, regular_user, stored_files):
        att = await _upload(db, ticket, regular_user, to_ticket=True)
        detail = await get_ticket_detail(db, ticket.ticket_uuid, regular_user)
        assert [a.attachment_uuid for a in detail.attachments] == [att.attachment_uuid]

    async def test_staff_cannot_attach_to_ticket(self, db, ticket, admin_user, stored_files):
        with pytest.raises(HTTPException) as exc:
            await _upload(db, ticket, admin_user, to_ticket=True)
        assert exc.value.status_code == 403

    async def test_sixth_ticket_level_image_rejected(self, db, ticket, regular_user, stored_files):
        for _ in range(5):
            await _upload(db, ticket, regular_user, to_ticket=True)
        with pytest.raises(HTTPException) as exc:
            await _upload(db, ticket, regular_user, to_ticket=True)
        assert exc.value.status_code == 400

    async def test_pending_cap(self, db, ticket, regular_user, stored_files):
        for _ in range(20):
            await _upload(db, ticket, regular_user)
        with pytest.raises(HTTPException) as exc:
            await _upload(db, ticket, regular_user)
        assert exc.value.status_code == 400

    async def test_learner_cannot_upload_internal(self, db, ticket, regular_user, stored_files):
        with pytest.raises(HTTPException) as exc:
            await _upload(db, ticket, regular_user, internal=True)
        assert exc.value.status_code == 403

    async def test_staff_internal_upload_goes_to_internal_folder(self, db, ticket, admin_user, stored_files):
        att = await _upload(db, ticket, admin_user, internal=True)
        assert stored_files.call_args.kwargs["directory"] == f"tickets/{ticket.ticket_uuid}/internal"
        assert "/internal/" in att.file_path and att.is_internal is True

    async def test_other_learner_gets_404(self, db, ticket, other_learner, stored_files):
        with pytest.raises(HTTPException) as exc:
            await _upload(db, ticket, other_learner)
        assert exc.value.status_code == 404
        stored_files.assert_not_called()

    async def test_closed_ticket_rejects_upload(self, db, ticket, regular_user, admin_user, stored_files):
        await update_support_ticket(db, ticket.ticket_uuid, SupportTicketUpdate(status=TicketStatusEnum.CLOSED), admin_user)
        with pytest.raises(HTTPException) as exc:
            await _upload(db, ticket, regular_user)
        assert exc.value.status_code == 409
        stored_files.assert_not_called()


class TestReplyAttachments:
    async def test_reply_links_own_pending_upload(self, db, ticket, regular_user, stored_files):
        att = await _upload(db, ticket, regular_user)
        msg = await add_ticket_message(
            db, ticket.ticket_uuid, TicketMessageCreate(content="see screenshot", attachment_uuids=[att.attachment_uuid]), regular_user
        )
        assert [a.attachment_uuid for a in msg.attachments] == [att.attachment_uuid]
        detail = await get_ticket_detail(db, ticket.ticket_uuid, regular_user)
        assert [a.attachment_uuid for a in detail.messages[0].attachments] == [att.attachment_uuid]

    async def test_images_only_reply(self, db, ticket, regular_user, stored_files):
        att = await _upload(db, ticket, regular_user)
        msg = await add_ticket_message(
            db, ticket.ticket_uuid, TicketMessageCreate(content="", attachment_uuids=[att.attachment_uuid]), regular_user
        )
        assert msg.content == "" and len(msg.attachments) == 1

    async def test_cannot_attach_someone_elses_upload(self, db, ticket, regular_user, admin_user, stored_files):
        att = await _upload(db, ticket, admin_user)
        with pytest.raises(HTTPException) as exc:
            await add_ticket_message(
                db, ticket.ticket_uuid, TicketMessageCreate(content="x", attachment_uuids=[att.attachment_uuid]), regular_user
            )
        assert exc.value.status_code == 400

    async def test_cannot_reuse_an_attached_upload(self, db, ticket, regular_user, stored_files):
        att = await _upload(db, ticket, regular_user)
        body = TicketMessageCreate(content="x", attachment_uuids=[att.attachment_uuid])
        await add_ticket_message(db, ticket.ticket_uuid, body, regular_user)
        with pytest.raises(HTTPException) as exc:
            await add_ticket_message(db, ticket.ticket_uuid, body, regular_user)
        assert exc.value.status_code == 400

    async def test_unknown_uuid_rejected_and_nothing_saved(self, db, ticket, regular_user, stored_files):
        with pytest.raises(HTTPException) as exc:
            await add_ticket_message(
                db, ticket.ticket_uuid, TicketMessageCreate(content="x", attachment_uuids=["ticketatt_nope"]), regular_user
            )
        assert exc.value.status_code == 400
        detail = await get_ticket_detail(db, ticket.ticket_uuid, regular_user)
        assert detail.messages == []

    async def test_internal_flag_must_match_message(self, db, ticket, admin_user, stored_files):
        public = await _upload(db, ticket, admin_user)
        internal = await _upload(db, ticket, admin_user, internal=True)
        with pytest.raises(HTTPException):
            await add_ticket_message(
                db, ticket.ticket_uuid, TicketMessageCreate(content="x", is_internal=True, attachment_uuids=[public.attachment_uuid]), admin_user
            )
        with pytest.raises(HTTPException):
            await add_ticket_message(
                db, ticket.ticket_uuid, TicketMessageCreate(content="x", attachment_uuids=[internal.attachment_uuid]), admin_user
            )

    async def test_upload_from_another_ticket_rejected(self, db, org, ticket, regular_user, stored_files):
        other = await create_support_ticket(db, _ticket_in(org.id, subject="Second ticket"), regular_user)
        att = await upload_ticket_attachment(db, other.ticket_uuid, _png(), False, False, regular_user)
        with pytest.raises(HTTPException) as exc:
            await add_ticket_message(
                db, ticket.ticket_uuid, TicketMessageCreate(content="x", attachment_uuids=[att.attachment_uuid]), regular_user
            )
        assert exc.value.status_code == 400

    async def test_owner_never_sees_internal_note_images(self, db, ticket, regular_user, admin_user, stored_files):
        public = await _upload(db, ticket, admin_user)
        internal = await _upload(db, ticket, admin_user, internal=True)
        await add_ticket_message(db, ticket.ticket_uuid, TicketMessageCreate(content="reply", attachment_uuids=[public.attachment_uuid]), admin_user)
        await add_ticket_message(db, ticket.ticket_uuid, TicketMessageCreate(content="note", is_internal=True, attachment_uuids=[internal.attachment_uuid]), admin_user)

        owner_view = await get_ticket_detail(db, ticket.ticket_uuid, regular_user)
        staff_view = await get_ticket_detail(db, ticket.ticket_uuid, admin_user)
        owner_uuids = [a.attachment_uuid for m in owner_view.messages for a in m.attachments]
        staff_uuids = [a.attachment_uuid for m in staff_view.messages for a in m.attachments]
        assert owner_uuids == [public.attachment_uuid]
        assert staff_uuids == [public.attachment_uuid, internal.attachment_uuid]
