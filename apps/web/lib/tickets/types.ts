// Mirrors the backend schemas in apps/api/src/db/tickets/. Keep in sync.

export const TICKET_STATUSES = ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'] as const
export const TICKET_PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'] as const
export const TICKET_CATEGORIES = ['TECHNICAL', 'COURSE_CONTENT', 'BILLING', 'ACCOUNT', 'OTHER'] as const

export type TicketStatus = (typeof TICKET_STATUSES)[number]
export type TicketPriority = (typeof TICKET_PRIORITIES)[number]
export type TicketCategory = (typeof TICKET_CATEGORIES)[number]

export interface TicketAuthor {
  id: number
  user_uuid: string
  username: string
  first_name: string
  last_name: string
  avatar_image?: string | null
}

export interface TicketCourseRef {
  id: number
  course_uuid: string
  name: string
}

export interface SupportTicket {
  id: number
  ticket_uuid: string
  org_id: number
  subject: string
  description: string
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  resolution_note: string | null
  user_id: number
  course_id: number | null
  assigned_to: number | null
  creation_date: string
  update_date: string
  author: TicketAuthor | null
  assignee: TicketAuthor | null
  course: TicketCourseRef | null
  message_count: number
}

export interface TicketAttachment {
  attachment_uuid: string
  /** Content-relative path; see ticketAttachmentUrl. */
  file_path: string
  content_type: string
  size: number
  is_internal: boolean
}

export interface TicketMessage {
  id: number
  message_uuid: string
  ticket_id: number
  author_id: number
  content: string
  is_staff: boolean
  is_internal: boolean
  creation_date: string
  author: TicketAuthor | null
  attachments: TicketAttachment[]
}

export type SupportTicketDetail = SupportTicket & {
  messages: TicketMessage[]
  /** Images raised with the ticket (shown under the description). */
  attachments: TicketAttachment[]
}

export interface SupportTicketPage {
  items: SupportTicket[]
  total: number
  page: number
  limit: number
}

export interface SupportTicketCreate {
  org_id: number
  subject: string
  description: string
  category: TicketCategory
  course_id?: number | null
}

export interface SupportTicketUpdate {
  status?: TicketStatus
  priority?: TicketPriority
  assigned_to?: number | null
  resolution_note?: string | null
}

export interface TicketQueueFilters {
  status: TicketStatus | 'ALL'
  priority: TicketPriority | 'ALL'
  category: TicketCategory | 'ALL'
  mine: boolean
  page: number
}
