import type { CourseGradeItem, CourseGradeResult } from './types'

/** "76.5%" — at most one decimal, no trailing ".0". */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${Math.round(value * 10) / 10}%`
}

/** Every counted item in a result (categories first, then uncategorised). */
export function allItems(result: CourseGradeResult): CourseGradeItem[] {
  return [...result.categories.flatMap((c) => c.assignments), ...result.uncategorised]
}

/** Counted assignments still waiting for a grade (or for their due date). */
export function pendingCount(result: CourseGradeResult): number {
  return result.categories.flatMap((c) => c.assignments).filter((a) => a.state === 'PENDING').length
}

export type GradeStanding = 'none' | 'passed' | 'failed' | 'on_track' | 'below'

/**
 * How to label the learner's grade. A complete grade is final (passed /
 * failed); an incomplete one is only a current standing (on track / below).
 */
export function gradeStanding(result: CourseGradeResult): GradeStanding {
  if (result.percentage === null) return 'none'
  if (result.complete) return result.passed ? 'passed' : 'failed'
  return result.passed ? 'on_track' : 'below'
}

/** Whether the learner page should show the card at all. */
export function shouldShowGradeCard(result: CourseGradeResult | undefined): boolean {
  return !!result && result.grading_mode === 'WEIGHTED' && result.categories.length > 0
}
