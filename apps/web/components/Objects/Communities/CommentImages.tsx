'use client'
import React from 'react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { communityImageUrl } from './CommunityImage'
import type { CommentImage } from './richContent'

interface CommentImagesProps {
  images: CommentImage[]
  /** Shows a remove button on each image (composer / edit mode). */
  onRemove?: (index: number) => void
  /** `thumb` = small squares for the composer, `full` = in the reply itself. */
  variant?: 'thumb' | 'full'
}

export function CommentImages({ images, onRemove, variant = 'full' }: CommentImagesProps) {
  const { t } = useTranslation()
  if (images.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {images.map((img, index) => {
        const src = communityImageUrl(img)
        if (!src) return null
        return (
          <div key={`${img.fileId}-${index}`} className="relative">
            <a href={src} target="_blank" rel="noopener noreferrer" className="block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src}
                alt={img.alt || ''}
                loading="lazy"
                className={
                  variant === 'thumb'
                    ? 'h-16 w-16 object-cover rounded-md border border-gray-200'
                    : 'max-h-72 max-w-full sm:max-w-sm object-contain rounded-md border border-gray-200 bg-gray-50 cursor-zoom-in'
                }
              />
            </a>
            {onRemove && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onRemove(index)}
                aria-label={t('communities.media.remove_image', 'Remove image')}
                title={t('communities.media.remove_image', 'Remove image')}
                className="absolute -top-1.5 -end-1.5 p-0.5 rounded-full bg-neutral-900 text-white hover:bg-neutral-700 shadow"
              >
                <X size={12} />
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default CommentImages
