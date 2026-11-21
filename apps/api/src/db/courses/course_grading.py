"""Course-level grading: weighted categories and the course grading settings.

Today every assignment is graded on its own and a certificate requires every
graded assignment to be passed. These tables add an optional course-level grade:

- ``CourseGradeCategory`` groups a course's assignments (Quizzes, Labs, ...) and
  gives the group a weight. ``drop_lowest`` discards the k lowest scores in the
  group once the learner has finished every assignment in it.
- ``CourseGradingSettings`` holds the per-course switches: whether the weighted
  grade is used at all, how the final grade is displayed, the pass mark, how
  missing work counts, and which rule gates the certificate.

A course with no settings row behaves exactly as before (ALL_MUST_PASS +
ALL_ASSIGNMENTS), so nothing changes until a teacher opts in.

Assignment membership lives on the ``assignment`` row itself
(``grade_category_id``, ``category_weight``, ``never_drop``); see
``src/db/courses/assignments.py``.
"""

from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, ForeignKey, Index
from sqlmodel import Field, SQLModel

from src.db.courses.assignments import GradingTypeEnum


class GradingModeEnum(str, Enum):
    """How the course grade is produced.

    ALL_MUST_PASS - no course grade; legacy behaviour (every assignment stands
                    on its own).
    WEIGHTED      - weighted average of category averages.
    """

    ALL_MUST_PASS = "ALL_MUST_PASS"
    WEIGHTED = "WEIGHTED"


class MissingWorkPolicyEnum(str, Enum):
    """How an assignment the learner has not handed in counts.

    ZERO_AFTER_DUE - 0% once its due date has passed (no due date: never
                     auto-zeroed, it stays pending).
    EXCLUDE        - ignored until it is graded.
    """

    ZERO_AFTER_DUE = "ZERO_AFTER_DUE"
    EXCLUDE = "EXCLUDE"


class CertificateRuleEnum(str, Enum):
    """What a learner must achieve to be certified.

    ALL_ASSIGNMENTS - pass every graded assignment (legacy behaviour).
    FINAL_GRADE     - final course grade at or above the course pass mark.
    BOTH            - both of the above.
    """

    ALL_ASSIGNMENTS = "ALL_ASSIGNMENTS"
    FINAL_GRADE = "FINAL_GRADE"
    BOTH = "BOTH"


## CourseGradeCategory ##


class CourseGradeCategoryBase(SQLModel):
    name: str
    # Share of the course grade, 0-100. The categories of a course must total
    # 100 when the course uses WEIGHTED mode (enforced by the service).
    weight: float = Field(default=0, ge=0, le=100)
    # Drop the k lowest assignment scores in this category. Applied only once
    # every assignment in the category is done for that learner.
    drop_lowest: int = Field(default=0, ge=0)
    position: int = 0


class CourseGradeCategory(CourseGradeCategoryBase, table=True):
    __table_args__ = (Index("ix_coursegradecategory_course_id", "course_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    category_uuid: str = Field(default="", unique=True, index=True)
    course_id: int = Field(
        sa_column=Column(
            "course_id", ForeignKey("course.id", ondelete="CASCADE"), nullable=False
        )
    )
    creation_date: Optional[str] = None
    update_date: Optional[str] = None


## CourseGradingSettings ##


class CourseGradingSettingsBase(SQLModel):
    grading_mode: GradingModeEnum = GradingModeEnum.ALL_MUST_PASS
    final_grading_type: GradingTypeEnum = GradingTypeEnum.PERCENTAGE
    # Course pass mark (0-100). None = the grading-type default (50, or 60 for
    # ALPHABET / GPA_SCALE), same convention as Assignment.pass_threshold_percentage.
    final_pass_threshold: Optional[float] = Field(default=None, ge=0, le=100)
    missing_policy: MissingWorkPolicyEnum = MissingWorkPolicyEnum.ZERO_AFTER_DUE
    certificate_rule: CertificateRuleEnum = CertificateRuleEnum.ALL_ASSIGNMENTS


class CourseGradingSettings(CourseGradingSettingsBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(
        sa_column=Column(
            "course_id",
            ForeignKey("course.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )
    )
    creation_date: Optional[str] = None
    update_date: Optional[str] = None


## API models ##


class GradingAssignmentPlacement(SQLModel):
    """Where one assignment sits in the course grade."""

    assignment_uuid: str
    # None = uncategorised (does not count toward the weighted grade).
    category_uuid: Optional[str] = None
    category_weight: float = Field(default=1.0, ge=0)
    never_drop: bool = False


class CourseGradeCategoryInput(CourseGradeCategoryBase):
    # Omitted for a new category; given to keep an existing one (and its id).
    category_uuid: Optional[str] = None


class CourseGradingUpdate(CourseGradingSettingsBase):
    """Body of PUT /courses/{course_uuid}/grading.

    The full desired state: categories not listed are deleted (their
    assignments become uncategorised), assignments not listed keep their
    current placement.
    """

    categories: List[CourseGradeCategoryInput] = Field(default_factory=list)
    assignments: List[GradingAssignmentPlacement] = Field(default_factory=list)


class CourseGradeCategoryRead(CourseGradeCategoryBase):
    category_uuid: str


class GradingAssignmentRead(SQLModel):
    assignment_uuid: str
    title: str
    category_uuid: Optional[str] = None
    category_weight: float = 1.0
    never_drop: bool = False
    ungraded: bool = False
    due_date: Optional[str] = None


class CourseGradingRead(CourseGradingSettingsBase):
    course_uuid: str
    categories: List[CourseGradeCategoryRead] = Field(default_factory=list)
    assignments: List[GradingAssignmentRead] = Field(default_factory=list)


## Grade results ##


class CourseGradeItemResult(SQLModel):
    assignment_uuid: str
    title: str
    state: str  # GRADED / MISSING / PENDING
    percentage: Optional[float] = None
    category_weight: float = 1.0
    never_drop: bool = False
    dropped: bool = False


class CourseGradeCategoryResult(SQLModel):
    category_uuid: str
    name: str
    weight: float
    drop_lowest: int
    percentage: Optional[float] = None
    complete: bool
    dropped_count: int
    assignments: List[CourseGradeItemResult] = Field(default_factory=list)


class CourseGradeResult(SQLModel):
    grading_mode: GradingModeEnum
    # True once every counted assignment is graded (or counted as missing).
    complete: bool
    percentage: Optional[float] = None
    display_grade: Optional[str] = None
    letter_grade: Optional[str] = None
    passed: bool = False
    passing_threshold: float
    grading_type: str
    categories: List[CourseGradeCategoryResult] = Field(default_factory=list)
    uncategorised: List[CourseGradeItemResult] = Field(default_factory=list)


class GradebookStudent(SQLModel):
    user_id: int
    user_uuid: str
    username: str
    first_name: str = ""
    last_name: str = ""
    grade: CourseGradeResult


class GradebookRead(SQLModel):
    course_uuid: str
    grading_mode: GradingModeEnum
    categories: List[CourseGradeCategoryRead] = Field(default_factory=list)
    assignments: List[GradingAssignmentRead] = Field(default_factory=list)
    students: List[GradebookStudent] = Field(default_factory=list)


class CourseGradingUpdateResult(CourseGradingRead):
    # Certificates changed by re-evaluating every learner under the new rules.
    certificates_issued: int = 0
    certificates_revoked: int = 0
