import type {
  CertificateRule,
  CourseGrading,
  CourseGradingUpdate,
  GradingMode,
  GradingType,
  MissingWorkPolicy,
} from './types'

// Editable state of the Grading tab. Numeric inputs hold '' while empty so the
// field can be cleared without snapping back to 0.
export type NumberInput = number | ''

export interface CategoryForm {
  category_uuid: string
  name: string
  weight: NumberInput
  drop_lowest: NumberInput
}

export interface AssignmentForm {
  assignment_uuid: string
  title: string
  ungraded: boolean
  due_date: string | null
  category_uuid: string | null
  category_weight: NumberInput
  never_drop: boolean
}

export interface GradingForm {
  grading_mode: GradingMode
  final_grading_type: GradingType
  final_pass_threshold: NumberInput
  missing_policy: MissingWorkPolicy
  certificate_rule: CertificateRule
  categories: CategoryForm[]
  assignments: AssignmentForm[]
}

export type GradingIssue =
  | { code: 'no_categories' }
  | { code: 'weights_total'; total: number }
  | { code: 'category_name_required'; index: number }
  | { code: 'category_name_duplicate'; name: string }
  | { code: 'category_weight_invalid'; name: string }
  | { code: 'drop_too_high'; name: string; drop: number; count: number }
  | { code: 'assignment_weight_invalid'; title: string }
  | { code: 'pass_mark_invalid' }

// Same tolerance as the API (_WEIGHT_TOLERANCE).
const WEIGHT_TOLERANCE = 0.01

export function newCategoryUuid(): string {
  const id =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  return `category_${id}`
}

export function toForm(grading: CourseGrading): GradingForm {
  return {
    grading_mode: grading.grading_mode,
    final_grading_type: grading.final_grading_type,
    final_pass_threshold: grading.final_pass_threshold ?? '',
    missing_policy: grading.missing_policy,
    certificate_rule: grading.certificate_rule,
    categories: [...grading.categories]
      .sort((a, b) => a.position - b.position)
      .map((c) => ({
        category_uuid: c.category_uuid,
        name: c.name,
        weight: c.weight,
        drop_lowest: c.drop_lowest,
      })),
    assignments: grading.assignments.map((a) => ({
      assignment_uuid: a.assignment_uuid,
      title: a.title,
      ungraded: a.ungraded,
      due_date: a.due_date,
      category_uuid: a.category_uuid,
      category_weight: a.category_weight,
      never_drop: a.never_drop,
    })),
  }
}

const num = (v: NumberInput, fallback = 0): number => (v === '' || Number.isNaN(Number(v)) ? fallback : Number(v))

export function weightsTotal(form: Pick<GradingForm, 'categories'>): number {
  return Math.round(form.categories.reduce((sum, c) => sum + num(c.weight), 0) * 100) / 100
}

/** Assignments that count in a category: placed in it and not formative. */
export function categoryMembers(form: GradingForm, categoryUuid: string): AssignmentForm[] {
  return form.assignments.filter((a) => !a.ungraded && a.category_uuid === categoryUuid)
}

/** Problems that would make the API refuse the save. Empty = savable. */
export function validateGradingForm(form: GradingForm): GradingIssue[] {
  const issues: GradingIssue[] = []
  const weighted = form.grading_mode === 'WEIGHTED'

  if (weighted && form.categories.length === 0) issues.push({ code: 'no_categories' })
  if (weighted && form.categories.length > 0) {
    const total = weightsTotal(form)
    if (Math.abs(total - 100) > WEIGHT_TOLERANCE) issues.push({ code: 'weights_total', total })
  }

  const seen = new Set<string>()
  form.categories.forEach((c, index) => {
    const name = c.name.trim()
    if (!name) {
      issues.push({ code: 'category_name_required', index })
    } else if (seen.has(name.toLowerCase())) {
      issues.push({ code: 'category_name_duplicate', name })
    }
    seen.add(name.toLowerCase())

    const w = c.weight === '' ? NaN : Number(c.weight)
    if (!(w >= 0 && w <= 100)) issues.push({ code: 'category_weight_invalid', name: name || `#${index + 1}` })

    const drop = num(c.drop_lowest)
    const count = categoryMembers(form, c.category_uuid).length
    if (drop > 0 && count > 0 && drop >= count) {
      issues.push({ code: 'drop_too_high', name: name || `#${index + 1}`, drop, count })
    }
  })

  for (const a of form.assignments) {
    if (a.category_uuid === null) continue
    const w = a.category_weight === '' ? NaN : Number(a.category_weight)
    if (!(w >= 0)) issues.push({ code: 'assignment_weight_invalid', title: a.title })
  }

  if (form.final_pass_threshold !== '') {
    const p = Number(form.final_pass_threshold)
    if (!(p >= 0 && p <= 100)) issues.push({ code: 'pass_mark_invalid' })
  }
  return issues
}

/** The PUT body for a form. A non-weighted course can only use the legacy rule. */
export function toPayload(form: GradingForm): CourseGradingUpdate {
  const weighted = form.grading_mode === 'WEIGHTED'
  const known = new Set(form.categories.map((c) => c.category_uuid))
  return {
    grading_mode: form.grading_mode,
    final_grading_type: form.final_grading_type,
    final_pass_threshold: form.final_pass_threshold === '' ? null : Number(form.final_pass_threshold),
    missing_policy: form.missing_policy,
    certificate_rule: weighted ? form.certificate_rule : 'ALL_ASSIGNMENTS',
    categories: form.categories.map((c, position) => ({
      category_uuid: c.category_uuid,
      name: c.name.trim(),
      weight: num(c.weight),
      drop_lowest: Math.max(0, Math.floor(num(c.drop_lowest))),
      position,
    })),
    assignments: form.assignments.map((a) => ({
      assignment_uuid: a.assignment_uuid,
      category_uuid: a.category_uuid && known.has(a.category_uuid) ? a.category_uuid : null,
      category_weight: num(a.category_weight, 1),
      never_drop: a.never_drop,
    })),
  }
}

/** Remove a category; its assignments become uncategorised. */
export function removeCategory(form: GradingForm, categoryUuid: string): GradingForm {
  return {
    ...form,
    categories: form.categories.filter((c) => c.category_uuid !== categoryUuid),
    assignments: form.assignments.map((a) =>
      a.category_uuid === categoryUuid ? { ...a, category_uuid: null } : a
    ),
  }
}

/** Split the remaining weight evenly so a new setup starts at 100%. */
export function evenWeights(count: number): number[] {
  if (count <= 0) return []
  const base = Math.floor((100 / count) * 100) / 100
  const weights = Array(count).fill(base)
  weights[count - 1] = Math.round((100 - base * (count - 1)) * 100) / 100
  return weights
}

export function isDirty(a: GradingForm, b: GradingForm): boolean {
  return JSON.stringify(toPayload(a)) !== JSON.stringify(toPayload(b))
}
