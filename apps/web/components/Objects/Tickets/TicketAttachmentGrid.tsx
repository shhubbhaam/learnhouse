'use client'

import React, { useState } from 'react'
import { ImageOff, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Modal from '@components/Objects/StyledElements/Modal/Modal'
import { useTicketsAccessToken } from '@/hooks/queries/useTickets'
import { ticketAttachmentUrl } from '@/lib/tickets/attachments'
import type { TicketAttachment } from '@/lib/tickets/types'
import { useAuthedImage } from './useAuthedImage'

function Thumbnail({ attachment, token, onOpen }: { attachment: TicketAttachment; token?: string; onOpen: () => void }) {
  const { t } = useTranslation()
  const { src, error } = useAuthedImage(ticketAttachmentUrl(attachment.file_path), token)

  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={!src}
      title={t('tickets.attachments.view')}
      className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-lg border border-gray-200 bg-gray-50 hover:opacity-90 disabled:cursor-default"
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="h-full w-full object-cover" />
      ) : error ? (
        <ImageOff size={18} className="text-gray-400" aria-label={t('tickets.attachments.image_unavailable')} />
      ) : (
        <Loader2 size={18} className="animate-spin text-gray-300" />
      )}
    </button>
  )
}

function FullImage({ attachment, token }: { attachment: TicketAttachment; token?: string }) {
  const { t } = useTranslation()
  const { src, error } = useAuthedImage(ticketAttachmentUrl(attachment.file_path), token)
  if (error) return <p className="p-6 text-sm text-gray-500">{t('tickets.attachments.image_unavailable')}</p>
  if (!src) return <Loader2 className="m-10 animate-spin text-gray-300" />
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt="" className="max-h-[80vh] max-w-full object-contain" />
}

export default function TicketAttachmentGrid({ attachments }: { attachments: TicketAttachment[] }) {
  const token = useTicketsAccessToken()
  const [open, setOpen] = useState<TicketAttachment | null>(null)
  if (!attachments || attachments.length === 0) return null

  return (
    <>
      <div className="mt-2 flex flex-wrap gap-2">
        {attachments.map((a) => (
          <Thumbnail key={a.attachment_uuid} attachment={a} token={token} onOpen={() => setOpen(a)} />
        ))}
      </div>
      <Modal
        isDialogOpen={!!open}
        onOpenChange={(o) => !o && setOpen(null)}
        noPadding
        dialogContent={
          <div className="flex items-center justify-center bg-gray-50 p-2">
            {open && <FullImage attachment={open} token={token} />}
          </div>
        }
      />
    </>
  )
}
