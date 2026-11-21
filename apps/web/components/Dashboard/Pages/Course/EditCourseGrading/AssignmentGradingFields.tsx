'use client'
import React from 'react'
import { useTranslation } from 'react-i18next'
import { Layers } from 'lucide-react'
import type { CourseGrading } from '@/lib/grading/types'
import { type NumberInput, toForm, toPayload } from '@/lib/grading/form'

export interface AssignmentPlacement {
  category_uuid: string | null
  category_weight: NumberInput
  never_drop: boolean
}

export function placementOf(grading: CourseGrading | undefined, assignmentUuid: string): AssignmentPlacement | null {
  const a = grading?.assignments.find((x) => x.assignment_uuid === assignmentUuid)
  return a ? { category_uuid: a.category_uuid, category_weight: a.category_weight, never_drop: a.never_drop } : null
}

export function samePlacement(a: AssignmentPlacement | null, b: AssignmentPlacement | null): boolean {
  if (!a || !b) return a === b
  return (
    a.category_uuid === b.category_uuid &&
    Number(a.category_weight === '' ? 1 : a.category_weight) === Number(b.category_weight === '' ? 1 : b.category_weight) &&
    a.never_drop === b.never_drop
  )
}

/** The full grading PUT body with one assignment's placement changed. */
export function payloadWithPlacement(grading: CourseGrading, assignmentUuid: string, placement: AssignmentPlacement) {
  const form = toForm(grading)
  form.assignments = form.assignments.map((a) =>
    a.assignment_uuid === assignmentUuid ? { ...a, ...placement } : a
  )
  return toPayload(form)
}

const inputClass =
  'w-full h-9 px-3 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors disabled:text-gray-400'

/** Category, weight and never-drop for one assignment, shown in its settings modal. */
export default function AssignmentGradingFields({
  grading,
  value,
  onChange,
}: {
  grading: CourseGrading
  value: AssignmentPlacement
  onChange: (next: AssignmentPlacement) => void
}) {
  const { t } = useTranslation()
  const category = grading.categories.find((c) => c.category_uuid === value.category_uuid)

  return (
    <div className="space-y-3 rounded-lg border border-gray-200 p-3">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
        <Layers size={15} />
        {t('dashboard.courses.grading.assignment_fields.title')}
      </div>
      <p className="text-xs text-gray-500">{t('dashboard.courses.grading.assignment_fields.description')}</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-xs font-medium text-gray-600">{t('dashboard.courses.grading.assignments.category')}</span>
          <select
            className={inputClass}
            value={value.category_uuid ?? ''}
            onChange={(e) => onChange({ ...value, category_uuid: e.target.value || null })}
          >
            <option value="">{t('dashboard.courses.grading.assignments.uncategorised')}</option>
            {grading.categories.map((c) => (
              <option key={c.category_uuid} value={c.category_uuid}>
                {t('dashboard.courses.grading.assignment_fields.category_option', { name: c.name, weight: c.weight })}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">{t('dashboard.courses.grading.assignments.weight')}</span>
          <input
            type="number"
            min={0}
            step="any"
            className={inputClass}
            disabled={!value.category_uuid}
            value={value.category_weight}
            onChange={(e) =>
              onChange({ ...value, category_weight: e.target.value === '' ? '' : Number(e.target.value) })
            }
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          className="h-4 w-4 accent-blue-600"
          disabled={!value.category_uuid}
          checked={value.never_drop}
          onChange={(e) => onChange({ ...value, never_drop: e.target.checked })}
        />
        {t('dashboard.courses.grading.assignments.never_drop')}
        {category && category.drop_lowest > 0 && (
          <span className="text-xs text-gray-500">
            {t('dashboard.courses.grading.assignment_fields.drop_note', { count: category.drop_lowest })}
          </span>
        )}
      </label>
    </div>
  )
}
