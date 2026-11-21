'use client'

import React from 'react'
import { useTranslation } from 'react-i18next'
import { formatRelative } from '@/lib/format'
import type { TicketMessage } from '@/lib/tickets/types'
import TicketAuthorAvatar, { authorName } from './TicketAuthorAvatar'
import TicketAttachmentGrid from './TicketAttachmentGrid'

interface TicketThreadProps {
  messages: TicketMessage[]
  viewerUserId?: number
}

function messageStyle(m: TicketMessage): { box: string; label?: string } {
  if (m.is_internal) return { box: 'bg-amber-50 border-amber-200', label: 'tickets.thread.internal' }
  if (m.is_staff) return { box: 'bg-sky-50 border-sky-100', label: 'tickets.thread.support_team' }
  return { box: 'bg-white border-gray-100' }
}

export default function TicketThread({ messages, viewerUserId }: TicketThreadProps) {
  const { t, i18n } = useTranslation()
  if (messages.length === 0) return null

  return (
    <ul className="space-y-3">
      {messages.map((m) => {
        const style = messageStyle(m)
        const isViewer = viewerUserId !== undefined && m.author_id === viewerUserId
        return (
          <li key={m.message_uuid} className={`flex gap-3 rounded-lg border p-3 ${style.box}`}>
            <div className="flex-shrink-0">
              <TicketAuthorAvatar author={m.author} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
                <span className="font-semibold text-gray-800">
                  {isViewer ? t('tickets.thread.you') : authorName(m.author)}
                </span>
                {style.label && (
                  <span className="rounded bg-white/70 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-[10px] text-gray-600">
                    {t(style.label)}
                  </span>
                )}
                <span>{formatRelative(m.creation_date, i18n.language)}</span>
              </div>
              {m.content && (
                <p className="mt-1 text-sm text-gray-800 whitespace-pre-wrap break-words">{m.content}</p>
              )}
              <TicketAttachmentGrid attachments={m.attachments} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
