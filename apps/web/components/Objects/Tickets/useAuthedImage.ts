'use client'

import { useEffect, useState } from 'react'

/**
 * Load a private image with the bearer token and expose it as a blob URL.
 * Ticket images are only served to the ticket owner and org staff, so a plain
 * <img src> would depend on the session cookie reaching the API domain.
 */
export function useAuthedImage(url: string | null, token?: string): { src: string | null; error: boolean } {
  const [src, setSrc] = useState<string | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!url || !token) return
    const controller = new AbortController()
    let objectUrl: string | null = null
    setError(false)
    setSrc(null)

    fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status))
        return res.blob()
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') setError(true)
      })

    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url, token])

  return { src, error }
}
