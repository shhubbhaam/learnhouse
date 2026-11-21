// Same limits as the backend (apps/api/src/db/tickets/). Measured after
// trimming, because the backend trims before it checks length.
export const SUBJECT_MIN = 3
export const SUBJECT_MAX = 200
export const DESCRIPTION_MIN = 10
export const TEXT_MAX = 10_000

export type LengthError = 'too_short' | 'too_long'

export interface TicketFormErrors {
  subject?: LengthError
  description?: LengthError
}

function lengthError(value: string, min: number, max: number): LengthError | undefined {
  const len = value.trim().length
  if (len < min) return 'too_short'
  if (len > max) return 'too_long'
  return undefined
}

export function validateTicketForm(values: { subject: string; description: string }): TicketFormErrors {
  const errors: TicketFormErrors = {}
  const subject = lengthError(values.subject, SUBJECT_MIN, SUBJECT_MAX)
  const description = lengthError(values.description, DESCRIPTION_MIN, TEXT_MAX)
  if (subject) errors.subject = subject
  if (description) errors.description = description
  return errors
}

export function isValidReply(content: string): boolean {
  return lengthError(content, 1, TEXT_MAX) === undefined
}
