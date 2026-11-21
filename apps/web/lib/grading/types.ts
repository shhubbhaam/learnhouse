// Mirrors apps/api/src/db/courses/course_grading.py.

export type GradingMode = 'ALL_MUST_PASS' | 'WEIGHTED'
export type MissingWorkPolicy = 'ZERO_AFTER_DUE' | 'EXCLUDE'
export type CertificateRule = 'ALL_ASSIGNMENTS' | 'FINAL_GRADE' | 'BOTH'
export type GradingType = 'ALPHABET' | 'NUMERIC' | 'PERCENTAGE' | 'PASS_FAIL' | 'GPA_SCALE'

export interface GradeCategory {
  category_uuid: string
  name: string
  weight: number
  drop_lowest: number
  position: number
}

export interface GradingAssignment {
  assignment_uuid: string
  title: string
  category_uuid: string | null
  category_weight: number
  never_drop: boolean
  ungraded: boolean
  due_date: string | null
}

export interface CourseGradingSettings {
  grading_mode: GradingMode
  final_grading_type: GradingType
  final_pass_threshold: number | null
  missing_policy: MissingWorkPolicy
  certificate_rule: CertificateRule
}

export interface CourseGrading extends CourseGradingSettings {
  course_uuid: string
  categories: GradeCategory[]
  assignments: GradingAssignment[]
}

export interface CourseGradingUpdate extends CourseGradingSettings {
  categories: Array<Omit<GradeCategory, 'position'> & { position?: number }>
  assignments: Array<{
    assignment_uuid: string
    category_uuid: string | null
    category_weight: number
    never_drop: boolean
  }>
}

export interface CourseGradingUpdateResult extends CourseGrading {
  certificates_issued: number
  certificates_revoked: number
}

export type GradeItemState = 'GRADED' | 'MISSING' | 'PENDING'

export interface CourseGradeItem {
  assignment_uuid: string
  title: string
  state: GradeItemState
  percentage: number | null
  category_weight: number
  never_drop: boolean
  dropped: boolean
}

export interface CourseGradeCategoryResult {
  category_uuid: string
  name: string
  weight: number
  drop_lowest: number
  percentage: number | null
  complete: boolean
  dropped_count: number
  assignments: CourseGradeItem[]
}

export interface CourseGradeResult {
  grading_mode: GradingMode
  complete: boolean
  percentage: number | null
  display_grade: string | null
  letter_grade: string | null
  passed: boolean
  passing_threshold: number
  grading_type: GradingType
  categories: CourseGradeCategoryResult[]
  uncategorised: CourseGradeItem[]
}

export interface GradebookStudent {
  user_id: number
  user_uuid: string
  username: string
  first_name: string
  last_name: string
  grade: CourseGradeResult
}

export interface Gradebook {
  course_uuid: string
  grading_mode: GradingMode
  categories: GradeCategory[]
  assignments: GradingAssignment[]
  students: GradebookStudent[]
}
