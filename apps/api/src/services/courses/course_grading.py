"""Course-level weighted grading.

Turns a learner's per-assignment results into one course grade:

1. Each assignment is classified (``classify_assignment``): GRADED with its
   percentage, MISSING (counted as 0% once past due, when the course says so),
   PENDING (not counted yet), or excluded (formative / nothing to grade).
2. Each category averages its assignments, weighted by ``category_weight``.
   Its ``drop_lowest`` k lowest scores are discarded, but only once every
   assignment in the category is done for that learner (no PENDING item), and
   never an assignment flagged ``never_drop``. A skipped assignment counted as
   0% can be the one dropped.
3. The course percentage is the weight-averaged category percentages, divided
   by the weights of the categories that have a score so far, so a learner
   halfway through the course sees a fair current grade.
4. The percentage is formatted with the course's grading type and pass mark,
   reusing ``compute_assignment_grade`` so letters / GPA / pass-fail render
   exactly like an assignment grade.

The pure functions (``classify_assignment``, ``compute_weighted_course_grade``)
hold all the maths and take no database session, so they are unit-tested
directly. ``compute_course_grade`` / ``compute_course_grades`` load the rows.

Imports of the assignments service are deferred: that module imports
``certifications``, which imports this one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.assignments import (
    Assignment,
    AssignmentTask,
    AssignmentUserSubmission,
    AssignmentUserSubmissionStatus,
    GradingTypeEnum,
)
from src.db.courses.chapter_activities import ChapterActivity
from src.db.courses.course_grading import (
    CourseGradeCategory,
    CourseGradingSettings,
    GradingModeEnum,
    MissingWorkPolicyEnum,
)

ITEM_GRADED = "GRADED"
ITEM_MISSING = "MISSING"  # not handed in, past due, counted as 0%
ITEM_PENDING = "PENDING"  # not counted yet

_NOT_HANDED_IN = (
    AssignmentUserSubmissionStatus.PENDING,
    AssignmentUserSubmissionStatus.NOT_SUBMITTED,
)


@dataclass(frozen=True)
class GradeItem:
    """One assignment's contribution for one learner."""

    assignment_id: int
    assignment_uuid: str
    title: str
    category_id: Optional[int]
    category_weight: float
    never_drop: bool
    state: str
    percentage: Optional[float]  # None while PENDING


@dataclass(frozen=True)
class CategorySpec:
    id: int
    category_uuid: str
    name: str
    weight: float
    drop_lowest: int
    position: int = 0


def classify_assignment(
    assignment: Assignment,
    max_grade: int,
    submission: Optional[AssignmentUserSubmission],
    missing_policy: MissingWorkPolicyEnum | str,
) -> Optional[tuple[str, Optional[float]]]:
    """Return ``(state, percentage)`` for one assignment, or None to exclude it.

    Excluded: formative (``ungraded``) assignments, which never carry a grade,
    and assignments with no gradable points (same rule the certificate check
    uses, so they never count against a learner).
    """
    from src.services.courses.activities.assignments import _is_assignment_past_due

    if getattr(assignment, "ungraded", False):
        return None
    if int(max_grade or 0) <= 0:
        return None

    if (
        submission is not None
        and submission.submission_status == AssignmentUserSubmissionStatus.GRADED
    ):
        raw = max(min(int(submission.grade or 0), int(max_grade)), 0)
        return ITEM_GRADED, round(raw / int(max_grade) * 100.0, 2)

    policy = (
        missing_policy.value
        if isinstance(missing_policy, MissingWorkPolicyEnum)
        else missing_policy
    )
    not_handed_in = submission is None or submission.submission_status in _NOT_HANDED_IN
    if (
        policy == MissingWorkPolicyEnum.ZERO_AFTER_DUE.value
        and not_handed_in
        and _is_assignment_past_due(assignment)
    ):
        return ITEM_MISSING, 0.0

    # Handed in but not graded yet, not due yet, or EXCLUDE policy.
    return ITEM_PENDING, None


def _format_percentage(
    percentage: Optional[float],
    grading_type: GradingTypeEnum | str | None,
    pass_threshold: Optional[float],
) -> dict:
    """Display fields for a course percentage, same rules as an assignment grade."""
    from src.services.courses.activities.assignments import compute_assignment_grade

    if percentage is None:
        # Still format with 0 to learn the threshold, but report no grade.
        base = compute_assignment_grade(0, 100, grading_type, None, pass_threshold)
        return {
            "percentage": None,
            "display_grade": None,
            "letter_grade": None,
            "passed": False,
            "passing_threshold": base["passing_threshold"],
            "grading_type": base["grading_type"],
        }
    # Basis points keep two decimals through the integer API.
    computed = compute_assignment_grade(
        int(round(percentage * 100)), 10000, grading_type, None, pass_threshold
    )
    return {
        "percentage": computed["percentage"],
        "display_grade": computed["display_grade"],
        "letter_grade": computed["letter_grade"],
        "passed": computed["passed"],
        "passing_threshold": computed["passing_threshold"],
        "grading_type": computed["grading_type"],
    }


def _item_row(item: GradeItem, dropped: bool) -> dict:
    return {
        "assignment_uuid": item.assignment_uuid,
        "title": item.title,
        "state": item.state,
        "percentage": item.percentage,
        "category_weight": item.category_weight,
        "never_drop": item.never_drop,
        "dropped": dropped,
    }


def _compute_category(category: CategorySpec, items: Sequence[GradeItem]) -> dict:
    complete = all(i.state != ITEM_PENDING for i in items)
    scored = [i for i in items if i.percentage is not None]

    dropped_ids: set[int] = set()
    if complete and category.drop_lowest > 0 and len(scored) > 1:
        candidates = sorted(
            (i for i in scored if not i.never_drop),
            # Lowest score first; on a tie drop the heavier one (it helps the
            # learner more); then a stable order.
            key=lambda i: (i.percentage, -i.category_weight, i.assignment_id),
        )
        # Never drop every score: at least one must remain.
        n_drop = min(category.drop_lowest, len(candidates), len(scored) - 1)
        dropped_ids = {i.assignment_id for i in candidates[:n_drop]}

    kept = [i for i in scored if i.assignment_id not in dropped_ids]
    total_weight = sum(max(i.category_weight, 0.0) for i in kept)
    percentage = (
        round(
            sum(max(i.category_weight, 0.0) * i.percentage for i in kept) / total_weight,
            2,
        )
        if total_weight > 0
        else None
    )
    return {
        "category_uuid": category.category_uuid,
        "name": category.name,
        "weight": category.weight,
        "drop_lowest": category.drop_lowest,
        "percentage": percentage,
        "complete": complete,
        "dropped_count": len(dropped_ids),
        "assignments": [_item_row(i, i.assignment_id in dropped_ids) for i in items],
    }


def compute_weighted_course_grade(
    categories: Iterable[CategorySpec],
    items: Iterable[GradeItem],
    final_grading_type: GradingTypeEnum | str | None = GradingTypeEnum.PERCENTAGE,
    final_pass_threshold: Optional[float] = None,
) -> dict:
    """The course grade from categories and classified items. Pure function."""
    categories = sorted(categories, key=lambda c: (c.position, c.id))
    items = list(items)
    by_category: dict[int, list[GradeItem]] = {}
    for item in items:
        if item.category_id is not None:
            by_category.setdefault(item.category_id, []).append(item)
    known = {c.id for c in categories}

    category_rows = [_compute_category(c, by_category.get(c.id, [])) for c in categories]

    counted = [
        (c.weight, row["percentage"])
        for c, row in zip(categories, category_rows)
        if row["percentage"] is not None and c.weight > 0
    ]
    total = sum(w for w, _ in counted)
    percentage = round(sum(w * p for w, p in counted) / total, 2) if total > 0 else None

    uncategorised = [
        _item_row(i, False)
        for i in items
        if i.category_id is None or i.category_id not in known
    ]
    complete = percentage is not None and all(r["complete"] for r in category_rows)

    return {
        "grading_mode": GradingModeEnum.WEIGHTED.value,
        "complete": complete,
        **_format_percentage(percentage, final_grading_type, final_pass_threshold),
        "categories": category_rows,
        "uncategorised": uncategorised,
    }


## Loading from the database ##


def default_settings(course_id: int) -> CourseGradingSettings:
    """Settings for a course that never opted in: the legacy behaviour."""
    return CourseGradingSettings(course_id=course_id)


async def get_grading_settings(course_id: int, db_session: AsyncSession) -> CourseGradingSettings:
    settings = (
        await db_session.execute(
            select(CourseGradingSettings).where(CourseGradingSettings.course_id == course_id)
        )
    ).scalars().first()
    return settings or default_settings(course_id)


async def get_grade_categories(course_id: int, db_session: AsyncSession) -> list[CourseGradeCategory]:
    rows = (
        await db_session.execute(
            select(CourseGradeCategory)
            .where(CourseGradeCategory.course_id == course_id)
            .order_by(CourseGradeCategory.position, CourseGradeCategory.id)
        )
    ).scalars().all()
    return list(rows)


async def get_course_assignments(course_id: int, db_session: AsyncSession) -> list[Assignment]:
    """Assignments whose activity is actually placed in this course.

    Same selection as the certificate check (an IN-subquery so an activity
    reused across chapters is not counted twice).
    """
    rows = (
        await db_session.execute(
            select(Assignment)
            .where(
                Assignment.course_id == course_id,
                Assignment.activity_id.in_(
                    select(ChapterActivity.activity_id).where(
                        ChapterActivity.course_id == course_id
                    )
                ),
            )
            .order_by(Assignment.id)
        )
    ).scalars().all()
    return list(rows)


async def get_max_grades(assignment_ids: Sequence[int], db_session: AsyncSession) -> dict[int, int]:
    if not assignment_ids:
        return {}
    rows = (
        await db_session.execute(
            select(
                AssignmentTask.assignment_id,
                func.coalesce(func.sum(AssignmentTask.max_grade_value), 0),
            )
            .where(AssignmentTask.assignment_id.in_(assignment_ids))
            .group_by(AssignmentTask.assignment_id)
        )
    ).all()
    return {aid: int(m or 0) for aid, m in rows}


async def compute_course_grades(
    course_id: int,
    user_ids: Sequence[int],
    db_session: AsyncSession,
) -> dict[int, dict]:
    """Course grade for several learners with a fixed number of queries."""
    settings = await get_grading_settings(course_id, db_session)
    categories = await get_grade_categories(course_id, db_session)
    assignments = await get_course_assignments(course_id, db_session)
    assignment_ids = [a.id for a in assignments if a.id is not None]
    max_by_assignment = await get_max_grades(assignment_ids, db_session)

    submissions: dict[tuple[int, int], AssignmentUserSubmission] = {}
    if assignment_ids and user_ids:
        rows = (
            await db_session.execute(
                select(AssignmentUserSubmission).where(
                    AssignmentUserSubmission.assignment_id.in_(assignment_ids),
                    AssignmentUserSubmission.user_id.in_(list(user_ids)),
                )
            )
        ).scalars().all()
        submissions = {(s.user_id, s.assignment_id): s for s in rows}

    specs = [
        CategorySpec(
            id=c.id,
            category_uuid=c.category_uuid,
            name=c.name,
            weight=float(c.weight or 0),
            drop_lowest=int(c.drop_lowest or 0),
            position=int(c.position or 0),
        )
        for c in categories
    ]
    weighted = settings.grading_mode == GradingModeEnum.WEIGHTED

    results: dict[int, dict] = {}
    for user_id in user_ids:
        items: list[GradeItem] = []
        for a in assignments:
            classified = classify_assignment(
                a,
                max_by_assignment.get(a.id, 0),
                submissions.get((user_id, a.id)),
                settings.missing_policy,
            )
            if classified is None:
                continue
            state, pct = classified
            items.append(
                GradeItem(
                    assignment_id=a.id,
                    assignment_uuid=a.assignment_uuid,
                    title=a.title,
                    category_id=a.grade_category_id if weighted else None,
                    category_weight=float(
                        a.category_weight if a.category_weight is not None else 1.0
                    ),
                    never_drop=bool(a.never_drop),
                    state=state,
                    percentage=pct,
                )
            )

        if weighted:
            results[user_id] = compute_weighted_course_grade(
                specs, items, settings.final_grading_type, settings.final_pass_threshold
            )
        else:
            # Legacy mode: no course grade, just the per-assignment results.
            results[user_id] = {
                "grading_mode": GradingModeEnum.ALL_MUST_PASS.value,
                "complete": all(i.state != ITEM_PENDING for i in items),
                **_format_percentage(None, settings.final_grading_type, settings.final_pass_threshold),
                "categories": [],
                "uncategorised": [_item_row(i, False) for i in items],
            }
    return results


async def compute_course_grade(course_id: int, user_id: int, db_session: AsyncSession) -> dict:
    return (await compute_course_grades(course_id, [user_id], db_session))[user_id]


## API services ##
#
# Teacher endpoints authorize like grading does (course UPDATE through
# authorize_assignment_access, which also accepts API tokens scoped to
# assignments). The learner endpoint only ever returns the caller's own grade.

_WEIGHT_TOLERANCE = 0.01


async def _get_course_or_404(course_uuid: str, db_session: AsyncSession):
    from fastapi import HTTPException
    from src.db.courses.courses import Course

    course = (
        await db_session.execute(select(Course).where(Course.course_uuid == course_uuid))
    ).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


async def _authorize_teacher(request, db_session, current_user, course) -> None:
    from src.security.rbac import AccessAction
    from src.services.courses.activities.assignments import authorize_assignment_access

    await authorize_assignment_access(
        request, db_session, current_user, course.course_uuid, AccessAction.UPDATE,
        token_action="read",
    )


def _grading_read(course, settings, categories, assignments):
    from src.db.courses.course_grading import (
        CourseGradeCategoryRead,
        CourseGradingRead,
        GradingAssignmentRead,
    )

    uuid_by_id = {c.id: c.category_uuid for c in categories}
    return CourseGradingRead(
        course_uuid=course.course_uuid,
        grading_mode=settings.grading_mode,
        final_grading_type=settings.final_grading_type,
        final_pass_threshold=settings.final_pass_threshold,
        missing_policy=settings.missing_policy,
        certificate_rule=settings.certificate_rule,
        categories=[
            CourseGradeCategoryRead(
                category_uuid=c.category_uuid, name=c.name, weight=c.weight,
                drop_lowest=c.drop_lowest, position=c.position,
            )
            for c in categories
        ],
        assignments=[
            GradingAssignmentRead(
                assignment_uuid=a.assignment_uuid,
                title=a.title,
                category_uuid=uuid_by_id.get(a.grade_category_id),
                category_weight=float(a.category_weight if a.category_weight is not None else 1.0),
                never_drop=bool(a.never_drop),
                ungraded=bool(a.ungraded),
                due_date=a.due_date,
            )
            for a in assignments
        ],
    )


async def read_course_grading(request, course_uuid: str, current_user, db_session: AsyncSession):
    course = await _get_course_or_404(course_uuid, db_session)
    await _authorize_teacher(request, db_session, current_user, course)
    settings = await get_grading_settings(course.id, db_session)
    categories = await get_grade_categories(course.id, db_session)
    assignments = await get_course_assignments(course.id, db_session)
    return _grading_read(course, settings, categories, assignments)


def _validate_update(body, course_assignments, placement_by_uuid) -> None:
    """Reject inconsistent settings before anything is written."""
    from fastapi import HTTPException
    from src.db.courses.course_grading import CertificateRuleEnum

    def bad(detail: str):
        raise HTTPException(status_code=400, detail=detail)

    if body.grading_mode != GradingModeEnum.WEIGHTED:
        if body.certificate_rule != CertificateRuleEnum.ALL_ASSIGNMENTS:
            bad("A final-grade certificate rule needs weighted grading")
    else:
        if not body.categories:
            bad("Weighted grading needs at least one category")
        total = sum(c.weight for c in body.categories)
        if abs(total - 100.0) > _WEIGHT_TOLERANCE:
            bad(f"Category weights must total 100 (got {total:g})")

    names = [c.name.strip() for c in body.categories]
    if any(not n for n in names):
        bad("Every category needs a name")
    if len({n.lower() for n in names}) != len(names):
        bad("Category names must be unique")

    uuids = [c.category_uuid for c in body.categories if c.category_uuid]
    if len(set(uuids)) != len(uuids):
        bad("Duplicate category_uuid")

    seen = set()
    for p in body.assignments:
        if p.assignment_uuid in seen:
            bad(f"Assignment listed twice: {p.assignment_uuid}")
        seen.add(p.assignment_uuid)
        if p.assignment_uuid not in course_assignments:
            bad(f"Assignment not in this course: {p.assignment_uuid}")
        if p.category_uuid is not None and p.category_uuid not in set(uuids):
            bad(f"Unknown category for {p.assignment_uuid}: {p.category_uuid}")

    # drop_lowest must leave at least one score in the category.
    for c in body.categories:
        if not c.drop_lowest or not c.category_uuid:
            continue
        members = [
            a for a in course_assignments.values()
            if not a.ungraded and placement_by_uuid.get(a.assignment_uuid) == c.category_uuid
        ]
        if members and c.drop_lowest >= len(members):
            bad(
                f"'{c.name}' drops {c.drop_lowest} of {len(members)} assignments; "
                "at least one must count"
            )


async def update_course_grading(request, course_uuid: str, body, current_user, db_session: AsyncSession):
    """Replace the course's grading setup with ``body`` and re-check certificates."""
    from datetime import datetime
    from uuid import uuid4
    from fastapi import HTTPException
    from src.db.courses.course_grading import CourseGradingUpdateResult

    course = await _get_course_or_404(course_uuid, db_session)
    await _authorize_teacher(request, db_session, current_user, course)

    existing = {c.category_uuid: c for c in await get_grade_categories(course.id, db_session)}
    # Every category in the body gets a uuid now, so placements can refer to
    # categories created in this same request. A client-chosen uuid that
    # already belongs to another course is refused.
    for c in body.categories:
        if not c.category_uuid:
            c.category_uuid = f"category_{uuid4()}"
        elif c.category_uuid not in existing:
            taken = (await db_session.execute(
                select(CourseGradeCategory.id).where(
                    CourseGradeCategory.category_uuid == c.category_uuid
                )
            )).first()
            if taken:
                raise HTTPException(status_code=400, detail=f"category_uuid already in use: {c.category_uuid}")

    course_assignments = {a.assignment_uuid: a for a in await get_course_assignments(course.id, db_session)}
    # The placement each assignment will end up with: current unless overridden.
    current_uuid_by_id = {c.id: u for u, c in existing.items()}
    placement_by_uuid = {
        u: current_uuid_by_id.get(a.grade_category_id) for u, a in course_assignments.items()
    }
    for p in body.assignments:
        placement_by_uuid[p.assignment_uuid] = p.category_uuid
    kept_uuids = {c.category_uuid for c in body.categories}
    placement_by_uuid = {
        u: (cu if cu in kept_uuids else None) for u, cu in placement_by_uuid.items()
    }

    _validate_update(body, course_assignments, placement_by_uuid)

    now = str(datetime.now())

    # Categories: update kept, create new, delete the rest.
    by_uuid: dict[str, CourseGradeCategory] = {}
    for position, c in enumerate(body.categories):
        row = existing.get(c.category_uuid)
        if row is None:
            row = CourseGradeCategory(
                category_uuid=c.category_uuid, course_id=course.id, creation_date=now,
                name="", weight=0,
            )
        row.name = c.name.strip()
        row.weight = c.weight
        row.drop_lowest = c.drop_lowest
        row.position = position
        row.update_date = now
        db_session.add(row)
        by_uuid[c.category_uuid] = row
    await db_session.flush()

    removed = [row for u, row in existing.items() if u not in kept_uuids]

    # Assignments: apply the final placement (also clears removed categories;
    # done explicitly rather than relying on ON DELETE SET NULL, which SQLite
    # does not enforce without the foreign_keys pragma).
    overrides = {p.assignment_uuid: p for p in body.assignments}
    for u, a in course_assignments.items():
        target = placement_by_uuid.get(u)
        a.grade_category_id = by_uuid[target].id if target else None
        if u in overrides:
            a.category_weight = overrides[u].category_weight
            a.never_drop = overrides[u].never_drop
        db_session.add(a)

    for row in removed:
        await db_session.delete(row)

    settings = (await db_session.execute(
        select(CourseGradingSettings).where(CourseGradingSettings.course_id == course.id)
    )).scalars().first()
    if settings is None:
        settings = CourseGradingSettings(course_id=course.id, creation_date=now)
    settings.grading_mode = body.grading_mode
    settings.final_grading_type = body.final_grading_type
    settings.final_pass_threshold = body.final_pass_threshold
    settings.missing_policy = body.missing_policy
    settings.certificate_rule = body.certificate_rule
    settings.update_date = now
    db_session.add(settings)
    await db_session.commit()

    issued, revoked = await reconcile_course_certificates(request, course, db_session)

    categories = await get_grade_categories(course.id, db_session)
    assignments = await get_course_assignments(course.id, db_session)
    base = _grading_read(course, settings, categories, assignments)
    return CourseGradingUpdateResult(
        **base.model_dump(), certificates_issued=issued, certificates_revoked=revoked,
    )


async def _enrolled_user_ids(course_id: int, db_session: AsyncSession) -> list[int]:
    """Learners enrolled in the course, plus anyone with a submission in it."""
    from src.db.trail_runs import TrailRun

    enrolled = (await db_session.execute(
        select(TrailRun.user_id).where(TrailRun.course_id == course_id)
    )).scalars().all()
    submitted = (await db_session.execute(
        select(AssignmentUserSubmission.user_id)
        .join(Assignment, Assignment.id == AssignmentUserSubmission.assignment_id)
        .where(Assignment.course_id == course_id)
    )).scalars().all()
    return sorted({u for u in (*enrolled, *submitted) if u is not None})


async def _certificate_holders(course_id: int, db_session: AsyncSession) -> set[int]:
    from src.db.courses.certifications import CertificateUser, Certifications

    rows = (await db_session.execute(
        select(CertificateUser.user_id)
        .join(Certifications, Certifications.id == CertificateUser.certification_id)
        .where(Certifications.course_id == course_id)
    )).scalars().all()
    return set(rows)


async def reconcile_course_certificates(request, course, db_session: AsyncSession) -> tuple[int, int]:
    """Re-check every learner's certificate after the grading rules changed.

    Returns (issued, revoked). Best-effort per learner, like the regrade path.
    """
    from src.services.courses.activities.assignments import (
        _reconcile_certificate_after_grade_change,
    )

    before = await _certificate_holders(course.id, db_session)
    for user_id in await _enrolled_user_ids(course.id, db_session):
        await _reconcile_certificate_after_grade_change(request, user_id, course, db_session)
    after = await _certificate_holders(course.id, db_session)
    return len(after - before), len(before - after)


async def read_gradebook(request, course_uuid: str, current_user, db_session: AsyncSession):
    from src.db.courses.course_grading import GradebookRead, GradebookStudent
    from src.db.users import User

    course = await _get_course_or_404(course_uuid, db_session)
    await _authorize_teacher(request, db_session, current_user, course)

    user_ids = await _enrolled_user_ids(course.id, db_session)
    users = {}
    if user_ids:
        users = {
            u.id: u for u in (await db_session.execute(
                select(User).where(User.id.in_(user_ids))
            )).scalars().all()
        }
    grades = await compute_course_grades(course.id, user_ids, db_session)
    setup = await read_course_grading(request, course_uuid, current_user, db_session)

    students = [
        GradebookStudent(
            user_id=uid,
            user_uuid=users[uid].user_uuid,
            username=users[uid].username,
            first_name=users[uid].first_name or "",
            last_name=users[uid].last_name or "",
            grade=grades[uid],
        )
        for uid in user_ids
        if uid in users
    ]
    students.sort(key=lambda s: (s.last_name.lower(), s.first_name.lower(), s.username.lower()))
    return GradebookRead(
        course_uuid=course.course_uuid,
        grading_mode=setup.grading_mode,
        categories=setup.categories,
        assignments=setup.assignments,
        students=students,
    )


async def export_gradebook_csv(request, course_uuid: str, current_user, db_session: AsyncSession) -> str:
    """The gradebook as CSV: one row per learner, a column per assignment and category."""
    import csv
    import io
    from src.services.orgs.users import _csv_safe

    book = await read_gradebook(request, course_uuid, current_user, db_session)
    counted = [a for a in book.assignments if not a.ungraded]

    out = io.StringIO()
    writer = csv.writer(out)
    # Titles and category names are teacher-typed, so the header is sanitised too.
    writer.writerow([_csv_safe(v) for v in (
        "username", "first_name", "last_name",
        *(f"{a.title} (%)" for a in counted),
        *(f"{c.name} [{c.weight:g}%] (%)" for c in book.categories),
        "course_percentage", "course_grade", "passed", "complete",
    )])

    def fmt(v):
        return "" if v is None else f"{v:g}"

    for s in book.students:
        g = s.grade
        pct_by_assignment = {
            i.assignment_uuid: i.percentage
            for i in [*(x for c in g.categories for x in c.assignments), *g.uncategorised]
        }
        pct_by_category = {c.category_uuid: c.percentage for c in g.categories}
        writer.writerow([_csv_safe(v) for v in (
            s.username, s.first_name, s.last_name,
            *(fmt(pct_by_assignment.get(a.assignment_uuid)) for a in counted),
            *(fmt(pct_by_category.get(c.category_uuid)) for c in book.categories),
            fmt(g.percentage), g.display_grade or "", "yes" if g.passed else "no",
            "yes" if g.complete else "no",
        )])
    return out.getvalue()


async def read_my_course_grade(request, course_uuid: str, current_user, db_session: AsyncSession):
    from fastapi import HTTPException
    from src.db.users import PublicUser
    from src.security.rbac import AccessAction, check_resource_access

    if not isinstance(current_user, PublicUser):
        raise HTTPException(status_code=403, detail="Only a signed-in learner has a course grade")
    course = await _get_course_or_404(course_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)
    return await compute_course_grade(course.id, current_user.id, db_session)
