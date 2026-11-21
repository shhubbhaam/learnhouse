'use client'

import React from 'react'
import { LifeBuoy } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useMyTickets } from '@/hooks/queries/useTickets'
import TicketCard from './TicketCard'

interface MyTicketsListProps {
  orgId?: number
  onOpen: (uuid: string) => void
  onRaise: () => void
}

export default function MyTicketsList({ orgId, onOpen, onRaise }: MyTicketsListProps) {
  const { t } = useTranslation()
  const { data: tickets, isLoading, isError, refetch } = useMyTickets(orgId)

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-20 animate-pulse rounded-xl bg-white nice-shadow" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-xl bg-white p-6 text-center text-sm text-gray-600 nice-shadow">
        {t('tickets.load_error')}{' '}
        <button type="button" onClick={() => refetch()} className="font-semibold underline">
          {t('tickets.retry')}
        </button>
      </div>
    )
  }

  if (!tickets || tickets.length === 0) {
    return (
      <div className="rounded-xl bg-white p-10 text-center nice-shadow">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
          <LifeBuoy size={32} className="text-gray-300" />
        </div>
        <p className="mb-4 text-gray-600">{t('help.empty')}</p>
        <button
          type="button"
          onClick={onRaise}
          className="rounded-lg bg-black px-5 py-2 text-xs font-bold text-white nice-shadow transition-all hover:scale-105"
        >
          {t('help.raise_new')}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {tickets.map((ticket) => (
        <TicketCard key={ticket.ticket_uuid} ticket={ticket} onClick={() => onOpen(ticket.ticket_uuid)} />
      ))}
    </div>
  )
}
