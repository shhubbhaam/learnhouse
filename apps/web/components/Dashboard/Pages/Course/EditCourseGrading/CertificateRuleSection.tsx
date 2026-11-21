'use client'
import React from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import { Loader2, ShieldCheck } from 'lucide-react'
import { useCourseGrading, useSaveCourseGrading } from '@/hooks/queries/useCourseGrading'
import { toForm, toPayload } from '@/lib/grading/form'
import type { CertificateRule } from '@/lib/grading/types'
import { getUriWithOrg } from '@services/config/config'

const RULES: CertificateRule[] = ['ALL_ASSIGNMENTS', 'FINAL_GRADE', 'BOTH']

/**
 * "Who earns the certificate" — the course's certificate rule. Lives in the
 * Certification tab but is stored with the grading setup, so it saves through
 * the grading endpoint (immediately, since the API re-checks certificates).
 */
export default function CertificateRuleSection({ courseUuid, orgslug }: { courseUuid: string; orgslug: string }) {
  const { t } = useTranslation()
  const { data, isPending, error } = useCourseGrading(courseUuid)
  const save = useSaveCourseGrading(courseUuid)

  if (error) return null
  if (isPending || !data) {
    return <div className="h-24 bg-gray-50 rounded-lg animate-pulse mb-6" />
  }

  const weighted = data.grading_mode === 'WEIGHTED'
  const current: CertificateRule = weighted ? data.certificate_rule : 'ALL_ASSIGNMENTS'
  const gradingHref = getUriWithOrg(orgslug, `/dash/courses/course/${courseUuid.replace('course_', '')}/grading`)

  const choose = async (rule: CertificateRule) => {
    if (rule === current || save.isPending) return
    try {
      const result = await save.mutateAsync({ ...toPayload(toForm(data)), certificate_rule: rule })
      toast.success(t('dashboard.courses.grading.certificate_rule.saved'))
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
    <div className="mb-6">
      <div className="flex flex-col bg-gray-50 -space-y-1 px-3 sm:px-5 py-3 rounded-md mb-3">
        <h3 className="font-bold text-md text-gray-800 flex items-center gap-2">
          <ShieldCheck size={16} />
          {t('dashboard.courses.grading.certificate_rule.title')}
          {save.isPending && <Loader2 size={14} className="animate-spin text-gray-400" />}
        </h3>
        <p className="text-gray-500 text-xs sm:text-sm">{t('dashboard.courses.grading.certificate_rule.subtitle')}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {RULES.map((rule) => {
          const disabled = !weighted && rule !== 'ALL_ASSIGNMENTS'
          const selected = current === rule
          return (
            <label
              key={rule}
              className={`flex gap-3 items-start p-3 rounded-lg border transition-colors ${
                disabled
                  ? 'border-gray-100 bg-gray-50 opacity-60 cursor-not-allowed'
                  : selected
                    ? 'border-blue-400 bg-blue-50 cursor-pointer'
                    : 'border-gray-200 bg-white hover:bg-gray-50 cursor-pointer'
              }`}
            >
              <input
                type="radio"
                name="certificate_rule"
                className="mt-1 accent-blue-600"
                checked={selected}
                disabled={disabled || save.isPending}
                onChange={() => choose(rule)}
              />
              <span className="flex flex-col">
                <span className="text-sm font-semibold text-gray-800">
                  {t(`dashboard.courses.grading.certificate_rule.${rule.toLowerCase()}`)}
                </span>
                <span className="text-xs text-gray-500">
                  {t(`dashboard.courses.grading.certificate_rule.${rule.toLowerCase()}_hint`)}
                </span>
              </span>
            </label>
          )
        })}
      </div>
      {!weighted && (
        <p className="text-xs text-gray-500 mt-2">
          {t('dashboard.courses.grading.certificate_rule.needs_weighted')}{' '}
          <Link href={gradingHref} className="text-blue-600 hover:underline">
            {t('dashboard.courses.grading.certificate_rule.open_grading')}
          </Link>
        </p>
      )}
    </div>
  )
}
