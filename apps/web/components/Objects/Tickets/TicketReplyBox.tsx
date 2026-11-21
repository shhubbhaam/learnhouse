'use client'

import React, { useEffect, useRef, useState } from 'react'
import { ImagePlus, Loader2, Lock, Send, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { Switch } from '@components/ui/switch'
import { Textarea } from '@components/ui/textarea'
import { imageFilesFrom } from '@components/Objects/Communities/useCommunityImageUpload'
import { useTicketsAccessToken } from '@/hooks/queries/useTickets'
import { MAX_ATTACHMENTS, TICKET_IMAGE_TYPES, screenImageFiles } from '@/lib/tickets/attachments'
import { TEXT_MAX, isValidReply } from '@/lib/tickets/validation'
import type { TicketAttachment, TicketStatus } from '@/lib/tickets/types'
import { uploadTicketAttachment } from '@services/tickets/tickets'

interface PendingImage {
  key: string
  previewUrl: string
  attachment: TicketAttachment | null // null while uploading
}

interface TicketReplyBoxProps {
  ticketUuid: string
  status: TicketStatus
  allowInternal: boolean
  /** Resolve on success (box clears); reject on failure (text and images are kept). */
  onSubmit: (content: string, isInternal: boolean, attachmentUuids: string[]) => Promise<void>
}

export default function TicketReplyBox({ ticketUuid, status, allowInternal, onSubmit }: TicketReplyBoxProps) {
  const { t } = useTranslation()
  const token = useTicketsAccessToken()
  const fileInput = useRef<HTMLInputElement>(null)
  const [content, setContent] = useState('')
  const [internal, setInternal] = useState(false)
  const [pending, setPending] = useState(false)
  const [images, setImages] = useState<PendingImage[]>([])

  // Free preview URLs when the box goes away.
  const imagesRef = useRef(images)
  imagesRef.current = images
  useEffect(() => () => imagesRef.current.forEach((i) => URL.revokeObjectURL(i.previewUrl)), [])

  if (status === 'CLOSED') {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
        {t('tickets.reply.closed')}
      </div>
    )
  }

  const internalMode = allowInternal && internal
  const uploading = images.some((i) => i.attachment === null)
  const uploaded = images.filter((i) => i.attachment !== null)
  const trimmed = content.trim()
  const textOk = trimmed.length === 0 ? uploaded.length > 0 : isValidReply(content)
  const canSend = !pending && !uploading && textOk && trimmed.length <= TEXT_MAX

  const addFiles = async (files: File[]) => {
    if (!token || files.length === 0) return
    const { accepted, errors } = screenImageFiles(files, MAX_ATTACHMENTS - images.length)
    errors.forEach((e) => toast.error(t(`tickets.attachments.${e}`)))
    for (const file of accepted) {
      const key = `${Date.now()}-${Math.random()}`
      const previewUrl = URL.createObjectURL(file)
      setImages((list) => [...list, { key, previewUrl, attachment: null }])
      try {
        const attachment = await uploadTicketAttachment(ticketUuid, file, { isInternal: internalMode }, token)
        setImages((list) => list.map((i) => (i.key === key ? { ...i, attachment } : i)))
      } catch (err: any) {
        URL.revokeObjectURL(previewUrl)
        setImages((list) => list.filter((i) => i.key !== key))
        toast.error(err?.message || t('tickets.attachments.upload_failed'))
      }
    }
  }

  const removeImage = (key: string) => {
    setImages((list) => {
      const gone = list.find((i) => i.key === key)
      if (gone) URL.revokeObjectURL(gone.previewUrl)
      return list.filter((i) => i.key !== key)
    })
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSend) return
    setPending(true)
    try {
      await onSubmit(
        trimmed,
        internalMode,
        uploaded.map((i) => i.attachment!.attachment_uuid)
      )
      images.forEach((i) => URL.revokeObjectURL(i.previewUrl))
      setImages([])
      setContent('')
    } catch {
      // The caller reports the error; keep text and images so nothing is lost.
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      {status === 'RESOLVED' && !internalMode && (
        <p className="text-xs text-gray-500">{t('tickets.reply.reopen_hint')}</p>
      )}
      <Textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onPaste={(e) => {
          const files = imageFilesFrom(e.clipboardData)
          if (files.length > 0) {
            e.preventDefault()
            addFiles(files)
          }
        }}
        placeholder={t('tickets.reply.placeholder')}
        rows={3}
        disabled={pending}
        className={`bg-white ${internalMode ? 'border-amber-300 bg-amber-50' : ''}`}
      />

      {images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {images.map((img) => (
            <div key={img.key} className="relative h-16 w-16 overflow-hidden rounded-lg border border-gray-200">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img.previewUrl} alt="" className="h-full w-full object-cover" />
              {img.attachment === null ? (
                <div className="absolute inset-0 flex items-center justify-center bg-white/60">
                  <Loader2 size={16} className="animate-spin text-gray-600" aria-label={t('tickets.attachments.uploading')} />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => removeImage(img.key)}
                  disabled={pending}
                  aria-label={t('tickets.attachments.remove')}
                  className="absolute end-0.5 top-0.5 rounded-full bg-black/60 p-0.5 text-white hover:bg-black"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <input
            ref={fileInput}
            type="file"
            accept={TICKET_IMAGE_TYPES.join(',')}
            multiple
            hidden
            onChange={(e) => {
              addFiles(Array.from(e.target.files || []))
              e.target.value = ''
            }}
          />
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={pending || images.length >= MAX_ATTACHMENTS}
            className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-40"
          >
            <ImagePlus size={14} />
            {t('tickets.attachments.add')}
          </button>
          {allowInternal && (
            <label
              className="flex items-center gap-2 text-xs font-medium text-gray-600 cursor-pointer"
              title={images.length > 0 ? t('tickets.attachments.internal_locked') : undefined}
            >
              {/* Locked while images are attached: they were uploaded as public or internal. */}
              <Switch checked={internal} onCheckedChange={setInternal} disabled={pending || images.length > 0} />
              <Lock size={12} />
              {t('tickets.reply.internal_toggle')}
            </label>
          )}
        </div>
        <button
          type="submit"
          disabled={!canSend}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold text-white transition-all disabled:cursor-not-allowed disabled:opacity-40 ${
            internalMode ? 'bg-amber-600 hover:bg-amber-700' : 'bg-black hover:scale-105'
          }`}
        >
          <Send size={14} />
          {internalMode ? t('tickets.reply.internal_send') : t('tickets.reply.send')}
        </button>
      </div>
    </form>
  )
}
