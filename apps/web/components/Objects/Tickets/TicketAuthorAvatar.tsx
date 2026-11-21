'use client'

import React from 'react'
import UserAvatar from '@components/Objects/UserAvatar'
import { getUserAvatarMediaDirectory } from '@services/media/media'
import type { TicketAuthor } from '@/lib/tickets/types'

// Same resolution rules as community comments (CommentCard.getAvatarUrl).
export function ticketAvatarUrl(author: TicketAuthor | null): string | undefined {
  if (!author?.avatar_image) return undefined
  if (author.avatar_image.startsWith('http://') || author.avatar_image.startsWith('https://')) {
    return author.avatar_image
  }
  return getUserAvatarMediaDirectory(author.user_uuid, author.avatar_image)
}

export function authorName(author: TicketAuthor | null): string {
  if (!author) return '—'
  const full = `${author.first_name ?? ''} ${author.last_name ?? ''}`.trim()
  return full || author.username
}

export default function TicketAuthorAvatar({ author, width = 32 }: { author: TicketAuthor | null; width?: number }) {
  return (
    <UserAvatar
      width={width}
      rounded="rounded-full"
      avatar_url={ticketAvatarUrl(author)}
      predefined_avatar={author?.avatar_image ? undefined : 'empty'}
      shadow="shadow-none"
    />
  )
}
