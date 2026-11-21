import { describe, expect, test } from 'bun:test'

import {
  evenWeights,
  isDirty,
  removeCategory,
  toForm,
  toPayload,
  validateGradingForm,
  weightsTotal,
} from '../lib/grading/form.ts'

const grading = (over = {}) => ({
  course_uuid: 'course_x',
  grading_mode: 'WEIGHTED',
  final_grading_type: 'PERCENTAGE',
  final_pass_threshold: null,
  missing_policy: 'ZERO_AFTER_DUE',
  certificate_rule: 'FINAL_GRADE',
  categories: [
    { category_uuid: 'category_b', name: 'Project', weight: 60, drop_lowest: 0, position: 1 },
    { category_uuid: 'category_a', name: 'Quizzes', weight: 40, drop_lowest: 1, position: 0 },
  ],
  assignments: [
    { assignment_uuid: 'q1', title: 'Quiz 1', category_uuid: 'category_a', category_weight: 1, never_drop: false, ungraded: false, due_date: null },
    { assignment_uuid: 'q2', title: 'Quiz 2', category_uuid: 'category_a', category_weight: 1, never_drop: false, ungraded: false, due_date: null },
    { assignment_uuid: 'p1', title: 'Project', category_uuid: 'category_b', category_weight: 1, never_drop: false, ungraded: false, due_date: null },
    { assignment_uuid: 'f1', title: 'Reflection', category_uuid: null, category_weight: 1, never_drop: false, ungraded: true, due_date: null },
  ],
  ...over,
})

const codes = (form) => validateGradingForm(form).map((i) => i.code)

describe('grading form', () => {
  test('toForm orders categories by position and round-trips to the payload', () => {
    const form = toForm(grading())
    expect(form.categories.map((c) => c.name)).toEqual(['Quizzes', 'Project'])
    const body = toPayload(form)
    expect(body.categories.map((c) => [c.category_uuid, c.position])).toEqual([
      ['category_a', 0],
      ['category_b', 1],
    ])
    expect(body.final_pass_threshold).toBeNull()
    expect(body.assignments).toHaveLength(4)
  })

  test('a valid setup has no issues', () => {
    expect(codes(toForm(grading()))).toEqual([])
  })

  test('weights must total 100', () => {
    const form = toForm(grading())
    form.categories[0].weight = 30
    expect(weightsTotal(form)).toBe(90)
    const issue = validateGradingForm(form).find((i) => i.code === 'weights_total')
    expect(issue.total).toBe(90)
  })

  test('fractional weights within tolerance pass', () => {
    const form = toForm(grading())
    form.categories[0].weight = 33.33
    form.categories[1].weight = 66.67
    expect(codes(form)).toEqual([])
  })

  test('weighted mode needs a category', () => {
    expect(codes(toForm(grading({ categories: [], assignments: [] })))).toEqual(['no_categories'])
  })

  test('legacy mode ignores the weight total and forces the legacy certificate rule', () => {
    const form = toForm(grading({ grading_mode: 'ALL_MUST_PASS', categories: [], assignments: [] }))
    expect(codes(form)).toEqual([])
    expect(toPayload(form).certificate_rule).toBe('ALL_ASSIGNMENTS')
  })

  test('names are required and unique (case-insensitive)', () => {
    const form = toForm(grading())
    form.categories[0].name = '  '
    expect(codes(form)).toContain('category_name_required')
    form.categories[0].name = 'project'
    expect(codes(form)).toContain('category_name_duplicate')
  })

  test('drop lowest must leave one assignment; formative ones do not count', () => {
    const form = toForm(grading())
    form.categories[0].drop_lowest = 2
    const issue = validateGradingForm(form).find((i) => i.code === 'drop_too_high')
    expect(issue).toEqual({ code: 'drop_too_high', name: 'Quizzes', drop: 2, count: 2 })
  })

  test('empty and negative inputs are caught', () => {
    const form = toForm(grading())
    form.categories[1].weight = ''
    form.assignments[0].category_weight = -1
    form.final_pass_threshold = 120
    const c = codes(form)
    expect(c).toContain('category_weight_invalid')
    expect(c).toContain('assignment_weight_invalid')
    expect(c).toContain('pass_mark_invalid')
  })

  test('an empty assignment weight is sent as 1, drop_lowest as an integer', () => {
    const form = toForm(grading())
    form.assignments[0].category_weight = ''
    form.categories[0].drop_lowest = 1.7
    const body = toPayload(form)
    expect(body.assignments[0].category_weight).toBe(1)
    expect(body.categories[0].drop_lowest).toBe(1)
  })

  test('removing a category uncategorises its assignments', () => {
    const form = removeCategory(toForm(grading()), 'category_a')
    expect(form.categories.map((c) => c.category_uuid)).toEqual(['category_b'])
    expect(form.assignments.filter((a) => a.category_uuid === null).map((a) => a.assignment_uuid)).toEqual([
      'q1',
      'q2',
      'f1',
    ])
  })

  test('a placement pointing at a missing category is sent as uncategorised', () => {
    const form = toForm(grading())
    form.assignments[0].category_uuid = 'category_gone'
    expect(toPayload(form).assignments[0].category_uuid).toBeNull()
  })

  test('evenWeights always totals 100', () => {
    for (const n of [1, 2, 3, 6, 7]) {
      const w = evenWeights(n)
      expect(w).toHaveLength(n)
      expect(Math.round(w.reduce((a, b) => a + b, 0) * 100) / 100).toBe(100)
    }
    expect(evenWeights(0)).toEqual([])
  })

  test('isDirty compares what would be saved', () => {
    const a = toForm(grading())
    const b = toForm(grading())
    expect(isDirty(a, b)).toBe(false)
    b.categories[0].name = 'Quizzes '
    expect(isDirty(a, b)).toBe(false) // trimmed before saving
    b.missing_policy = 'EXCLUDE'
    expect(isDirty(a, b)).toBe(true)
  })
})
