'use client'
import React, { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import {
  AlertTriangle,
  CheckCircle2,
  Layers,
  ListChecks,
  Loader2,
  Plus,
  Scale,
  Target,
  Trash2,
} from 'lucide-react'
import { useCourse } from '@components/Contexts/CourseContext'
import { useCourseGrading, useSaveCourseGrading } from '@/hooks/queries/useCourseGrading'
import {
  type GradingForm,
  type GradingIssue,
  type NumberInput,
  categoryMembers,
  evenWeights,
  isDirty,
  newCategoryUuid,
  removeCategory,
  toForm,
  toPayload,
  validateGradingForm,
  weightsTotal,
} from '@/lib/grading/form'
import type { GradingMode, GradingType, MissingWorkPolicy } from '@/lib/grading/types'

const inputClass =
  'w-full h-9 px-3 text-sm rounded-lg bg-white border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors disabled:bg-gray-50 disabled:text-gray-400'
const GRADING_TYPES: GradingType[] = ['PERCENTAGE', 'ALPHABET', 'NUMERIC', 'PASS_FAIL', 'GPA_SCALE']
const GRADING_TYPE_KEY: Record<GradingType, string> = {
  PERCENTAGE: 'percentage',
  ALPHABET: 'alphabet',
  NUMERIC: 'numeric',
  PASS_FAIL: 'pass_fail',
  GPA_SCALE: 'gpa_scale',
}

const toNumberInput = (raw: string): NumberInput => (raw === '' ? '' : Number(raw))

function SectionHeader({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle: string }) {
  return (
    <div className="flex flex-col bg-gray-50 -space-y-1 px-3 sm:px-5 py-3 rounded-md mb-3">
      <h3 className="font-bold text-md text-gray-800 flex items-center gap-2">
        {icon}
        {title}
      </h3>
      <p className="text-gray-500 text-xs sm:text-sm">{subtitle}</p>
    </div>
  )
}

function ChoiceCard({
  selected,
  onSelect,
  title,
  hint,
  name,
}: {
  selected: boolean
  onSelect: () => void
  title: string
  hint: string
  name: string
}) {
  return (
    <label
      className={`flex gap-3 items-start p-3 rounded-lg border cursor-pointer transition-colors ${
        selected ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white hover:bg-gray-50'
      }`}
    >
      <input type="radio" name={name} checked={selected} onChange={onSelect} className="mt-1 accent-blue-600" />
      <span className="flex flex-col">
        <span className="text-sm font-semibold text-gray-800">{title}</span>
        <span className="text-xs text-gray-500">{hint}</span>
      </span>
    </label>
  )
}

function issueMessage(issue: GradingIssue, t: (key: string, opts?: any) => string): string {
  const k = `dashboard.courses.grading.issues.${issue.code}`
  switch (issue.code) {
    case 'weights_total':
      return t(k, { total: issue.total })
    case 'category_name_required':
      return t(k, { index: issue.index + 1 })
    case 'category_name_duplicate':
    case 'category_weight_invalid':
      return t(k, { name: issue.name })
    case 'drop_too_high':
      return t(k, { name: issue.name, drop: issue.drop, count: issue.count })
    case 'assignment_weight_invalid':
      return t(k, { title: issue.title })
    default:
      return t(k)
  }
}

function EditCourseGrading(_props: { orgslug: string }) {
  const { t } = useTranslation()
  const { courseStructure } = useCourse() as any
  const courseUuid: string | undefined = courseStructure?.course_uuid
  const { data, isPending, error } = useCourseGrading(courseUuid)
  const save = useSaveCourseGrading(courseUuid)

  const saved = useMemo(() => (data ? toForm(data) : null), [data])
  const [form, setForm] = useState<GradingForm | null>(null)
  useEffect(() => {
    if (saved) setForm(saved)
  }, [saved])

  const issues = useMemo(() => (form ? validateGradingForm(form) : []), [form])
  const dirty = !!(form && saved && isDirty(form, saved))

  if (isPending || !form) {
    if (error) {
      return (
        <div className="mx-4 sm:mx-10 bg-white rounded-xl shadow-xs px-4 py-6 text-sm text-red-700">
          {t('dashboard.courses.grading.errors.loading')}
        </div>
      )
    }
    return (
      <div className="mx-4 sm:mx-10 bg-white rounded-xl shadow-xs px-4 py-4">
        <div className="animate-pulse space-y-4">
          <div className="h-14 bg-gray-50 rounded-md" />
          <div className="h-24 bg-gray-100 rounded-lg" />
          <div className="h-40 bg-gray-100 rounded-lg" />
        </div>
      </div>
    )
  }

  const weighted = form.grading_mode === 'WEIGHTED'
  const total = weightsTotal(form)
  const totalOk = Math.abs(total - 100) <= 0.01
  const gradedAssignments = form.assignments.filter((a) => !a.ungraded)
  const uncategorised = gradedAssignments.filter((a) => !a.category_uuid).length

  const update = (patch: Partial<GradingForm>) => setForm((f) => (f ? { ...f, ...patch } : f))
  const updateCategory = (uuid: string, patch: Partial<GradingForm['categories'][number]>) =>
    setForm((f) =>
      f ? { ...f, categories: f.categories.map((c) => (c.category_uuid === uuid ? { ...c, ...patch } : c)) } : f
    )
  const updateAssignment = (uuid: string, patch: Partial<GradingForm['assignments'][number]>) =>
    setForm((f) =>
      f ? { ...f, assignments: f.assignments.map((a) => (a.assignment_uuid === uuid ? { ...a, ...patch } : a)) } : f
    )

  const setMode = (mode: GradingMode) => {
    if (mode === 'WEIGHTED' && form.categories.length === 0) {
      // Start with one category holding every graded assignment, so the course
      // grade works the moment weighted mode is switched on.
      const uuid = newCategoryUuid()
      update({
        grading_mode: mode,
        categories: [{ category_uuid: uuid, name: t('dashboard.courses.grading.categories.default_name'), weight: 100, drop_lowest: 0 }],
        assignments: form.assignments.map((a) => (a.ungraded ? a : { ...a, category_uuid: uuid })),
      })
    } else {
      update({ grading_mode: mode })
    }
  }

  const addCategory = () =>
    update({
      categories: [
        ...form.categories,
        { category_uuid: newCategoryUuid(), name: '', weight: Math.max(0, Math.round((100 - total) * 100) / 100), drop_lowest: 0 },
      ],
    })

  const splitEvenly = () => {
    const weights = evenWeights(form.categories.length)
    update({ categories: form.categories.map((c, i) => ({ ...c, weight: weights[i] })) })
  }

  const onSave = async () => {
    if (issues.length) return
    try {
      const result = await save.mutateAsync(toPayload(form))
      toast.success(t('dashboard.courses.grading.toasts.saved'))
      if (result.certificates_issued || result.certificates_revoked) {
        toast(
          t('dashboard.courses.grading.toasts.certificates_changed', {
            issued: result.certificates_issued,
            revoked: result.certificates_revoked,
          }),
          { duration: 6000 }
        )
      }
    } catch (e: any) {
      toast.error(e?.message || t('dashboard.courses.grading.toasts.error'))
    }
  }

  return (
    <div className="mx-4 sm:mx-10 bg-white rounded-xl shadow-xs px-4 py-4 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap gap-3 items-center justify-between bg-gray-50 px-3 sm:px-5 py-3 rounded-md">
        <div className="flex flex-col -space-y-1">
          <h1 className="font-bold text-lg sm:text-xl text-gray-800">{t('dashboard.courses.grading.title')}</h1>
          <h2 className="text-gray-500 text-xs sm:text-sm">{t('dashboard.courses.grading.subtitle')}</h2>
        </div>
        <div className="flex items-center gap-3">
          {dirty && <span className="text-xs text-amber-600">{t('dashboard.courses.grading.unsaved')}</span>}
          <button
            type="button"
            onClick={() => saved && setForm(saved)}
            disabled={!dirty || save.isPending}
            className="h-9 px-3 text-sm rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-40"
          >
            {t('dashboard.courses.grading.discard')}
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={!dirty || issues.length > 0 || save.isPending}
            className="h-9 px-4 text-sm font-semibold rounded-lg bg-black text-white hover:bg-gray-800 disabled:opacity-40 flex items-center gap-2"
          >
            {save.isPending && <Loader2 size={14} className="animate-spin" />}
            {save.isPending ? t('dashboard.courses.grading.saving') : t('dashboard.courses.grading.save')}
          </button>
        </div>
      </div>

      {issues.length > 0 && dirty && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-1" role="alert">
          {issues.map((issue, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-red-800">
              <AlertTriangle size={14} className="shrink-0" />
              {issueMessage(issue, t)}
            </div>
          ))}
        </div>
      )}

      {/* Grading method */}
      <section>
        <SectionHeader
          icon={<Scale size={16} />}
          title={t('dashboard.courses.grading.mode.title')}
          subtitle={t('dashboard.courses.grading.mode.subtitle')}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <ChoiceCard
            name="grading_mode"
            selected={!weighted}
            onSelect={() => setMode('ALL_MUST_PASS')}
            title={t('dashboard.courses.grading.mode.all_must_pass')}
            hint={t('dashboard.courses.grading.mode.all_must_pass_hint')}
          />
          <ChoiceCard
            name="grading_mode"
            selected={weighted}
            onSelect={() => setMode('WEIGHTED')}
            title={t('dashboard.courses.grading.mode.weighted')}
            hint={t('dashboard.courses.grading.mode.weighted_hint')}
          />
        </div>
      </section>

      {weighted && (
        <>
          {/* Categories */}
          <section>
            <SectionHeader
              icon={<Layers size={16} />}
              title={t('dashboard.courses.grading.categories.title')}
              subtitle={t('dashboard.courses.grading.categories.subtitle')}
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-start text-xs text-gray-500 border-b border-gray-100">
                    <th className="text-start font-medium py-2 pe-3">{t('dashboard.courses.grading.categories.name')}</th>
                    <th className="text-start font-medium py-2 pe-3 w-32">{t('dashboard.courses.grading.categories.weight')}</th>
                    <th className="text-start font-medium py-2 pe-3 w-40">
                      <span title={t('dashboard.courses.grading.categories.drop_lowest_hint')}>
                        {t('dashboard.courses.grading.categories.drop_lowest')}
                      </span>
                    </th>
                    <th className="text-start font-medium py-2 pe-3">{t('dashboard.courses.grading.categories.counted')}</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {form.categories.map((c) => {
                    const members = categoryMembers(form, c.category_uuid).length
                    const drop = c.drop_lowest === '' ? 0 : Number(c.drop_lowest)
                    return (
                      <tr key={c.category_uuid} className="border-b border-gray-50">
                        <td className="py-2 pe-3">
                          <input
                            className={inputClass}
                            value={c.name}
                            placeholder={t('dashboard.courses.grading.categories.name_placeholder')}
                            aria-label={t('dashboard.courses.grading.categories.name')}
                            onChange={(e) => updateCategory(c.category_uuid, { name: e.target.value })}
                          />
                        </td>
                        <td className="py-2 pe-3">
                          <div className="relative">
                            <input
                              type="number"
                              min={0}
                              max={100}
                              step="any"
                              className={`${inputClass} pe-7`}
                              value={c.weight}
                              aria-label={t('dashboard.courses.grading.categories.weight')}
                              onChange={(e) => updateCategory(c.category_uuid, { weight: toNumberInput(e.target.value) })}
                            />
                            <span className="absolute end-3 top-2 text-gray-400 text-sm">%</span>
                          </div>
                        </td>
                        <td className="py-2 pe-3">
                          <input
                            type="number"
                            min={0}
                            step={1}
                            className={inputClass}
                            value={c.drop_lowest}
                            aria-label={t('dashboard.courses.grading.categories.drop_lowest')}
                            onChange={(e) => updateCategory(c.category_uuid, { drop_lowest: toNumberInput(e.target.value) })}
                          />
                        </td>
                        <td className="py-2 pe-3 text-xs text-gray-500">
                          {drop > 0 && members > 0
                            ? t('dashboard.courses.grading.categories.best_of', { kept: Math.max(members - drop, 1), count: members })
                            : t('dashboard.courses.grading.categories.all_of', { count: members })}
                        </td>
                        <td className="py-2 text-end">
                          <button
                            type="button"
                            onClick={() => setForm(removeCategory(form, c.category_uuid))}
                            className="p-2 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50"
                            aria-label={t('dashboard.courses.grading.categories.remove')}
                            title={t('dashboard.courses.grading.categories.remove')}
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 mt-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={addCategory}
                  className="h-8 px-3 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 flex items-center gap-1.5"
                >
                  <Plus size={14} /> {t('dashboard.courses.grading.categories.add')}
                </button>
                {form.categories.length > 1 && (
                  <button
                    type="button"
                    onClick={splitEvenly}
                    className="h-8 px-3 text-sm rounded-lg text-gray-600 hover:bg-gray-50"
                  >
                    {t('dashboard.courses.grading.categories.split_evenly')}
                  </button>
                )}
              </div>
              <div
                className={`flex items-center gap-1.5 text-sm font-semibold ${totalOk ? 'text-green-700' : 'text-red-700'}`}
              >
                {totalOk ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
                {t('dashboard.courses.grading.categories.total', { total })}
              </div>
            </div>
          </section>

          {/* Assignments */}
          <section>
            <SectionHeader
              icon={<ListChecks size={16} />}
              title={t('dashboard.courses.grading.assignments.title')}
              subtitle={t('dashboard.courses.grading.assignments.subtitle')}
            />
            {uncategorised > 0 && (
              <div className="flex items-center gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
                <AlertTriangle size={14} />
                {t('dashboard.courses.grading.assignments.uncategorised_warning', { count: uncategorised })}
              </div>
            )}
            {form.assignments.length === 0 ? (
              <p className="text-sm text-gray-500 px-1">{t('dashboard.courses.grading.assignments.empty')}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-500 border-b border-gray-100">
                      <th className="text-start font-medium py-2 pe-3">{t('dashboard.courses.grading.assignments.assignment')}</th>
                      <th className="text-start font-medium py-2 pe-3 w-56">{t('dashboard.courses.grading.assignments.category')}</th>
                      <th className="text-start font-medium py-2 pe-3 w-28">
                        <span title={t('dashboard.courses.grading.assignments.weight_hint')}>
                          {t('dashboard.courses.grading.assignments.weight')}
                        </span>
                      </th>
                      <th className="text-start font-medium py-2 w-28">
                        <span title={t('dashboard.courses.grading.assignments.never_drop_hint')}>
                          {t('dashboard.courses.grading.assignments.never_drop')}
                        </span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {form.assignments.map((a) => (
                      <tr key={a.assignment_uuid} className={`border-b border-gray-50 ${a.ungraded ? 'opacity-60' : ''}`}>
                        <td className="py-2 pe-3">
                          <div className="font-medium text-gray-800">{a.title}</div>
                          {a.ungraded && (
                            <div className="text-xs text-gray-500">{t('dashboard.courses.grading.assignments.formative')}</div>
                          )}
                        </td>
                        <td className="py-2 pe-3">
                          <select
                            className={inputClass}
                            value={a.category_uuid ?? ''}
                            disabled={a.ungraded}
                            aria-label={t('dashboard.courses.grading.assignments.category')}
                            onChange={(e) => updateAssignment(a.assignment_uuid, { category_uuid: e.target.value || null })}
                          >
                            <option value="">{t('dashboard.courses.grading.assignments.uncategorised')}</option>
                            {form.categories.map((c) => (
                              <option key={c.category_uuid} value={c.category_uuid}>
                                {c.name.trim() || t('dashboard.courses.grading.categories.unnamed')}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2 pe-3">
                          <input
                            type="number"
                            min={0}
                            step="any"
                            className={inputClass}
                            value={a.category_weight}
                            disabled={a.ungraded || !a.category_uuid}
                            aria-label={t('dashboard.courses.grading.assignments.weight')}
                            onChange={(e) => updateAssignment(a.assignment_uuid, { category_weight: toNumberInput(e.target.value) })}
                          />
                        </td>
                        <td className="py-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-blue-600"
                            checked={a.never_drop}
                            disabled={a.ungraded || !a.category_uuid}
                            aria-label={t('dashboard.courses.grading.assignments.never_drop')}
                            onChange={(e) => updateAssignment(a.assignment_uuid, { never_drop: e.target.checked })}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Final grade */}
          <section>
            <SectionHeader
              icon={<Target size={16} />}
              title={t('dashboard.courses.grading.final.title')}
              subtitle={t('dashboard.courses.grading.final.subtitle')}
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-gray-700">{t('dashboard.courses.grading.final.grade_type')}</span>
                <select
                  className={inputClass}
                  value={form.final_grading_type}
                  onChange={(e) => update({ final_grading_type: e.target.value as GradingType })}
                >
                  {GRADING_TYPES.map((g) => (
                    <option key={g} value={g}>
                      {t(`dashboard.assignments.modals.edit.form.grading_types.${GRADING_TYPE_KEY[g]}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-gray-700">{t('dashboard.courses.grading.final.pass_mark')}</span>
                <div className="relative">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step="any"
                    className={`${inputClass} pe-7`}
                    value={form.final_pass_threshold}
                    placeholder={t('dashboard.courses.grading.final.pass_mark_placeholder', {
                      default: form.final_grading_type === 'ALPHABET' || form.final_grading_type === 'GPA_SCALE' ? 60 : 50,
                    })}
                    onChange={(e) => update({ final_pass_threshold: toNumberInput(e.target.value) })}
                  />
                  <span className="absolute end-3 top-2 text-gray-400 text-sm">%</span>
                </div>
              </label>
            </div>
            <div className="mt-4 space-y-1.5">
              <span className="text-sm font-medium text-gray-700">{t('dashboard.courses.grading.final.missing_work')}</span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(['ZERO_AFTER_DUE', 'EXCLUDE'] as MissingWorkPolicy[]).map((p) => (
                  <ChoiceCard
                    key={p}
                    name="missing_policy"
                    selected={form.missing_policy === p}
                    onSelect={() => update({ missing_policy: p })}
                    title={t(`dashboard.courses.grading.final.missing.${p.toLowerCase()}`)}
                    hint={t(`dashboard.courses.grading.final.missing.${p.toLowerCase()}_hint`)}
                  />
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

export default EditCourseGrading
