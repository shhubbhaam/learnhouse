'use client'

import React from 'react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { formatRelative } from '@/lib/format'
import { categoryLabelKey } from '@/lib/tickets/labels'
import type { SupportTicketUpdate } from '@/lib/tickets/types'
import { useInvalidateTickets, useTicket, useTicketsAccessToken } from '@/hooks/queries/useTickets'
import { replyToTicket, updateTicket } from '@services/tickets/tickets'
import { TicketPriorityBadge, TicketStatusBadge } from '@components/Objects/Tickets/TicketBadges'
import TicketAuthorAvatar, { authorName } from '@components/Objects/Tickets/TicketAuthorAvatar'
import TicketResolutionBox from '@components/Objects/Tickets/TicketResolutionBox'
import TicketThread from '@components/Objects/Tickets/TicketThread'
import TicketAttachmentGrid from '@components/Objects/Tickets/TicketAttachmentGrid'
import TicketReplyBox from '@components/Objects/Tickets/TicketReplyBox'
import TriageBar from './TriageBar'

interface StaffTicketDetailProps {
  uuid: string
  currentUserId?: number
  onNotFound: () => void
}

export default function StaffTicketDetail({ uuid, currentUserId, onNotFound }: StaffTicketDetailProps) {
  const { t, i18n } = useTranslation()
  const token = useTicketsAccessToken()
  const invalidate = useInvalidateTickets()
  const { data: ticket, isLoading, error } = useTicket(uuid)

  if (isLoading) return <div className="h-80 animate-pulse rounded-xl bg-white nice-shadow" />

  if (error || !ticket) {
    return (
      <div className="rounded-xl bg-white p-6 text-sm text-gray-600 nice-shadow">
        {t('tickets.not_found')}{' '}
        <button type="button" onClick={onNotFound} className="font-semibold underline">
          {t('dashboard.support.back')}
        </button>
      </div>
    )
  }

  const onUpdate = async (data: SupportTicketUpdate) => {
    try {
      await updateTicket(uuid, data, token)
      toast.success(t('dashboard.support.updated'))
    } catch (e: any) {
      toast.error(e?.message || String(e))
      throw e
    } finally {
      await invalidate()
    }
  }

  const onReply = async (content: string, isInternal: boolean, attachmentUuids: string[]) => {
    try {
      await replyToTicket(uuid, { content, is_internal: isInternal, attachment_uuids: attachmentUuids }, token)
      toast.success(t('tickets.reply.sent'))
    } catch (e: any) {
      toast.error(e?.message || String(e))
      throw e
    } finally {
      await invalidate()
    }
  }

  return (
    <div className="space-y-4 rounded-xl bg-white p-5 nice-shadow">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="min-w-0 text-lg font-bold text-gray-900 break-words">{ticket.subject}</h2>
        <div className="flex gap-2">
          <TicketPriorityBadge priority={ticket.priority} />
          <TicketStatusBadge status={ticket.status} />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-gray-500">
        <span className="flex items-center gap-2">
          <TicketAuthorAvatar author={ticket.author} width={24} />
          <span className="font-semibold text-gray-800">{authorName(ticket.author)}</span>
          {ticket.author && <span>@{ticket.author.username}</span>}
        </span>
        <span>{t(categoryLabelKey(ticket.category))}</span>
        {ticket.course && <span>{ticket.course.name}</span>}
        <span>{t('tickets.opened', { time: formatRelative(ticket.creation_date, i18n.language) })}</span>
      </div>

      <TriageBar ticket={ticket} currentUserId={currentUserId} onUpdate={onUpdate} />

      <p className="text-sm text-gray-800 whitespace-pre-wrap break-words">{ticket.description}</p>
      <TicketAttachmentGrid attachments={ticket.attachments} />
      <TicketResolutionBox note={ticket.resolution_note} />
      <TicketThread messages={ticket.messages} viewerUserId={currentUserId} />
      <TicketReplyBox ticketUuid={uuid} status={ticket.status} allowInternal onSubmit={onReply} />
    </div>
  )
}
