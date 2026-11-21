import { TICKET_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES } from './types'

export interface BadgeMeta {
  labelKey: string
  className: string
}

const NEUTRAL = 'bg-gray-100 text-gray-600'

const STATUS_CLASSES: Record<string, string> = {
  OPEN: 'bg-blue-100 text-blue-700',
  IN_PROGRESS: 'bg-amber-100 text-amber-700',
  RESOLVED: 'bg-green-100 text-green-700',
  CLOSED: 'bg-gray-200 text-gray-600',
}

const PRIORITY_CLASSES: Record<string, string> = {
  URGENT: 'bg-red-100 text-red-700',
  HIGH: 'bg-orange-100 text-orange-700',
  MEDIUM: 'bg-gray-100 text-gray-700',
  LOW: 'bg-slate-100 text-slate-500',
}

// Values outside the known enums (a newer backend, a bad cache) get a neutral
// badge instead of throwing.
export function statusMeta(status: string | null | undefined): BadgeMeta {
  if (status && (TICKET_STATUSES as readonly string[]).includes(status)) {
    return { labelKey: `tickets.status.${status}`, className: STATUS_CLASSES[status] }
  }
  return { labelKey: 'tickets.status.unknown', className: NEUTRAL }
}

export function priorityMeta(priority: string | null | undefined): BadgeMeta {
  if (priority && (TICKET_PRIORITIES as readonly string[]).includes(priority)) {
    return { labelKey: `tickets.priority.${priority}`, className: PRIORITY_CLASSES[priority] }
  }
  return { labelKey: 'tickets.priority.unknown', className: NEUTRAL }
}

export function categoryLabelKey(category: string | null | undefined): string {
  if (category && (TICKET_CATEGORIES as readonly string[]).includes(category)) {
    return `tickets.category.${category}`
  }
  return 'tickets.category.OTHER'
}
