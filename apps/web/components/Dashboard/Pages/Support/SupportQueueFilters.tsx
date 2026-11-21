'use client'

import React from 'react'
import { useTranslation } from 'react-i18next'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { Switch } from '@components/ui/switch'
import { categoryLabelKey, priorityMeta, statusMeta } from '@/lib/tickets/labels'
import { TICKET_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES, type TicketQueueFilters } from '@/lib/tickets/types'

interface SupportQueueFiltersProps {
  filters: TicketQueueFilters
  onChange: (next: TicketQueueFilters) => void
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-1">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-8 bg-white text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value} className="text-xs">
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export default function SupportQueueFilters({ filters, onChange }: SupportQueueFiltersProps) {
  const { t } = useTranslation()
  const all = { value: 'ALL', label: t('dashboard.support.all') }

  return (
    <div className="rounded-xl bg-white p-4 nice-shadow">
      <div className="grid grid-cols-3 gap-3">
        <FilterSelect
          label={t('dashboard.support.filter_status')}
          value={filters.status}
          options={[all, ...TICKET_STATUSES.map((s) => ({ value: s, label: t(statusMeta(s).labelKey) }))]}
          onChange={(v) => onChange({ ...filters, status: v as TicketQueueFilters['status'] })}
        />
        <FilterSelect
          label={t('dashboard.support.filter_priority')}
          value={filters.priority}
          options={[all, ...TICKET_PRIORITIES.map((p) => ({ value: p, label: t(priorityMeta(p).labelKey) }))]}
          onChange={(v) => onChange({ ...filters, priority: v as TicketQueueFilters['priority'] })}
        />
        <FilterSelect
          label={t('dashboard.support.filter_category')}
          value={filters.category}
          options={[all, ...TICKET_CATEGORIES.map((c) => ({ value: c, label: t(categoryLabelKey(c)) }))]}
          onChange={(v) => onChange({ ...filters, category: v as TicketQueueFilters['category'] })}
        />
      </div>
      <label className="mt-3 flex cursor-pointer items-center gap-2 text-xs font-medium text-gray-600">
        <Switch checked={filters.mine} onCheckedChange={(mine) => onChange({ ...filters, mine })} />
        {t('dashboard.support.assigned_to_me')}
      </label>
    </div>
  )
}
