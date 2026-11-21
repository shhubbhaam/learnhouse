"""Router + service tests for the course grading endpoints (src/routers/courses/grading.py)."""

import csv
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from src.core.events.database import get_db_session
from src.db.courses.assignments import (
    Assignment,
    AssignmentTask,
    AssignmentTaskTypeEnum,
    AssignmentUserSubmission,
    AssignmentUserSubmissionStatus,
    GradingTypeEnum,
)
from src.db.courses.certifications import CertificateUser, Certifications
from src.routers.courses.grading import router as grading_router
from src.security.auth import get_authenticated_user

BASE = "/api/v1/courses/course_test"


@pytest.fixture
def current_user(admin_user):
    return {"user": admin_user}


@pytest.fixture
def app(db, current_user):
    app = FastAPI()
    app.include_router(grading_router, prefix="/api/v1/courses")
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_authenticated_user] = lambda: current_user["user"]
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def rbac():
    """Allow by default; tests flip ``side_effect`` to deny."""
    mock = AsyncMock()
    with patch("src.services.courses.activities.assignments.check_resource_access", mock), \
         patch("src.security.rbac.check_resource_access", mock):
        yield mock


@pytest.fixture
def quiet_side_effects():
    with patch("src.services.courses.certifications.track", new_callable=AsyncMock), \
         patch("src.services.courses.certifications.dispatch_webhooks", new_callable=AsyncMock), \
         patch("src.services.courses.certifications.record_audit_event", new_callable=AsyncMock), \
         patch("src.services.courses.certifications.is_course_fully_completed",
               new=AsyncMock(return_value=True)):
        yield


async def _assignment(db, org, course, activity, uuid, title=None):
    a = Assignment(
        title=title or uuid, description="", due_date="2024-01-01", published=True,
        grading_type=GradingTypeEnum.PERCENTAGE, org_id=org.id, course_id=course.id,
        chapter_id=1, activity_id=activity.id, assignment_uuid=uuid,
        creation_date="2024-01-01", update_date="2024-01-01",
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    db.add(AssignmentTask(
        title="T", description="", hint="", assignment_type=AssignmentTaskTypeEnum.QUIZ,
        contents={}, max_grade_value=100, assignment_id=a.id, org_id=org.id,
        course_id=course.id, chapter_id=1, activity_id=activity.id,
        assignment_task_uuid=f"task_{uuid}", creation_date="2024-01-01", update_date="2024-01-01",
    ))
    await db.commit()
    return a


async def _grade(db, assignment, user, grade):
    db.add(AssignmentUserSubmission(
        submission_status=AssignmentUserSubmissionStatus.GRADED, grade=grade,
        user_id=user.id, assignment_id=assignment.id,
        assignmentusersubmission_uuid=f"aus_{assignment.id}_{user.id}",
        creation_date="2024-01-01", update_date="2024-01-01",
    ))
    await db.commit()


@pytest.fixture
async def quizzes(db, org, course, activity, regular_user):
    q1 = await _assignment(db, org, course, activity, "q1", "Quiz 1")
    q2 = await _assignment(db, org, course, activity, "q2", "=Quiz 2")  # CSV-injection title
    await _grade(db, q1, regular_user, 90)
    await _grade(db, q2, regular_user, 40)
    return q1, q2


def _weighted_body(rule="ALL_ASSIGNMENTS", weight=100, drop=1):
    return {
        "grading_mode": "WEIGHTED",
        "final_grading_type": "PERCENTAGE",
        "missing_policy": "ZERO_AFTER_DUE",
        "certificate_rule": rule,
        "categories": [{"category_uuid": "category_quizzes", "name": "Quizzes", "weight": weight, "drop_lowest": drop}],
        "assignments": [
            {"assignment_uuid": "q1", "category_uuid": "category_quizzes"},
            {"assignment_uuid": "q2", "category_uuid": "category_quizzes"},
        ],
    }


class TestGradingSetup:
    async def test_defaults_to_legacy(self, client, rbac, quizzes):
        r = await client.get(f"{BASE}/grading")
        assert r.status_code == 200
        body = r.json()
        assert body["grading_mode"] == "ALL_MUST_PASS"
        assert body["certificate_rule"] == "ALL_ASSIGNMENTS"
        assert {a["assignment_uuid"] for a in body["assignments"]} == {"q1", "q2"}
        assert all(a["category_uuid"] is None for a in body["assignments"])

    async def test_put_creates_categories_and_places_assignments(self, client, rbac, quizzes):
        r = await client.put(f"{BASE}/grading", json=_weighted_body())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["grading_mode"] == "WEIGHTED"
        assert [c["name"] for c in body["categories"]] == ["Quizzes"]
        assert {a["category_uuid"] for a in body["assignments"]} == {"category_quizzes"}

        again = (await client.get(f"{BASE}/grading")).json()
        assert again["categories"][0]["drop_lowest"] == 1

    async def test_new_category_without_uuid_gets_one(self, client, rbac, quizzes):
        body = _weighted_body()
        body["categories"][0].pop("category_uuid")
        body["assignments"] = []
        r = await client.put(f"{BASE}/grading", json=body)
        assert r.status_code == 200, r.text
        assert r.json()["categories"][0]["category_uuid"].startswith("category_")

    async def test_removing_a_category_uncategorises_its_assignments(self, client, rbac, quizzes):
        await client.put(f"{BASE}/grading", json=_weighted_body())
        r = await client.put(f"{BASE}/grading", json={
            "grading_mode": "ALL_MUST_PASS", "categories": [], "assignments": [],
        })
        assert r.status_code == 200, r.text
        assert r.json()["categories"] == []
        assert all(a["category_uuid"] is None for a in r.json()["assignments"])

    async def test_assignment_weight_and_never_drop_are_saved(self, client, rbac, quizzes):
        body = _weighted_body()
        body["assignments"][0].update(category_weight=2.5, never_drop=True)
        r = await client.put(f"{BASE}/grading", json=body)
        q1 = next(a for a in r.json()["assignments"] if a["assignment_uuid"] == "q1")
        assert q1["category_weight"] == 2.5 and q1["never_drop"] is True

    @pytest.mark.parametrize("mutate, message", [
        (lambda b: b["categories"][0].update(weight=90), "total 100"),
        (lambda b: b["categories"][0].update(drop_lowest=2), "at least one must count"),
        (lambda b: b["assignments"].append({"assignment_uuid": "nope"}), "not in this course"),
        (lambda b: b["assignments"][0].update(category_uuid="category_missing"), "Unknown category"),
        (lambda b: b["categories"].append({"name": "quizzes", "weight": 0}), "unique"),
        (lambda b: b.update(grading_mode="ALL_MUST_PASS", certificate_rule="FINAL_GRADE"), "needs weighted"),
    ])
    async def test_invalid_setup_is_rejected(self, client, rbac, quizzes, mutate, message):
        body = _weighted_body()
        mutate(body)
        r = await client.put(f"{BASE}/grading", json=body)
        assert r.status_code == 400
        assert message in r.json()["detail"]

    async def test_category_uuid_from_another_course_is_rejected(self, client, rbac, quizzes, db, other_org):
        from src.db.courses.course_grading import CourseGradeCategory
        from src.db.courses.courses import Course
        other = Course(id=2, name="Other", description="", public=True, published=True,
                       open_to_contributors=False, org_id=other_org.id, course_uuid="course_other",
                       creation_date="2024-01-01", update_date="2024-01-01")
        db.add(other)
        await db.commit()
        db.add(CourseGradeCategory(category_uuid="category_quizzes", course_id=2, name="X", weight=100))
        await db.commit()
        r = await client.put(f"{BASE}/grading", json=_weighted_body())
        assert r.status_code == 400
        assert "already in use" in r.json()["detail"]

    async def test_denied_without_grading_rights(self, client, rbac, quizzes):
        rbac.side_effect = HTTPException(status_code=403, detail="nope")
        assert (await client.get(f"{BASE}/grading")).status_code == 403
        assert (await client.put(f"{BASE}/grading", json=_weighted_body())).status_code == 403
        assert (await client.get(f"{BASE}/gradebook")).status_code == 403

    async def test_unknown_course(self, client, rbac):
        assert (await client.get("/api/v1/courses/course_nope/grading")).status_code == 404


class TestGradebook:
    async def test_gradebook_and_csv(self, client, rbac, quizzes):
        await client.put(f"{BASE}/grading", json=_weighted_body())
        r = await client.get(f"{BASE}/gradebook")
        assert r.status_code == 200, r.text
        students = r.json()["students"]
        assert len(students) == 1
        grade = students[0]["grade"]
        # q2 (40) dropped -> 90
        assert grade["percentage"] == 90.0
        assert grade["categories"][0]["dropped_count"] == 1

        r = await client.get(f"{BASE}/gradebook/export")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0][3:5] == ["Quiz 1 (%)", "'=Quiz 2 (%)"]
        assert rows[1][3:5] == ["90", "40"]
        assert rows[1][-4:] == ["90", "90.00%", "yes", "yes"]

    async def test_my_grade_is_the_callers_own(self, client, rbac, quizzes, current_user, regular_user):
        await client.put(f"{BASE}/grading", json=_weighted_body())
        current_user["user"] = regular_user
        r = await client.get(f"{BASE}/grades/me")
        assert r.status_code == 200, r.text
        assert r.json()["percentage"] == 90.0


class TestCertificateRule:
    async def test_switching_rules_issues_and_revokes(
        self, client, rbac, quizzes, quiet_side_effects, db, course, regular_user,
    ):
        db.add(Certifications(course_id=course.id, config={}, certification_uuid="cert_x",
                              creation_date="2024-01-01", update_date="2024-01-01"))
        await db.commit()

        async def holders():
            return (await db.execute(select(CertificateUser.user_id))).scalars().all()

        # Legacy rule: the 40% quiz fails -> no certificate.
        r = await client.put(f"{BASE}/grading", json=_weighted_body("ALL_ASSIGNMENTS"))
        assert r.json()["certificates_issued"] == 0
        assert await holders() == []

        # Final grade rule: the 40% quiz is dropped, 90% passes -> issued.
        r = await client.put(f"{BASE}/grading", json=_weighted_body("FINAL_GRADE"))
        assert r.status_code == 200, r.text
        assert r.json()["certificates_issued"] == 1
        assert await holders() == [regular_user.id]

        # BOTH needs every assignment passed too -> revoked.
        r = await client.put(f"{BASE}/grading", json=_weighted_body("BOTH"))
        assert r.json()["certificates_revoked"] == 1
        assert await holders() == []
