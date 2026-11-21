'use client'

import React from 'react'
import { useTranslation } from 'react-i18next'
import { formatRelative } from '@/lib/format'
import { QUEUE_PAGE_SIZE } from '@/lib/tickets/filters'
import { categoryLabelKey } from '@/lib/tickets/labels'
import type { SupportTicketPage } from '@/lib/tickets/types'
import { TicketPriorityBadge, TicketStatusBadge } from '@components/Objects/Tickets/TicketBadges'
import TicketAuthorAvatar, { authorName } from '@components/Objects/Tickets/TicketAuthorAvatar'

interface SupportQueueTableProps {
  page: SupportTicketPage
  selectedUuid: string | null
  onSelect: (uuid: string) => void
  onPage: (n: number) => void
}

export default function SupportQueueTable({ page, selectedUuid, onSelect, onPage }: SupportQueueTableProps) {
  const { t, i18n } = useTranslation()

  if (page.items.length === 0) {
    return (
      <div className="rounded-xl bg-white p-8 text-center text-sm text-gray-500 nice-shadow">
        {t('dashboard.support.empty')}
      </div>
    )
  }

  const from = (page.page - 1) * QUEUE_PAGE_SIZE + 1
  const to = from + page.items.length - 1
  const lastPage = Math.max(1, Math.ceil(page.total / QUEUE_PAGE_SIZE))

  return (
    <div className="overflow-hidden rounded-xl bg-white nice-shadow">
      <ul className="divide-y divide-gray-100">
        {page.items.map((ticket) => {
          const active = ticket.ticket_uuid === selectedUuid
          return (
            <li key={ticket.ticket_uuid}>
              <button
                type="button"
                onClick={() => onSelect(ticket.ticket_uuid)}
                className={`w-full p-3 text-start transition-colors ${active ? 'bg-gray-100' : 'hover:bg-gray-50'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 text-sm font-semibold text-gray-900 line-clamp-2 break-words">
                    {ticket.subject}
                  </span>
                  <TicketPriorityBadge priority={ticket.priority} />
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
                  <TicketStatusBadge status={ticket.status} />
                  <span>{authorName(ticket.author)}</span>
                  <span>·</span>
                  <span>{t(categoryLabelKey(ticket.category))}</span>
                  <span>·</span>
                  <span>{formatRelative(ticket.creation_date, i18n.language)}</span>
                  <span className="ms-auto flex items-center gap-1">
                    {ticket.assignee ? (
                      <>
                        <TicketAuthorAvatar author={ticket.assignee} width={18} />
                        <span className="truncate max-w-[8rem]">{authorName(ticket.assignee)}</span>
                      </>
                    ) : (
                      <span className="italic">{t('dashboard.support.unassigned')}</span>
                    )}
                  </span>
                </div>
              </button>
            </li>
          )
        })}
      </ul>
      <div className="flex items-center justify-between border-t border-gray-100 px-3 py-2 text-xs text-gray-500">
        <span>{t('dashboard.support.showing', { from, to, total: page.total })}</span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page.page <= 1}
            onClick={() => onPage(page.page - 1)}
            className="rounded-md px-2 py-1 font-semibold hover:bg-gray-100 disabled:opacity-40"
          >
            {t('dashboard.support.previous')}
          </button>
          <button
            type="button"
            disabled={page.page >= lastPage}
            onClick={() => onPage(page.page + 1)}
            className="rounded-md px-2 py-1 font-semibold hover:bg-gray-100 disabled:opacity-40"
          >
            {t('dashboard.support.next')}
          </button>
        </div>
      </div>
    </div>
  )
}
