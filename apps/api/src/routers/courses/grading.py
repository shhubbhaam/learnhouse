"""Course-level weighted grading endpoints, mounted under /courses."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.courses.course_grading import (
    CourseGradeResult,
    CourseGradingRead,
    CourseGradingUpdate,
    CourseGradingUpdateResult,
    GradebookRead,
)
from src.db.users import PublicUser
from src.security.auth import get_authenticated_user
from src.services.courses.course_grading import (
    export_gradebook_csv,
    read_course_grading,
    read_gradebook,
    read_my_course_grade,
    update_course_grading,
)

router = APIRouter()

_TEACHER_ERRORS = {
    401: {"description": "Not signed in"},
    403: {"description": "Caller cannot grade this course"},
    404: {"description": "Course not found"},
}


@router.get(
    "/{course_uuid}/grading",
    response_model=CourseGradingRead,
    summary="Get course grading setup",
    description="Grading mode, final grade type, pass mark, missing-work policy, certificate rule, weighted categories and where each assignment sits.",
    responses=_TEACHER_ERRORS,
)
async def api_read_course_grading(
    request: Request,
    course_uuid: str,
    current_user: PublicUser = Depends(get_authenticated_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> CourseGradingRead:
    return await read_course_grading(request, course_uuid, current_user, db_session)


@router.put(
    "/{course_uuid}/grading",
    response_model=CourseGradingUpdateResult,
    summary="Replace course grading setup",
    description=(
        "Saves the whole grading setup in one transaction: categories not listed are deleted "
        "(their assignments become uncategorised), assignments not listed keep their placement. "
        "Weights must total 100 in weighted mode. Every learner's certificate is then re-checked; "
        "the response says how many were issued or revoked."
    ),
    responses={**_TEACHER_ERRORS, 400: {"description": "Invalid setup (weights, unknown category or assignment, drop_lowest too high)"}},
)
async def api_update_course_grading(
    request: Request,
    course_uuid: str,
    body: CourseGradingUpdate,
    current_user: PublicUser = Depends(get_authenticated_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> CourseGradingUpdateResult:
    return await update_course_grading(request, course_uuid, body, current_user, db_session)


@router.get(
    "/{course_uuid}/gradebook",
    response_model=GradebookRead,
    summary="Course gradebook",
    description="Every enrolled learner with per-assignment, per-category and final course grades.",
    responses=_TEACHER_ERRORS,
)
async def api_read_gradebook(
    request: Request,
    course_uuid: str,
    current_user: PublicUser = Depends(get_authenticated_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> GradebookRead:
    return await read_gradebook(request, course_uuid, current_user, db_session)


@router.get(
    "/{course_uuid}/gradebook/export",
    summary="Export course gradebook as CSV",
    responses={**_TEACHER_ERRORS, 200: {"content": {"text/csv": {}}}},
)
async def api_export_gradebook(
    request: Request,
    course_uuid: str,
    current_user: PublicUser = Depends(get_authenticated_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    body = await export_gradebook_csv(request, course_uuid, current_user, db_session)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="gradebook-{course_uuid}.csv"'},
    )


@router.get(
    "/{course_uuid}/grades/me",
    response_model=CourseGradeResult,
    summary="My course grade",
    description="The signed-in learner's own category breakdown and current course grade.",
    responses={401: {"description": "Not signed in"}, 403: {"description": "No access to this course"}, 404: {"description": "Course not found"}},
)
async def api_read_my_course_grade(
    request: Request,
    course_uuid: str,
    current_user: PublicUser = Depends(get_authenticated_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> CourseGradeResult:
    return await read_my_course_grade(request, course_uuid, current_user, db_session)
