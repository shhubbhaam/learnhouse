import { getBackendUrl, getConfig } from '@services/config/config'

// Same rules as the backend (apps/api/src/db/tickets/ticket_attachments.py).
export const TICKET_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
export const TICKET_IMAGE_MAX_BYTES = 10 * 1024 * 1024
export const MAX_ATTACHMENTS = 5

export type AttachmentError = 'unsupported_type' | 'too_large' | 'too_many'

interface FileLike {
  type: string
  size: number
}

/** Keep the files that may be uploaded, in order, and say (once each) why others were dropped. */
export function screenImageFiles<F extends FileLike>(
  files: F[],
  remaining: number
): { accepted: F[]; errors: AttachmentError[] } {
  const errors = new Set<AttachmentError>()
  const images = files.filter((f) => TICKET_IMAGE_TYPES.includes(f.type))
  if (images.length < files.length) errors.add('unsupported_type')
  let accepted = images.filter((f) => f.size <= TICKET_IMAGE_MAX_BYTES)
  if (accepted.length < images.length) errors.add('too_large')
  const slots = Math.max(0, remaining)
  if (accepted.length > slots) {
    errors.add('too_many')
    accepted = accepted.slice(0, slots)
  }
  return { accepted, errors: [...errors] }
}

// Mirrors getMediaUrl() in services/media/media.ts (not exported there).
function mediaBaseUrl(): string {
  const raw = getConfig('NEXT_PUBLIC_LEARNHOUSE_MEDIA_URL') || getBackendUrl()
  return raw.endsWith('/') ? raw : `${raw}/`
}

/** Full URL of a ticket image. It is private: load it with the bearer token (useAuthedImage). */
export function ticketAttachmentUrl(filePath: string): string {
  return `${mediaBaseUrl()}content/${filePath.replace(/^\/+/, '')}`
}
