import { useMutation, useQuery } from '@tanstack/react-query'

import { fetchDeck, fetchSourceBundle, getArtifacts } from '@/api/artifactApi'
import { triggerDownload } from '@/lib/download'

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

export function useDownloadDeck(id: string) {
  return useMutation({
    mutationFn: () => fetchDeck(id),
    onSuccess: ({ blob, filename }) => {
      triggerDownload(blob, filename)
    },
  })
}
