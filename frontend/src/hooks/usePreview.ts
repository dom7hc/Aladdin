import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getPreview, startPreview, stopPreview } from '@/api/projectApi'
import type { PreviewState } from '@/types'

import { queryKeys } from './queryKeys'

export function usePreviewQuery(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.preview(id ?? ''),
    queryFn: () => getPreview(id as string),
    enabled: Boolean(id),
    // Poll while a build runs so the UI flips to the live URL on its own.
    refetchInterval: (query) =>
      query.state.data?.status === 'building' ? 2000 : false,
  })
}

export function useStartPreview(id: string | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => startPreview(id as string),
    onSuccess: (state: PreviewState) => {
      // The backend flips to running in the background; the query polls.
      client.setQueryData(queryKeys.preview(id ?? ''), state)
    },
  })
}

export function useStopPreview(id: string | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => stopPreview(id as string),
    onSuccess: (state: PreviewState) => {
      client.setQueryData(queryKeys.preview(id ?? ''), state)
    },
  })
}
