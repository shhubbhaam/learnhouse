import { describe, expect, test } from 'bun:test'

import { formatPercent, gradeStanding, pendingCount, shouldShowGradeCard } from '../lib/grading/display.ts'

const item = (state, percentage, extra = {}) => ({
  assignment_uuid: `a_${Math.random()}`, title: 'A', state, percentage,
  category_weight: 1, never_drop: false, dropped: false, ...extra,
})

const result = (over = {}) => ({
  grading_mode: 'WEIGHTED', complete: true, percentage: 76, display_grade: 'C', letter_grade: 'C',
  passed: true, passing_threshold: 60, grading_type: 'ALPHABET',
  categories: [{ category_uuid: 'c', name: 'Quizzes', weight: 100, drop_lowest: 0, percentage: 76,
    complete: true, dropped_count: 0, assignments: [item('GRADED', 76)] }],
  uncategorised: [],
  ...over,
})

describe('grade card display', () => {
  test('formatPercent', () => {
    expect(formatPercent(76)).toBe('76%')
    expect(formatPercent(66.666)).toBe('66.7%')
    expect(formatPercent(null)).toBe('—')
  })

  test('standing: final vs current', () => {
    expect(gradeStanding(result())).toBe('passed')
    expect(gradeStanding(result({ passed: false }))).toBe('failed')
    expect(gradeStanding(result({ complete: false }))).toBe('on_track')
    expect(gradeStanding(result({ complete: false, passed: false }))).toBe('below')
    expect(gradeStanding(result({ percentage: null, complete: false, passed: false }))).toBe('none')
  })

  test('pending counts only categorised pending items', () => {
    const r = result({
      categories: [{ ...result().categories[0], assignments: [item('PENDING', null), item('GRADED', 50), item('MISSING', 0)] }],
      uncategorised: [item('PENDING', null)],
    })
    expect(pendingCount(r)).toBe(1)
  })

  test('only weighted courses with categories show the card', () => {
    expect(shouldShowGradeCard(result())).toBe(true)
    expect(shouldShowGradeCard(result({ grading_mode: 'ALL_MUST_PASS', categories: [] }))).toBe(false)
    expect(shouldShowGradeCard(result({ categories: [] }))).toBe(false)
    expect(shouldShowGradeCard(undefined)).toBe(false)
  })
})
