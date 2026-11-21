'use client'

import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@components/ui/dialog'

interface CloseTicketDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => Promise<void>
}

export default function CloseTicketDialog({ open, onOpenChange, onConfirm }: CloseTicketDialogProps) {
  const { t } = useTranslation()
  const [pending, setPending] = useState(false)

  const confirm = async () => {
    if (pending) return
    setPending(true)
    try {
      await onConfirm()
      onOpenChange(false)
    } catch {
      // Parent shows the error toast.
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !pending && onOpenChange(o)}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t('dashboard.support.close_confirm')}</DialogTitle>
        </DialogHeader>
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
            disabled={pending}
            className="rounded-lg bg-red-600 px-4 py-2 text-xs font-bold text-white nice-shadow disabled:opacity-40"
          >
            {t('dashboard.support.close')}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
