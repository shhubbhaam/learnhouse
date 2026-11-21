'use client'

import React from 'react'
import { useTranslation } from 'react-i18next'
import { priorityMeta, statusMeta } from '@/lib/tickets/labels'

function Pill({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${className}`}>
      {label}
    </span>
  )
}

export function TicketStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const meta = statusMeta(status)
  return <Pill label={t(meta.labelKey)} className={meta.className} />
}

export function TicketPriorityBadge({ priority }: { priority: string }) {
  const { t } = useTranslation()
  const meta = priorityMeta(priority)
  return <Pill label={t(meta.labelKey)} className={meta.className} />
}
