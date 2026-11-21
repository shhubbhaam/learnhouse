'use client'
import React from 'react'
import { useTranslation } from 'react-i18next'
import { GraduationCap } from 'lucide-react'
import { useMyCourseGrade } from '@/hooks/queries/useCourseGrading'
import {
  type GradeStanding,
  formatPercent,
  gradeStanding,
  pendingCount,
  shouldShowGradeCard,
} from '@/lib/grading/display'
import type { CourseGradeItem } from '@/lib/grading/types'

const STANDING_STYLE: Record<Exclude<GradeStanding, 'none'>, string> = {
  passed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  on_track: 'bg-blue-100 text-blue-800',
  below: 'bg-amber-100 text-amber-800',
}

function ItemRow({ item }: { item: CourseGradeItem }) {
  const { t } = useTranslation()
  const value =
    item.state === 'PENDING'
      ? t('courses.grade_card.pending')
      : item.state === 'MISSING'
        ? t('courses.grade_card.missing')
        : formatPercent(item.percentage)
  return (
    <li className="flex items-center justify-between gap-2 py-1">
      <span className={`truncate ${item.dropped ? 'line-through text-gray-400' : 'text-gray-700'}`} title={item.title}>
        {item.title}
      </span>
      <span className="flex items-center gap-1.5 shrink-0">
        {item.dropped && (
          <span className="text-[10px] uppercase tracking-wide font-semibold text-gray-500 bg-gray-100 rounded px-1.5 py-0.5">
            {t('courses.grade_card.dropped')}
          </span>
        )}
        <span
          className={`tabular-nums ${
            item.state === 'PENDING' ? 'text-gray-400' : item.state === 'MISSING' ? 'text-red-600' : 'text-gray-800'
          } ${item.dropped ? 'line-through text-gray-400' : ''}`}
        >
          {value}
        </span>
      </span>
    </li>
  )
}

/**
 * The learner's weighted course grade, for the course page sidebar. Renders
 * nothing unless the course uses weighted grading and the viewer is an
 * enrolled learner, so other courses look exactly as before.
 */
export default function CourseGradeCard({ courseUuid, enrolled }: { courseUuid: string; enrolled: boolean }) {
  const { t } = useTranslation()
  const { data } = useMyCourseGrade(courseUuid, enrolled)

  if (!enrolled || !data || !shouldShowGradeCard(data)) return null

  const standing = gradeStanding(data)
  const pending = pendingCount(data)

  return (
    <section
      aria-labelledby="course-grade-title"
      className="bg-white shadow-md shadow-gray-300/25 outline outline-1 outline-neutral-200/40 rounded-lg overflow-hidden p-4 space-y-4"
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-gray-800">
        <GraduationCap size={16} className="text-gray-500" />
        <h2 id="course-grade-title">{t('courses.grade_card.title')}</h2>
      </div>

      {standing === 'none' ? (
        <p className="text-sm text-gray-500">{t('courses.grade_card.no_grades_yet')}</p>
      ) : (
        <div className="space-y-1">
          <div className="flex items-end justify-between gap-2">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900 tabular-nums">{data.display_grade}</span>
              {data.grading_type !== 'PERCENTAGE' && (
                <span className="text-sm text-gray-500 tabular-nums">{formatPercent(data.percentage)}</span>
              )}
            </div>
            <span className={`text-xs font-semibold rounded-full px-2 py-0.5 ${STANDING_STYLE[standing]}`}>
              {t(`courses.grade_card.standing.${standing}`)}
            </span>
          </div>
          <p className="text-xs text-gray-500">
            {t('courses.grade_card.pass_mark', { value: formatPercent(data.passing_threshold) })}
          </p>
        </div>
      )}

      {!data.complete && pending > 0 && (
        <p className="text-xs text-gray-600 bg-gray-50 rounded-md px-2.5 py-2">
          {t('courses.grade_card.not_final', { count: pending })}
        </p>
      )}

      <div className="space-y-3">
        {data.categories.map((c) => {
          const width = c.percentage === null ? 0 : Math.max(0, Math.min(100, c.percentage))
          return (
            <details key={c.category_uuid} className="group">
              <summary className="cursor-pointer list-none space-y-1.5">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium text-gray-800 truncate">
                    {c.name}
                    <span className="ms-1.5 text-xs font-normal text-gray-500">
                      {t('courses.grade_card.weight', { value: formatPercent(c.weight) })}
                    </span>
                  </span>
                  <span className="tabular-nums text-gray-800">{formatPercent(c.percentage)}</span>
                </div>
                <div
                  className="h-1.5 rounded-full bg-gray-100 overflow-hidden"
                  role="progressbar"
                  aria-label={c.name}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={c.percentage ?? undefined}
                >
                  <div className="h-full bg-gray-800 rounded-full" style={{ width: `${width}%` }} />
                </div>
                {c.drop_lowest > 0 && (
                  <p className="text-[11px] text-gray-500">
                    {c.complete
                      ? t('courses.grade_card.drop_applied', { count: c.dropped_count })
                      : t('courses.grade_card.drop_later', { count: c.drop_lowest })}
                  </p>
                )}
              </summary>
              <ul className="mt-2 ps-2 border-s border-gray-100 text-xs">
                {c.assignments.map((a) => (
                  <ItemRow key={a.assignment_uuid} item={a} />
                ))}
              </ul>
            </details>
          )
        })}
      </div>
    </section>
  )
}
