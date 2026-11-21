import {
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  TICKET_STATUSES,
  type TicketQueueFilters,
} from './types'

export const QUEUE_PAGE_SIZE = 25

export const DEFAULT_FILTERS: TicketQueueFilters = {
  status: 'OPEN',
  priority: 'ALL',
  category: 'ALL',
  mine: false,
  page: 1,
}

function pick<T extends string>(value: string | null, allowed: readonly T[], fallback: T | 'ALL'): T | 'ALL' {
  if (value === 'ALL') return 'ALL'
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : fallback
}

function parsePage(value: string | null): number {
  if (!value || !/^\d+$/.test(value)) return DEFAULT_FILTERS.page
  const n = Number(value)
  return n >= 1 ? n : DEFAULT_FILTERS.page
}

/** Read the dashboard URL. Each field is validated on its own; junk falls back to its default. */
export function queryToFilters(params: URLSearchParams): TicketQueueFilters {
  return {
    status: pick(params.get('status'), TICKET_STATUSES, DEFAULT_FILTERS.status),
    priority: pick(params.get('priority'), TICKET_PRIORITIES, DEFAULT_FILTERS.priority),
    category: pick(params.get('category'), TICKET_CATEGORIES, DEFAULT_FILTERS.category),
    mine: params.get('mine') === '1',
    page: parsePage(params.get('page')),
  }
}

/** Dashboard URL: only values that differ from the defaults, so the default view has a clean URL. */
export function filtersToSearchParams(filters: TicketQueueFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.status !== DEFAULT_FILTERS.status) params.set('status', filters.status)
  if (filters.priority !== DEFAULT_FILTERS.priority) params.set('priority', filters.priority)
  if (filters.category !== DEFAULT_FILTERS.category) params.set('category', filters.category)
  if (filters.mine) params.set('mine', '1')
  if (filters.page !== DEFAULT_FILTERS.page) params.set('page', String(filters.page))
  return params
}

/** Query string for GET /tickets/org/{id}/admin. */
export function filtersToApiQuery(filters: TicketQueueFilters, currentUserId: number): string {
  const params = new URLSearchParams()
  if (filters.status !== 'ALL') params.set('status', filters.status)
  if (filters.priority !== 'ALL') params.set('priority', filters.priority)
  if (filters.category !== 'ALL') params.set('category', filters.category)
  if (filters.mine) params.set('assigned_to', String(currentUserId))
  params.set('page', String(filters.page))
  params.set('limit', String(QUEUE_PAGE_SIZE))
  return params.toString()
}
