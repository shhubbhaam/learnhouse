'use client'

import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@components/ui/dialog'
import { Textarea } from '@components/ui/textarea'
import { TEXT_MAX } from '@/lib/tickets/validation'

interface ResolveTicketDialogProps {
  open: boolean
  initialNote: string | null
  onOpenChange: (open: boolean) => void
  onConfirm: (note: string) => Promise<void>
}

export default function ResolveTicketDialog({ open, initialNote, onOpenChange, onConfirm }: ResolveTicketDialogProps) {
  const { t } = useTranslation()
  const [note, setNote] = useState(initialNote ?? '')
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (open) setNote(initialNote ?? '')
  }, [open, initialNote])

  const trimmed = note.trim()
  const canConfirm = !pending && trimmed.length > 0 && trimmed.length <= TEXT_MAX

  const confirm = async () => {
    if (!canConfirm) return
    setPending(true)
    try {
      await onConfirm(trimmed)
      onOpenChange(false)
    } catch {
      // Parent shows the error toast; keep the dialog open with the text.
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !pending && onOpenChange(o)}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('dashboard.support.resolve_title')}</DialogTitle>
          <DialogDescription>{t('dashboard.support.resolve_note_hint')}</DialogDescription>
        </DialogHeader>
        <Textarea
          value={note}
          rows={5}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t('dashboard.support.resolve_note')}
          disabled={pending}
        />
        <DialogFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={pending}
            className="rounded-lg px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100"
          >
            {t('dashboard.support.cancel')}
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={!canConfirm}
            className="rounded-lg bg-black px-4 py-2 text-xs font-bold text-white nice-shadow disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t('dashboard.support.resolve_confirm')}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
