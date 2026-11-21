import { Lifebuoy } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.support',
  titleKey: 'dashboard.support.title',
  descriptionKey: 'dashboard.search.entries.support.description',
  keywordsKey: 'dashboard.search.entries.support.keywords',
  icon: Lifebuoy,
  href: '/dash/support',
  group: 'navigation',
  requiresOrgAdmin: true,
}
