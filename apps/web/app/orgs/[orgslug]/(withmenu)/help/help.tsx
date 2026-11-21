'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useOrg } from '@components/Contexts/OrgContext'
import GeneralWrapperStyled from '@components/Objects/StyledElements/Wrappers/GeneralWrapper'
import TypeOfContentTitle from '@components/Objects/StyledElements/Titles/TypeOfContentTitle'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import MyTicketsList from '@components/Pages/Help/MyTicketsList'
import LearnerTicketDetail from '@components/Pages/Help/LearnerTicketDetail'
import RaiseTicketForm from '@components/Pages/Help/RaiseTicketForm'
import { getUriWithOrg } from '@services/config/config'

type HelpTab = 'mine' | 'raise'

export default function Help({ orgslug }: { orgslug: string }) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const org = useOrg() as any
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const tab: HelpTab = searchParams.get('tab') === 'raise' ? 'raise' : 'mine'
  const ticketUuid = searchParams.get('ticket')

  const navigate = (next: { tab?: HelpTab; ticket?: string | null }) => {
    const params = new URLSearchParams()
    const nextTab = next.tab ?? tab
    if (nextTab === 'raise') params.set('tab', 'raise')
    const nextTicket = next.ticket === undefined ? ticketUuid : next.ticket
    if (nextTicket && nextTab === 'mine') params.set('ticket', nextTicket)
    const qs = params.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }

  const isSignedIn = session?.status === 'authenticated' || !!session?.data?.tokens?.access_token

  return (
    <GeneralWrapperStyled>
      <TypeOfContentTitle title={t('help.title')} type="help" />

      {session?.status === 'loading' ? null : !isSignedIn ? (
        <div className="rounded-xl bg-white p-8 text-center nice-shadow">
          <p className="mb-4 text-gray-600">{t('help.sign_in')}</p>
          <Link
            href={getUriWithOrg(orgslug, '/login')}
            className="inline-flex rounded-lg bg-black px-5 py-2 text-xs font-bold text-white nice-shadow"
          >
            {t('auth.login')}
          </Link>
        </div>
      ) : (
        <Tabs value={tab} onValueChange={(v) => navigate({ tab: v as HelpTab, ticket: null })}>
          <TabsList className="mb-4">
            <TabsTrigger value="mine">{t('help.tab_my_tickets')}</TabsTrigger>
            <TabsTrigger value="raise">{t('help.tab_raise')}</TabsTrigger>
          </TabsList>

          <TabsContent value="mine">
            {ticketUuid ? (
              <LearnerTicketDetail uuid={ticketUuid} onBack={() => navigate({ ticket: null })} />
            ) : (
              <MyTicketsList
                orgId={org?.id}
                onOpen={(uuid) => navigate({ ticket: uuid })}
                onRaise={() => navigate({ tab: 'raise', ticket: null })}
              />
            )}
          </TabsContent>

          <TabsContent value="raise">
            <RaiseTicketForm
              orgId={org?.id}
              orgslug={orgslug}
              onCreated={(uuid) => navigate({ tab: 'mine', ticket: uuid })}
            />
          </TabsContent>
        </Tabs>
      )}
    </GeneralWrapperStyled>
  )
}
