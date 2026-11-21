'use client'

import React from 'react'
import { ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { formatRelative } from '@/lib/format'
import { categoryLabelKey } from '@/lib/tickets/labels'
import { useInvalidateTickets, useTicket, useTicketsAccessToken } from '@/hooks/queries/useTickets'
import { replyToTicket } from '@services/tickets/tickets'
import { TicketStatusBadge } from '@components/Objects/Tickets/TicketBadges'
import TicketResolutionBox from '@components/Objects/Tickets/TicketResolutionBox'
import TicketThread from '@components/Objects/Tickets/TicketThread'
import TicketAttachmentGrid from '@components/Objects/Tickets/TicketAttachmentGrid'
import TicketReplyBox from '@components/Objects/Tickets/TicketReplyBox'

export default function LearnerTicketDetail({ uuid, onBack }: { uuid: string; onBack: () => void }) {
  const { t, i18n } = useTranslation()
  const session = useLHSession() as any
  const token = useTicketsAccessToken()
  const invalidate = useInvalidateTickets()
  const { data: ticket, isLoading, error } = useTicket(uuid)

  const back = (
    <button type="button" onClick={onBack} className="mb-4 flex items-center gap-1 text-sm text-gray-600 hover:text-black">
      <ArrowLeft size={14} />
      {t('help.back')}
    </button>
  )

  if (isLoading) {
    return (
      <div>
        {back}
        <div className="h-48 animate-pulse rounded-xl bg-white nice-shadow" />
      </div>
    )
  }

  if (error || !ticket) {
    return (
      <div>
        {back}
        <div className="rounded-xl bg-white p-6 text-sm text-gray-600 nice-shadow">{t('tickets.not_found')}</div>
      </div>
    )
  }

  const onReply = async (content: string, attachmentUuids: string[]) => {
    try {
      await replyToTicket(uuid, { content, attachment_uuids: attachmentUuids }, token)
      toast.success(t('tickets.reply.sent'))
    } catch (e: any) {
      toast.error(e?.message || String(e))
      throw e
    } finally {
      // Status may have changed (reopened, or closed by staff meanwhile).
      await invalidate()
    }
  }

  return (
    <div>
      {back}
      <div className="space-y-4 rounded-xl bg-white p-5 nice-shadow">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="min-w-0 text-lg font-bold text-gray-900 break-words">{ticket.subject}</h2>
          <TicketStatusBadge status={ticket.status} />
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
          <span>{t(categoryLabelKey(ticket.category))}</span>
          {ticket.course && <span>{ticket.course.name}</span>}
          <span>{t('tickets.opened', { time: formatRelative(ticket.creation_date, i18n.language) })}</span>
        </div>
        <p className="text-sm text-gray-800 whitespace-pre-wrap break-words">{ticket.description}</p>
        <TicketAttachmentGrid attachments={ticket.attachments} />

        <TicketResolutionBox note={ticket.resolution_note} />
        <TicketThread messages={ticket.messages} viewerUserId={session?.data?.user?.id} />
        <TicketReplyBox
          ticketUuid={uuid}
          status={ticket.status}
          allowInternal={false}
          onSubmit={(content, _internal, attachmentUuids) => onReply(content, attachmentUuids)}
        />
      </div>
    </div>
  )
}
