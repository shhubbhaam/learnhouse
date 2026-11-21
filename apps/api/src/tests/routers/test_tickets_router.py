"""Router tests for src/routers/tickets.py (wiring, validation, mounting)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.tickets.ticket_messages import TicketMessage  # noqa: F401 (registers table)
from src.routers.tickets import router as tickets_router
from src.security.auth import get_current_user


def _app(db, user) -> FastAPI:
    app = FastAPI()
    app.include_router(tickets_router, prefix="/api/v1/tickets")
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return app


async def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


VALID = {
    "org_id": 1,
    "subject": "Can't submit assignment",
    "description": "The submit button does nothing on the final step.",
    "category": "COURSE_CONTENT",
}


async def test_full_flow(db, org, regular_user, admin_user):
    async with await _client(_app(db, regular_user)) as learner:
        r = await learner.post("/api/v1/tickets/", json=VALID)
        assert r.status_code == 200, r.text
        uuid = r.json()["ticket_uuid"]
        assert r.json()["priority"] == "MEDIUM"

        r = await learner.get(f"/api/v1/tickets/org/{org.id}/me")
        assert r.status_code == 200 and len(r.json()) == 1

        r = await learner.get(f"/api/v1/tickets/org/{org.id}/admin")
        assert r.status_code == 403

        r = await learner.patch(f"/api/v1/tickets/{uuid}", json={"status": "CLOSED"})
        assert r.status_code == 404

    async with await _client(_app(db, admin_user)) as staff:
        r = await staff.get(f"/api/v1/tickets/org/{org.id}/admin", params={"status": "OPEN"})
        assert r.status_code == 200 and r.json()["total"] == 1

        r = await staff.post(f"/api/v1/tickets/{uuid}/messages", json={"content": "Looking now"})
        assert r.status_code == 200 and r.json()["is_staff"] is True

        r = await staff.patch(
            f"/api/v1/tickets/{uuid}",
            json={"status": "RESOLVED", "priority": "HIGH", "resolution_note": "Fixed the form."},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "RESOLVED" and r.json()["resolution_note"] == "Fixed the form."

    async with await _client(_app(db, regular_user)) as learner:
        r = await learner.get(f"/api/v1/tickets/{uuid}")
        assert r.status_code == 200
        body = r.json()
        assert body["resolution_note"] == "Fixed the form."
        assert [m["content"] for m in body["messages"]] == ["Looking now"]


@pytest.mark.parametrize(
    "patch",
    [
        {"subject": "no"},                       # too short
        {"description": "short"},                # too short
        {"category": "NOT_A_CATEGORY"},
        {"subject": "x" * 201},                  # too long
    ],
)
async def test_create_validation(db, org, regular_user, patch):
    async with await _client(_app(db, regular_user)) as c:
        r = await c.post("/api/v1/tickets/", json={**VALID, **patch})
        assert r.status_code == 422


async def test_admin_list_limit_capped(db, org, admin_user):
    async with await _client(_app(db, admin_user)) as c:
        r = await c.get(f"/api/v1/tickets/org/{org.id}/admin", params={"limit": 500})
        assert r.status_code == 422



async def test_attachment_upload_and_reply_over_http(db, org, regular_user, admin_user):
    from unittest.mock import AsyncMock, patch

    async with await _client(_app(db, regular_user)) as learner:
        uuid = (await learner.post("/api/v1/tickets/", json=VALID)).json()["ticket_uuid"]
        with patch("src.services.tickets.attachments.upload_file", new=AsyncMock(return_value="abc_ticket.png")):
            r = await learner.post(
                f"/api/v1/tickets/{uuid}/attachments",
                files={"file": ("shot.png", b"\x89PNG fake", "image/png")},
                data={"attach_to_ticket": "false"},
            )
        assert r.status_code == 200, r.text
        att = r.json()
        assert att["file_path"].endswith(f"/tickets/{uuid}/abc_ticket.png")

        r = await learner.post(f"/api/v1/tickets/{uuid}/messages", json={"content": "", "attachment_uuids": [att["attachment_uuid"]]})
        assert r.status_code == 200, r.text
        assert r.json()["attachments"][0]["attachment_uuid"] == att["attachment_uuid"]

        # A learner may not upload into an internal note.
        with patch("src.services.tickets.attachments.upload_file", new=AsyncMock(return_value="x.png")):
            r = await learner.post(
                f"/api/v1/tickets/{uuid}/attachments",
                files={"file": ("n.png", b"x", "image/png")},
                data={"is_internal": "true"},
            )
        assert r.status_code == 403
