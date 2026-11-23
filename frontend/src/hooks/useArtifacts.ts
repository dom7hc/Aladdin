import { useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { fetchSourceBundle, getArtifacts, getPresentationInput } from '@/api/artifactApi'
import { triggerDownload } from '@/lib/download'
import { openInNewTab } from '@/presentation/openInNewTab'

import { queryKeys } from './queryKeys'

export function useArtifactsQuery(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.artifacts(id ?? ''),
    queryFn: () => getArtifacts(id as string),
    enabled: Boolean(id) && enabled,
  })
}

export function useDownloadSource(id: string) {
  return useMutation({
    mutationFn: () => fetchSourceBundle(id),
    onSuccess: ({ blob, filename }) => {
      triggerDownload(blob, filename)
    },
  })
}

// One rendered file per stored snapshot: Open and Download use the same bytes.
const rendered = new Map<string, Promise<string>>()

function presentationHtml(id: string, inputHash: string): Promise<string> {
  const key = `${id}:${inputHash}`
  let html = rendered.get(key)
  if (!html) {
    html = Promise.all([getPresentationInput(id), import('@/presentation/renderPresentation')])
      .then(([input, { renderPresentationHtml }]) => renderPresentationHtml(input))
    html.catch(() => rendered.delete(key))
    rendered.set(key, html)
  }
  return html
}

/**
 * Render the slides while this page is visible. Charts measure themselves on
 * animation frames, which stop once a new tab hides this one, so rendering
 * only after the click left "Open presentation" on a blank tab.
 */
export function usePrefetchPresentation(id: string, inputHash: string | null | undefined, enabled: boolean) {
  useEffect(() => {
    if (enabled && id && inputHash) presentationHtml(id, inputHash).catch(() => {})
  }, [id, inputHash, enabled])
}

const htmlBlob = (html: string) => new Blob([html], { type: 'text/html;charset=utf-8' })

export function useOpenPresentation(id: string, inputHash: string | null | undefined) {
  return useMutation({
    mutationFn: () =>
      openInNewTab(
        () => window.open('', '_blank'),
        () => presentationHtml(id, inputHash ?? ''),
        (html) => {
          const url = URL.createObjectURL(htmlBlob(html))
          setTimeout(() => URL.revokeObjectURL(url), 60_000)
          return url
        },
      ),
  })
}

export function useDownloadPresentation(id: string, inputHash: string | null | undefined, name: string) {
  return useMutation({
    mutationFn: async () => {
      const html = await presentationHtml(id, inputHash ?? '')
      const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'aladdin'
      triggerDownload(htmlBlob(html), `${slug}-presentation.html`)
    },
  })
}
