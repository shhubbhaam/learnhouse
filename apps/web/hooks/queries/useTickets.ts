'use client'

import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { queryKeys } from '@lib/query/keys'
import { getMyTickets, getSupportQueue, getTicket } from '@services/tickets/tickets'

function useAccessToken(): string | undefined {
  const session = useLHSession() as any
  return session?.data?.tokens?.access_token as string | undefined
}

export function useMyTickets(orgId?: number) {
  const token = useAccessToken()
  return useQuery({
    queryKey: queryKeys.tickets.mine(orgId!),
    queryFn: () => getMyTickets(orgId!, token),
    enabled: !!orgId && !!token,
    staleTime: 30_000,
  })
}

/** retry: false so a 404 (wrong or foreign uuid) shows "not found" immediately. */
export function useTicket(uuid?: string | null) {
  const token = useAccessToken()
  return useQuery({
    queryKey: queryKeys.tickets.detail(uuid!),
    queryFn: () => getTicket(uuid!, token),
    enabled: !!uuid && !!token,
    staleTime: 30_000,
    retry: false,
  })
}

/** retry: false so a 403 (not staff) shows the access message immediately. */
export function useSupportQueue(orgId: number | undefined, query: string) {
  const token = useAccessToken()
  return useQuery({
    queryKey: queryKeys.tickets.queue(orgId!, query),
    queryFn: () => getSupportQueue(orgId!, query, token),
    enabled: !!orgId && !!token,
    staleTime: 30_000,
    retry: false,
  })
}

/** After any ticket write, refetch every ticket query (lists, detail, queue). */
export function useInvalidateTickets(): () => Promise<void> {
  const queryClient = useQueryClient()
  return useCallback(() => queryClient.invalidateQueries({ queryKey: queryKeys.tickets.all }), [queryClient])
}

export function useTicketsAccessToken(): string | undefined {
  return useAccessToken()
}
