import { getAPIUrl } from '@services/config/config'
import { RequestBodyFormWithAuthHeader, RequestBodyWithAuthHeader, errorHandling } from '@services/utils/ts/requests'
import type {
  SupportTicket,
  SupportTicketCreate,
  SupportTicketDetail,
  SupportTicketPage,
  SupportTicketUpdate,
  TicketAttachment,
  TicketMessage,
} from '@/lib/tickets/types'

export type {
  SupportTicket,
  SupportTicketCreate,
  SupportTicketDetail,
  SupportTicketPage,
  SupportTicketUpdate,
  TicketAttachment,
  TicketAuthor,
  TicketCategory,
  TicketCourseRef,
  TicketMessage,
  TicketPriority,
  TicketQueueFilters,
  TicketStatus,
} from '@/lib/tickets/types'

// Every call throws on a non-2xx response; the error carries `.status` and the
// backend's `detail` as its message (see errorHandling).

async function request<T>(method: string, path: string, data: unknown, token?: string): Promise<T> {
  const res = await fetch(`${getAPIUrl()}${path}`, RequestBodyWithAuthHeader(method, data, null, token))
  return errorHandling(res)
}

export function getMyTickets(orgId: number, token?: string): Promise<SupportTicket[]> {
  return request('GET', `tickets/org/${orgId}/me`, null, token)
}

export function getTicket(uuid: string, token?: string): Promise<SupportTicketDetail> {
  return request('GET', `tickets/${uuid}`, null, token)
}

export function getSupportQueue(orgId: number, query: string, token?: string): Promise<SupportTicketPage> {
  return request('GET', `tickets/org/${orgId}/admin?${query}`, null, token)
}

export function createTicket(data: SupportTicketCreate, token?: string): Promise<SupportTicket> {
  return request('POST', 'tickets/', data, token)
}

export function replyToTicket(
  uuid: string,
  data: { content: string; is_internal?: boolean; attachment_uuids?: string[] },
  token?: string
): Promise<TicketMessage> {
  return request('POST', `tickets/${uuid}/messages`, data, token)
}

export function updateTicket(uuid: string, data: SupportTicketUpdate, token?: string): Promise<SupportTicket> {
  return request('PATCH', `tickets/${uuid}`, data, token)
}

/** Upload one image. Pending until a reply sends its attachment_uuid, unless attachToTicket. */
export async function uploadTicketAttachment(
  uuid: string,
  file: File,
  opts: { isInternal?: boolean; attachToTicket?: boolean },
  token: string
): Promise<TicketAttachment> {
  const form = new FormData()
  form.append('file', file)
  form.append('is_internal', opts.isInternal ? 'true' : 'false')
  form.append('attach_to_ticket', opts.attachToTicket ? 'true' : 'false')
  const res = await fetch(
    `${getAPIUrl()}tickets/${uuid}/attachments`,
    RequestBodyFormWithAuthHeader('POST', form, null, token)
  )
  return errorHandling(res)
}
