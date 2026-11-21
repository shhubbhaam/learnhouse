"""Course-level weighted grading: the maths and the database loader."""

from datetime import datetime, timedelta

import pytest

from src.db.courses.assignments import (
    Assignment,
    AssignmentTask,
    AssignmentTaskTypeEnum,
    AssignmentUserSubmission,
    AssignmentUserSubmissionStatus,
    GradingTypeEnum,
)
from src.db.courses.course_grading import (
    CourseGradeCategory,
    CourseGradingSettings,
    GradingModeEnum,
    MissingWorkPolicyEnum,
)
from src.services.courses.course_grading import (
    ITEM_GRADED,
    ITEM_MISSING,
    ITEM_PENDING,
    CategorySpec,
    GradeItem,
    classify_assignment,
    compute_course_grade,
    compute_course_grades,
    compute_weighted_course_grade,
)

PAST = "2024-01-01"
FUTURE = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

_next_id = iter(range(1, 10_000))


def item(cat, pct, *, state=None, weight=1.0, never_drop=False, aid=None):
    aid = aid if aid is not None else next(_next_id)
    if state is None:
        state = ITEM_PENDING if pct is None else ITEM_GRADED
    return GradeItem(
        assignment_id=aid,
        assignment_uuid=f"assignment_{aid}",
        title=f"A{aid}",
        category_id=cat,
        category_weight=weight,
        never_drop=never_drop,
        state=state,
        percentage=pct,
    )


def cat(cid, weight, drop=0, position=0):
    return CategorySpec(
        id=cid, category_uuid=f"cat_{cid}", name=f"C{cid}",
        weight=weight, drop_lowest=drop, position=position,
    )


def by_uuid(result, uuid):
    return next(c for c in result["categories"] if c["category_uuid"] == uuid)


# ---------------------------------------------------------------------------
# compute_weighted_course_grade (pure)
# ---------------------------------------------------------------------------


class TestWeightedGrade:
    def test_worked_example_from_design_doc(self):
        cats = [cat(1, 20, drop=1, position=0), cat(2, 30, position=1),
                cat(3, 20, position=2), cat(4, 30, position=3)]
        items = [
            *(item(1, p) for p in (90, 85, 40, 80, 65)),
            item(2, 75), item(2, 65),
            item(3, 60),
            item(4, 90),
        ]
        r = compute_weighted_course_grade(cats, items, GradingTypeEnum.ALPHABET)
        assert by_uuid(r, "cat_1")["percentage"] == 80.0
        assert by_uuid(r, "cat_1")["dropped_count"] == 1
        assert by_uuid(r, "cat_2")["percentage"] == 70.0
        assert r["percentage"] == 76.0
        assert r["display_grade"] == "C"
        assert r["passed"] is True
        assert r["complete"] is True

    def test_drop_waits_until_category_is_done(self):
        # One quiz still pending: nothing is dropped yet.
        r = compute_weighted_course_grade(
            [cat(1, 100, drop=1)], [item(1, 90), item(1, 40), item(1, None)]
        )
        q = by_uuid(r, "cat_1")
        assert q["complete"] is False
        assert q["dropped_count"] == 0
        assert q["percentage"] == 65.0
        assert r["complete"] is False

    def test_skipped_assignment_counted_as_zero_is_the_one_dropped(self):
        r = compute_weighted_course_grade(
            [cat(1, 100, drop=1)],
            [item(1, 80), item(1, 70), item(1, 0.0, state=ITEM_MISSING)],
        )
        q = by_uuid(r, "cat_1")
        dropped = [a for a in q["assignments"] if a["dropped"]]
        assert len(dropped) == 1 and dropped[0]["state"] == ITEM_MISSING
        assert q["percentage"] == 75.0

    def test_never_drop_is_respected(self):
        r = compute_weighted_course_grade(
            [cat(1, 100, drop=1)],
            [item(1, 10, never_drop=True), item(1, 60), item(1, 80)],
        )
        q = by_uuid(r, "cat_1")
        # 10 is protected, so 60 is dropped: (10 + 80) / 2
        assert q["percentage"] == 45.0

    def test_never_drops_every_score(self):
        r = compute_weighted_course_grade(
            [cat(1, 100, drop=5)], [item(1, 50), item(1, 70)]
        )
        q = by_uuid(r, "cat_1")
        assert q["dropped_count"] == 1
        assert q["percentage"] == 70.0

    def test_single_score_is_never_dropped(self):
        r = compute_weighted_course_grade([cat(1, 100, drop=1)], [item(1, 30)])
        assert by_uuid(r, "cat_1")["percentage"] == 30.0

    def test_assignment_weights_inside_a_category(self):
        # Lab 2 counts double: (60*1 + 90*2) / 3 = 80
        r = compute_weighted_course_grade(
            [cat(1, 100)], [item(1, 60, weight=1), item(1, 90, weight=2)]
        )
        assert r["percentage"] == 80.0

    def test_zero_weight_assignment_does_not_count(self):
        r = compute_weighted_course_grade(
            [cat(1, 100)], [item(1, 0, weight=0), item(1, 90)]
        )
        assert r["percentage"] == 90.0

    def test_tie_drops_the_heavier_assignment(self):
        r = compute_weighted_course_grade(
            [cat(1, 100, drop=1)],
            [item(1, 50, weight=1, aid=901), item(1, 50, weight=3, aid=902), item(1, 100, aid=903)],
        )
        dropped = [a["assignment_uuid"] for a in by_uuid(r, "cat_1")["assignments"] if a["dropped"]]
        assert dropped == ["assignment_902"]
        # (50*1 + 100*1) / 2
        assert r["percentage"] == 75.0

    def test_current_grade_uses_only_categories_with_scores(self):
        # Exams not attempted yet: the current grade is the quiz average alone.
        r = compute_weighted_course_grade(
            [cat(1, 40), cat(2, 60)], [item(1, 80), item(2, None)]
        )
        assert r["percentage"] == 80.0
        assert r["complete"] is False

    def test_empty_category_is_ignored(self):
        r = compute_weighted_course_grade([cat(1, 50), cat(2, 50)], [item(1, 70)])
        assert r["percentage"] == 70.0
        assert by_uuid(r, "cat_2")["percentage"] is None

    def test_uncategorised_items_do_not_count(self):
        r = compute_weighted_course_grade(
            [cat(1, 100)], [item(1, 90), item(None, 10), item(99, 10)]
        )
        assert r["percentage"] == 90.0
        assert len(r["uncategorised"]) == 2

    def test_no_scores_means_no_grade(self):
        r = compute_weighted_course_grade([cat(1, 100)], [item(1, None)])
        assert r["percentage"] is None
        assert r["display_grade"] is None
        assert r["passed"] is False
        assert r["complete"] is False

    def test_pass_fail_with_custom_threshold(self):
        items = [item(1, 65)]
        assert compute_weighted_course_grade(
            [cat(1, 100)], items, GradingTypeEnum.PASS_FAIL, 70
        )["display_grade"] == "Fail"
        assert compute_weighted_course_grade(
            [cat(1, 100)], items, GradingTypeEnum.PASS_FAIL, 60
        )["display_grade"] == "Pass"

    def test_fractional_percentages_keep_two_decimals(self):
        r = compute_weighted_course_grade(
            [cat(1, 100)], [item(1, 100), item(1, 100), item(1, 0)]
        )
        assert r["percentage"] == 66.67


# ---------------------------------------------------------------------------
# classify_assignment (pure)
# ---------------------------------------------------------------------------


def _assignment(**kw):
    defaults = dict(
        title="A", description="", due_date=None, published=True,
        grading_type=GradingTypeEnum.PERCENTAGE, org_id=1, course_id=1,
        chapter_id=1, activity_id=1, assignment_uuid="assignment_x",
    )
    defaults.update(kw)
    return Assignment(**defaults)


def _submission(status, grade=0):
    return AssignmentUserSubmission(
        submission_status=status, grade=grade, user_id=1, assignment_id=1,
        assignmentusersubmission_uuid="aus_x",
    )


ZERO = MissingWorkPolicyEnum.ZERO_AFTER_DUE
EXCLUDE = MissingWorkPolicyEnum.EXCLUDE


class TestClassifyAssignment:
    def test_formative_is_excluded(self):
        assert classify_assignment(_assignment(ungraded=True), 100, None, ZERO) is None

    def test_zero_max_is_excluded(self):
        assert classify_assignment(_assignment(), 0, None, ZERO) is None

    def test_graded(self):
        s = _submission(AssignmentUserSubmissionStatus.GRADED, 45)
        assert classify_assignment(_assignment(), 60, s, ZERO) == (ITEM_GRADED, 75.0)

    def test_grade_is_clamped(self):
        s = _submission(AssignmentUserSubmissionStatus.GRADED, 150)
        assert classify_assignment(_assignment(), 100, s, ZERO) == (ITEM_GRADED, 100.0)

    def test_missing_past_due_counts_as_zero(self):
        assert classify_assignment(_assignment(due_date=PAST), 100, None, ZERO) == (ITEM_MISSING, 0.0)

    def test_saved_but_not_submitted_past_due_counts_as_zero(self):
        s = _submission(AssignmentUserSubmissionStatus.PENDING)
        assert classify_assignment(_assignment(due_date=PAST), 100, s, ZERO) == (ITEM_MISSING, 0.0)

    def test_missing_with_exclude_policy_stays_pending(self):
        assert classify_assignment(_assignment(due_date=PAST), 100, None, EXCLUDE) == (ITEM_PENDING, None)

    def test_not_due_yet_is_pending(self):
        assert classify_assignment(_assignment(due_date=FUTURE), 100, None, ZERO) == (ITEM_PENDING, None)

    def test_no_due_date_is_never_auto_zeroed(self):
        assert classify_assignment(_assignment(due_date=None), 100, None, ZERO) == (ITEM_PENDING, None)

    def test_handed_in_but_ungraded_is_pending_even_past_due(self):
        for status in (AssignmentUserSubmissionStatus.SUBMITTED, AssignmentUserSubmissionStatus.LATE):
            s = _submission(status)
            assert classify_assignment(_assignment(due_date=PAST), 100, s, ZERO) == (ITEM_PENDING, None)


# ---------------------------------------------------------------------------
# compute_course_grades (database)
# ---------------------------------------------------------------------------


async def _add_assignment(db, org, course, activity, uuid, *, category=None,
                          weight=1.0, max_grade=100, due_date=PAST, ungraded=False):
    a = Assignment(
        title=uuid, description="", due_date=due_date, published=True,
        grading_type=GradingTypeEnum.PERCENTAGE, ungraded=ungraded,
        org_id=org.id, course_id=course.id, chapter_id=1, activity_id=activity.id,
        assignment_uuid=uuid, creation_date="2024-01-01", update_date="2024-01-01",
        grade_category_id=category.id if category else None, category_weight=weight,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    db.add(AssignmentTask(
        title="T", description="", hint="", assignment_type=AssignmentTaskTypeEnum.QUIZ,
        contents={}, max_grade_value=max_grade, assignment_id=a.id, org_id=org.id,
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


async def _category(db, course, uuid, weight, drop=0, position=0):
    c = CourseGradeCategory(
        category_uuid=uuid, course_id=course.id, name=uuid,
        weight=weight, drop_lowest=drop, position=position,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


class TestComputeCourseGrades:
    @pytest.mark.asyncio
    async def test_legacy_course_has_no_course_grade(self, db, org, course, activity, regular_user):
        a = await _add_assignment(db, org, course, activity, "a1")
        await _grade(db, a, regular_user, 80)
        r = await compute_course_grade(course.id, regular_user.id, db)
        assert r["grading_mode"] == GradingModeEnum.ALL_MUST_PASS.value
        assert r["percentage"] is None
        assert r["uncategorised"][0]["percentage"] == 80.0

    @pytest.mark.asyncio
    async def test_weighted_course(self, db, org, course, activity, regular_user, admin_user):
        db.add(CourseGradingSettings(
            course_id=course.id, grading_mode=GradingModeEnum.WEIGHTED,
            final_grading_type=GradingTypeEnum.PERCENTAGE,
        ))
        await db.commit()
        quizzes = await _category(db, course, "quizzes", 40, drop=1, position=0)
        project = await _category(db, course, "project", 60, position=1)

        q1 = await _add_assignment(db, org, course, activity, "q1", category=quizzes)
        q2 = await _add_assignment(db, org, course, activity, "q2", category=quizzes)
        await _add_assignment(db, org, course, activity, "q3", category=quizzes)  # skipped
        p1 = await _add_assignment(db, org, course, activity, "p1", category=project, max_grade=50)
        await _add_assignment(db, org, course, activity, "formative", category=project, ungraded=True)

        for a, g in ((q1, 90), (q2, 70), (p1, 40)):
            await _grade(db, a, regular_user, g)
        await _grade(db, q1, admin_user, 100)

        grades = await compute_course_grades(course.id, [regular_user.id, admin_user.id], db)

        r = grades[regular_user.id]
        assert r["grading_mode"] == GradingModeEnum.WEIGHTED.value
        # q3 skipped (past due -> 0) and dropped: quizzes = 80; project = 40/50 = 80
        assert by_uuid(r, "quizzes")["percentage"] == 80.0
        assert by_uuid(r, "project")["percentage"] == 80.0
        assert r["percentage"] == 80.0
        assert r["complete"] is True
        # The formative assignment never appears in a grade.
        assert all(a["assignment_uuid"] != "formative"
                   for c in r["categories"] for a in c["assignments"])

        other = grades[admin_user.id]
        # q1=100, q2/q3 missing (0, one dropped) -> 50; project missing -> 0
        assert by_uuid(other, "quizzes")["percentage"] == 50.0
        assert other["percentage"] == 20.0
        assert other["passed"] is False
