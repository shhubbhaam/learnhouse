import React from 'react'
import { Metadata } from 'next'
import { getOrganizationContextInfo } from '@services/organizations/orgs'
import Help from './help'

export const dynamic = 'force-dynamic'

type MetadataProps = {
  params: Promise<{ orgslug: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export async function generateMetadata(props: MetadataProps): Promise<Metadata> {
  const params = await props.params
  const org = await getOrganizationContextInfo(params.orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })
  return {
    title: 'Help & Support | ' + org.name,
    description: 'Get help with your account and courses.',
  }
}

const HelpPage = async (params: any) => {
  const orgslug = (await params.params).orgslug
  return <Help orgslug={orgslug} />
}

export default HelpPage
