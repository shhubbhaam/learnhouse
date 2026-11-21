'use client'

import React from 'react'
import { MessageSquare } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { formatRelative } from '@/lib/format'
import { categoryLabelKey } from '@/lib/tickets/labels'
import type { SupportTicket } from '@/lib/tickets/types'
import { TicketStatusBadge } from '@components/Objects/Tickets/TicketBadges'

export default function TicketCard({ ticket, onClick }: { ticket: SupportTicket; onClick: () => void }) {
  const { t, i18n } = useTranslation()
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-xl bg-white p-4 text-start nice-shadow transition-all hover:scale-[1.005] hover:bg-gray-50"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 font-semibold text-gray-900 line-clamp-2 break-words">{ticket.subject}</h3>
        <TicketStatusBadge status={ticket.status} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
        <span>{t(categoryLabelKey(ticket.category))}</span>
        {ticket.course && <span className="truncate max-w-[16rem]">{ticket.course.name}</span>}
        <span>{t('tickets.updated', { time: formatRelative(ticket.update_date, i18n.language) })}</span>
        <span className="flex items-center gap-1">
          <MessageSquare size={12} />
          {t('tickets.messages_count', { count: ticket.message_count })}
        </span>
      </div>
    </button>
  )
}
