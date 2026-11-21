'use client'

import React from 'react'
import { CheckCircle2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export default function TicketResolutionBox({ note }: { note: string | null }) {
  const { t } = useTranslation()
  if (!note) return null
  return (
    <div className="rounded-lg border border-green-200 bg-green-50 p-4">
      <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-green-800">
        <CheckCircle2 size={16} />
        {t('tickets.resolution')}
      </div>
      <p className="text-sm text-green-900 whitespace-pre-wrap break-words">{note}</p>
    </div>
  )
}
