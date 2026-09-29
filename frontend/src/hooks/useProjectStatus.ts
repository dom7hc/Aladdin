import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getProjectStatus, startGeneration } from '@/api/projectApi'
import { TERMINAL_STATUSES } from '@/lib/status'

import { queryKeys } from './queryKeys'

interface UseProjectStatusOptions {
  enabled?: boolean
  poll?: boolean
  intervalMs?: number
}

export function useProjectStatusQuery(
  id: string | undefined,
  { enabled = true, poll = false, intervalMs = 2500 }: UseProjectStatusOptions = {},
) {
  return useQuery({
    queryKey: queryKeys.status(id ?? ''),
    queryFn: () => getProjectStatus(id as string),
    enabled: Boolean(id) && enabled,
    refetchInterval: (query) => {
      if (!poll) return false
      const status = query.state.data?.status
      if (status && TERMINAL_STATUSES.includes(status)) return false
      return intervalMs
    },
  })
}

export function useStartGeneration(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => startGeneration(id),
    onSuccess: (status) => {
      queryClient.setQueryData(queryKeys.status(id), status)
    },
  })
}
