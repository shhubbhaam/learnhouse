"""Tests for private support-ticket attachments.

Ticket files live under ``orgs/{org_uuid}/tickets/...``, which the generic
content rule would serve to anyone (org content is public). These tests pin
the stricter rule: only org staff, the uploader, or the ticket owner (for
non-internal, sent images) may load a file, and only if an attachment row for
that ticket and file exists.
"""

from datetime import datetime

import pytest
from fastapi import HTTPException

from src.db.tickets.ticket_attachments import TicketAttachment
from src.db.tickets.ticket_messages import TicketMessage  # noqa: F401 (registers table)
from src.db.tickets.tickets import SupportTicket
from src.db.user_organizations import UserOrganization
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User
from src.security.ticket_file_access import enforce_ticket_file_access, is_ticket_file

TICKET_UUID = "ticket_files_test"


def _parts(file_id, org_uuid="org_test", internal=False):
    base = ["orgs", org_uuid, "tickets", TICKET_UUID]
    return base + (["internal", file_id] if internal else [file_id])


async def _user(db, user_id, username, org_id=None, role_id=None) -> PublicUser:
    u = User(
        id=user_id, username=username, first_name=username, last_name="T",
        email=f"{username}@test.com", password="x", user_uuid=f"user_{username}",
        creation_date=str(datetime.now()), update_date=str(datetime.now()),
    )
    db.add(u)
    await db.commit()
    if org_id is not None:
        db.add(UserOrganization(user_id=user_id, org_id=org_id, role_id=role_id,
                                creation_date=str(datetime.now()), update_date=str(datetime.now())))
        await db.commit()
    return PublicUser(id=u.id, username=u.username, first_name=u.first_name,
                      last_name=u.last_name, email=u.email, user_uuid=u.user_uuid)


@pytest.fixture
async def ticket(db, org, regular_user):
    t = SupportTicket(ticket_uuid=TICKET_UUID, subject="s", description="d" * 10,
                      org_id=org.id, user_id=regular_user.id)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def _attach(db, ticket, uploader_id, file_id, *, internal=False, attached=True):
    db.add(TicketAttachment(
        attachment_uuid=f"ticketatt_{file_id}", ticket_id=ticket.id, uploader_id=uploader_id,
        file_id=file_id, content_type="image/png", size=10, is_internal=internal, attached=attached,
    ))
    await db.commit()


class TestIsTicketFile:
    def test_matches(self):
        assert is_ticket_file(_parts("a.png")) is True
        assert is_ticket_file(_parts("a.png", internal=True)) is True

    def test_rejects_other_paths(self):
        assert is_ticket_file(["orgs", "o", "communities", "c", "media", "a.png"]) is False
        assert is_ticket_file(["orgs", "o", "tickets"]) is False
        assert is_ticket_file(["users", "u", "tickets", "t", "a.png"]) is False


class TestEnforceTicketFileAccess:
    async def test_owner_reads_own_sent_image(self, db, ticket, regular_user):
        await _attach(db, ticket, regular_user.id, "own.png")
        await enforce_ticket_file_access(_parts("own.png"), regular_user, db)

    async def test_owner_cannot_read_internal_image(self, db, ticket, regular_user, admin_user):
        await _attach(db, ticket, admin_user.id, "note.png", internal=True)
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("note.png", internal=True), regular_user, db)
        assert exc.value.status_code == 403

    async def test_owner_cannot_read_staff_unsent_upload(self, db, ticket, regular_user, admin_user):
        await _attach(db, ticket, admin_user.id, "draft.png", attached=False)
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("draft.png"), regular_user, db)
        assert exc.value.status_code == 403

    async def test_uploader_reads_own_unsent_upload(self, db, ticket, regular_user):
        await _attach(db, ticket, regular_user.id, "mine.png", attached=False)
        await enforce_ticket_file_access(_parts("mine.png"), regular_user, db)

    async def test_staff_reads_everything(self, db, ticket, regular_user, admin_user):
        await _attach(db, ticket, regular_user.id, "a.png")
        await _attach(db, ticket, regular_user.id, "b.png", attached=False)
        await _attach(db, ticket, admin_user.id, "c.png", internal=True)
        await enforce_ticket_file_access(_parts("a.png"), admin_user, db)
        await enforce_ticket_file_access(_parts("b.png"), admin_user, db)
        await enforce_ticket_file_access(_parts("c.png", internal=True), admin_user, db)

    async def test_maintainer_is_staff(self, db, ticket, org, regular_user):
        maintainer = await _user(db, 20, "maint", org_id=org.id, role_id=2)
        await _attach(db, ticket, regular_user.id, "a.png")
        await enforce_ticket_file_access(_parts("a.png"), maintainer, db)

    async def test_other_learner_same_org_denied(self, db, ticket, org, regular_user):
        other = await _user(db, 40, "other", org_id=org.id, role_id=4)
        await _attach(db, ticket, regular_user.id, "a.png")
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("a.png"), other, db)
        assert exc.value.status_code == 403

    async def test_admin_of_other_org_denied(self, db, ticket, other_org, regular_user):
        outsider = await _user(db, 30, "outsider", org_id=other_org.id, role_id=1)
        await _attach(db, ticket, regular_user.id, "a.png")
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("a.png"), outsider, db)
        assert exc.value.status_code == 403

    async def test_wrong_org_uuid_in_path_denied(self, db, ticket, regular_user, admin_user):
        await _attach(db, ticket, regular_user.id, "a.png")
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("a.png", org_uuid="org_other"), admin_user, db)
        assert exc.value.status_code == 403

    async def test_internal_flag_must_match_path(self, db, ticket, regular_user):
        # A non-internal row requested through the internal/ path (or the reverse) is not a match.
        await _attach(db, ticket, regular_user.id, "a.png")
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("a.png", internal=True), regular_user, db)
        assert exc.value.status_code == 403

    async def test_file_without_row_denied_even_for_staff(self, db, ticket, admin_user):
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("ghost.png"), admin_user, db)
        assert exc.value.status_code == 403

    async def test_unknown_ticket_denied(self, db, org, admin_user):
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(
                ["orgs", "org_test", "tickets", "ticket_nope", "a.png"], admin_user, db
            )
        assert exc.value.status_code == 403

    async def test_anonymous_gets_401(self, db, ticket, regular_user):
        await _attach(db, ticket, regular_user.id, "a.png")
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("a.png"), AnonymousUser(), db)
        assert exc.value.status_code == 401

    async def test_api_token_denied(self, db, ticket, org, regular_user):
        await _attach(db, ticket, regular_user.id, "a.png")
        token = APITokenUser.model_construct(id=0, created_by_user_id=regular_user.id, org_id=org.id)
        with pytest.raises(HTTPException) as exc:
            await enforce_ticket_file_access(_parts("a.png"), token, db)
        assert exc.value.status_code == 403
