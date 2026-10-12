'use client'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import {
  COMMUNITY_IMAGE_MAX_BYTES,
  COMMUNITY_IMAGE_TYPES,
  CommunityMediaUpload,
  uploadCommunityMedia,
} from '@services/communities/discussions'

/**
 * Uploads images to a community's media store, one at a time, reporting each
 * finished upload through `onUploaded` so callers can show it right away.
 * Type/size/count problems are reported with a toast and the file skipped.
 */
export function useCommunityImageUpload(communityUuid?: string) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const accessToken = session?.data?.tokens?.access_token
  const [pending, setPending] = useState(0)

  const upload = useCallback(
    async (
      files: File[],
      remainingSlots: number,
      onUploaded: (media: CommunityMediaUpload, file: File) => void
    ) => {
      if (!communityUuid || !accessToken || files.length === 0) return

      const images = files.filter((f) => COMMUNITY_IMAGE_TYPES.includes(f.type))
      if (images.length < files.length) {
        toast.error(t('communities.media.unsupported_type', 'Only JPEG, PNG, GIF and WebP images can be uploaded.'))
      }
      let accepted = images.filter((f) => f.size <= COMMUNITY_IMAGE_MAX_BYTES)
      if (accepted.length < images.length) {
        toast.error(t('communities.media.too_large', 'Images must be 10 MB or smaller.'))
      }
      if (accepted.length > remainingSlots) {
        toast.error(t('communities.media.too_many', 'You can add up to 10 images per post.'))
        accepted = accepted.slice(0, Math.max(0, remainingSlots))
      }
      if (accepted.length === 0) return

      setPending((n) => n + accepted.length)
      for (const file of accepted) {
        try {
          const media = await uploadCommunityMedia(communityUuid, file, accessToken)
          onUploaded(media, file)
        } catch (err: any) {
          toast.error(err?.message || t('communities.media.upload_failed', 'Image upload failed.'))
        } finally {
          setPending((n) => n - 1)
        }
      }
    },
    [communityUuid, accessToken, t]
  )

  return { upload, isUploading: pending > 0, canUpload: !!communityUuid && !!accessToken }
}

/** Image files from a paste or drop event, if any. */
export function imageFilesFrom(data: DataTransfer | null | undefined): File[] {
  if (!data) return []
  return Array.from(data.files || []).filter((f) => f.type.startsWith('image/'))
}
