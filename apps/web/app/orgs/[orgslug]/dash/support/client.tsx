'use client'

import React from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, LifeBuoy } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { Breadcrumbs } from '@components/Objects/Breadcrumbs/Breadcrumbs'
import { useSupportQueue } from '@/hooks/queries/useTickets'
import { filtersToApiQuery, filtersToSearchParams, queryToFilters } from '@/lib/tickets/filters'
import type { TicketQueueFilters } from '@/lib/tickets/types'
import SupportQueueFilters from '@components/Dashboard/Pages/Support/SupportQueueFilters'
import SupportQueueTable from '@components/Dashboard/Pages/Support/SupportQueueTable'
import StaffTicketDetail from '@components/Dashboard/Pages/Support/StaffTicketDetail'

interface SupportDashClientProps {
  orgId: number
  orgslug: string
}

export default function SupportDashClient({ orgId }: SupportDashClientProps) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const currentUserId: number | undefined = session?.data?.user?.id
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const filters = queryToFilters(new URLSearchParams(searchParams.toString()))
  const selected = searchParams.get('ticket')
  const { data: page, isLoading, error, refetch } = useSupportQueue(
    currentUserId ? orgId : undefined,
    filtersToApiQuery(filters, currentUserId ?? 0)
  )

  const go = (nextFilters: TicketQueueFilters, ticket: string | null) => {
    const params = filtersToSearchParams(nextFilters)
    if (ticket) params.set('ticket', ticket)
    const qs = params.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }

  const status = (error as any)?.status
  if (status === 403) {
    return (
      <div className="h-full w-full bg-[#f8f8f8] ps-4 pe-4 sm:ps-10 sm:pe-10">
        <div className="pt-6">
          <Breadcrumbs items={[{ label: t('dashboard.support.title'), href: '/dash/support', icon: <LifeBuoy size={14} /> }]} />
          <div className="mt-8 rounded-xl bg-white p-8 text-center text-gray-600 nice-shadow">
            {t('dashboard.support.access_denied')}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full bg-[#f8f8f8] ps-4 pe-4 pb-10 sm:ps-10 sm:pe-10">
      <div className="mb-6 pt-6">
        <Breadcrumbs items={[{ label: t('dashboard.support.title'), href: '/dash/support', icon: <LifeBuoy size={14} /> }]} />
        <h1 className="mt-4 text-3xl font-bold">{t('dashboard.support.title')}</h1>
      </div>

      <div className="lg:grid lg:grid-cols-5 lg:gap-6">
        <section className={`lg:col-span-2 space-y-4 ${selected ? 'hidden lg:block' : ''}`}>
          <SupportQueueFilters filters={filters} onChange={(next) => go({ ...next, page: 1 }, selected)} />
          {isLoading ? (
            <div className="h-64 animate-pulse rounded-xl bg-white nice-shadow" />
          ) : error ? (
            <div className="rounded-xl bg-white p-6 text-center text-sm text-gray-600 nice-shadow">
              {t('tickets.load_error')}{' '}
              <button type="button" onClick={() => refetch()} className="font-semibold underline">
                {t('tickets.retry')}
              </button>
            </div>
          ) : page ? (
            <SupportQueueTable
              page={page}
              selectedUuid={selected}
              onSelect={(uuid) => go(filters, uuid)}
              onPage={(n) => go({ ...filters, page: n }, selected)}
            />
          ) : null}
        </section>

        <section className={`lg:col-span-3 ${selected ? '' : 'hidden lg:block'}`}>
          {selected ? (
            <>
              <button
                type="button"
                onClick={() => go(filters, null)}
                className="mb-3 flex items-center gap-1 text-sm text-gray-600 hover:text-black lg:hidden"
              >
                <ArrowLeft size={14} />
                {t('dashboard.support.back')}
              </button>
              <StaffTicketDetail
                uuid={selected}
                currentUserId={currentUserId}
                onNotFound={() => go(filters, null)}
              />
            </>
          ) : (
            <div className="rounded-xl border-2 border-dashed border-gray-200 p-10 text-center text-sm text-gray-400">
              {t('dashboard.support.select_ticket')}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
