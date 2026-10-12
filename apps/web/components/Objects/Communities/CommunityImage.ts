import { Node, mergeAttributes } from '@tiptap/core'
import { getCommunityMediaDirectory } from '@services/media/media'

/**
 * Image uploaded to a community (discussion body or reply).
 *
 * The node stores only the uploaded file id and the org/community it belongs
 * to, never a URL: the API rejects any image that does not reference a file
 * of the same community, so posts can't hotlink external images. The URL is
 * built here at render time from the configured media host.
 */
export interface CommunityImageAttrs {
  fileId: string
  orgUuid: string
  communityUuid: string
  alt?: string | null
}

// Mirrors COMMUNITY_MEDIA_FILE_PATTERN on the API.
const FILE_ID = /^[0-9a-fA-F-]{36}_media\.(?:jpg|png|gif|webp)$/
const SAFE_UUID = /^[A-Za-z0-9_-]+$/

export function communityImageUrl(attrs: Partial<CommunityImageAttrs>): string {
  const { fileId, orgUuid, communityUuid } = attrs
  if (
    !fileId || !orgUuid || !communityUuid ||
    !FILE_ID.test(fileId) || !SAFE_UUID.test(orgUuid) || !SAFE_UUID.test(communityUuid)
  ) {
    return ''
  }
  return getCommunityMediaDirectory(orgUuid, communityUuid, fileId)
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    communityImage: {
      insertCommunityImage: (attrs: CommunityImageAttrs) => ReturnType
    }
  }
}

const dataAttr = (name: string) => ({
  default: null,
  parseHTML: (el: HTMLElement) => el.getAttribute(name),
  // Rendered by the node itself (below), not as raw attributes.
  renderHTML: () => ({}),
})

export const CommunityImage = Node.create({
  name: 'communityImage',
  group: 'block',
  atom: true,
  draggable: true,
  selectable: true,

  addAttributes() {
    return {
      fileId: dataAttr('data-file-id'),
      orgUuid: dataAttr('data-org-uuid'),
      communityUuid: dataAttr('data-community-uuid'),
      alt: {
        default: null,
        parseHTML: (el: HTMLElement) => el.querySelector('img')?.getAttribute('alt') || null,
        renderHTML: () => ({}),
      },
    }
  },

  parseHTML() {
    return [{ tag: 'figure[data-community-image]' }]
  },

  renderHTML({ node, HTMLAttributes }) {
    const attrs = node.attrs as CommunityImageAttrs
    const src = communityImageUrl(attrs)
    return [
      'figure',
      mergeAttributes(HTMLAttributes, {
        'data-community-image': '',
        'data-file-id': attrs.fileId,
        'data-org-uuid': attrs.orgUuid,
        'data-community-uuid': attrs.communityUuid,
        class: 'discussion-image',
      }),
      [
        'a',
        { href: src, target: '_blank', rel: 'noopener noreferrer' },
        ['img', { src, alt: attrs.alt || '', loading: 'lazy', draggable: 'false' }],
      ],
    ]
  },

  addCommands() {
    return {
      insertCommunityImage:
        (attrs: CommunityImageAttrs) =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, attrs }),
    }
  },
})

/** Number of uploaded images in a tiptap document. */
export function countCommunityImages(doc: any): number {
  if (!doc || typeof doc !== 'object') return 0
  const self = doc.type === 'communityImage' ? 1 : 0
  return self + (Array.isArray(doc.content) ? doc.content.reduce((n: number, c: any) => n + countCommunityImages(c), 0) : 0)
}

export default CommunityImage
