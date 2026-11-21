'use client'

import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { priorityMeta, statusMeta } from '@/lib/tickets/labels'
import {
  TICKET_PRIORITIES,
  TICKET_STATUSES,
  type SupportTicket,
  type SupportTicketUpdate,
  type TicketPriority,
  type TicketStatus,
} from '@/lib/tickets/types'
import { authorName } from '@components/Objects/Tickets/TicketAuthorAvatar'
import ResolveTicketDialog from './ResolveTicketDialog'
import CloseTicketDialog from './CloseTicketDialog'

interface TriageBarProps {
  ticket: SupportTicket
  currentUserId?: number
  onUpdate: (data: SupportTicketUpdate) => Promise<void>
}

export default function TriageBar({ ticket, currentUserId, onUpdate }: TriageBarProps) {
  const { t } = useTranslation()
  const [pending, setPending] = useState(false)
  const [resolveOpen, setResolveOpen] = useState(false)
  const [closeOpen, setCloseOpen] = useState(false)

  const run = async (data: SupportTicketUpdate) => {
    setPending(true)
    try {
      await onUpdate(data)
    } finally {
      setPending(false)
    }
  }
  // Inline controls swallow the rejection (the parent already toasted);
  // dialogs re-throw so they stay open.
  const quiet = (data: SupportTicketUpdate) => run(data).catch(() => undefined)

  const assignedToMe = currentUserId !== undefined && ticket.assigned_to === currentUserId
  const isClosed = ticket.status === 'CLOSED'

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg bg-gray-50 p-3">
      <div className="space-y-1">
        <span className="text-xs font-medium text-gray-500">{t('dashboard.support.filter_status')}</span>
        <Select value={ticket.status} disabled={pending} onValueChange={(v) => quiet({ status: v as TicketStatus })}>
          <SelectTrigger className="h-8 w-36 bg-white text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TICKET_STATUSES.map((s) => (
              <SelectItem key={s} value={s} className="text-xs">
                {t(statusMeta(s).labelKey)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <span className="text-xs font-medium text-gray-500">{t('dashboard.support.filter_priority')}</span>
        <Select value={ticket.priority} disabled={pending} onValueChange={(v) => quiet({ priority: v as TicketPriority })}>
          <SelectTrigger className="h-8 w-28 bg-white text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TICKET_PRIORITIES.map((p) => (
              <SelectItem key={p} value={p} className="text-xs">
                {t(priorityMeta(p).labelKey)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <span className="text-xs font-medium text-gray-500">{t('dashboard.support.assignee')}</span>
        <div className="flex h-8 items-center gap-2 text-xs">
          {ticket.assignee && !assignedToMe && <span className="text-gray-700">{authorName(ticket.assignee)}</span>}
          {assignedToMe ? (
            <button
              type="button"
              disabled={pending}
              onClick={() => quiet({ assigned_to: null })}
              className="rounded-md border border-gray-200 bg-white px-2 py-1 font-semibold hover:bg-gray-100 disabled:opacity-40"
            >
              {t('dashboard.support.unassign')}
            </button>
          ) : (
            <button
              type="button"
              disabled={pending || currentUserId === undefined}
              onClick={() => quiet({ assigned_to: currentUserId })}
              className="rounded-md border border-gray-200 bg-white px-2 py-1 font-semibold hover:bg-gray-100 disabled:opacity-40"
            >
              {t('dashboard.support.assign_me')}
            </button>
          )}
        </div>
      </div>

      <div className="ms-auto flex gap-2">
        {isClosed ? (
          <button
            type="button"
            disabled={pending}
            onClick={() => quiet({ status: 'OPEN' })}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-bold hover:bg-gray-100 disabled:opacity-40"
          >
            {t('dashboard.support.reopen')}
          </button>
        ) : (
          <>
            <button
              type="button"
              disabled={pending}
              onClick={() => setCloseOpen(true)}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-bold hover:bg-gray-100 disabled:opacity-40"
            >
              {t('dashboard.support.close')}
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => setResolveOpen(true)}
              className="rounded-lg bg-black px-4 py-2 text-xs font-bold text-white nice-shadow transition-all hover:scale-105 disabled:opacity-40"
            >
              {t('dashboard.support.resolve')}
            </button>
          </>
        )}
      </div>

      <ResolveTicketDialog
        open={resolveOpen}
        initialNote={ticket.resolution_note}
        onOpenChange={setResolveOpen}
        onConfirm={(note) => run({ status: 'RESOLVED', resolution_note: note })}
      />
      <CloseTicketDialog open={closeOpen} onOpenChange={setCloseOpen} onConfirm={() => run({ status: 'CLOSED' })} />
    </div>
  )
}
